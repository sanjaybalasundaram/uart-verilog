`timescale 1ns/1ps
// Testbench: sends bytes through TX -> RX and checks they match,
// then tests the receiver against a noise glitch, a bad stop bit and a reset mid-byte.
module uart_tb;
    localparam CLK_PERIOD   = 20;    // 50 MHz
    localparam CLKS_PER_BIT = 434;   // 115200 baud

    reg        clk = 0, rst = 1, tx_start = 0;
    reg  [7:0] tx_data = 0;
    wire       tx_busy, tx_done, rx_done, serial_line;
    wire [7:0] rx_data;

    uart_top #(.CLKS_PER_BIT(CLKS_PER_BIT)) dut (
        .clk(clk), .rst(rst), .tx_start(tx_start), .tx_data(tx_data),
        .tx_busy(tx_busy), .tx_done(tx_done),
        .rx_data(rx_data), .rx_done(rx_done), .serial_line(serial_line)
    );

    // Second receiver driven directly by the testbench, so we can send bad frames
    reg        line = 1'b1;
    wire [7:0] rx2_data;
    wire       rx2_done;
    uart_rx #(.CLKS_PER_BIT(CLKS_PER_BIT)) rx2 (
        .clk(clk), .rst(rst), .rx(line), .rx_data(rx2_data), .rx_done(rx2_done)
    );

    // Count every byte rx2 reports
    integer rx2_count = 0;
    always @(posedge clk) if (rx2_done) rx2_count = rx2_count + 1;

    always #(CLK_PERIOD/2) clk = ~clk;

    reg [7:0] test_bytes [0:5];
    integer i, errors = 0, sweep_errors, n_before;

    task check(input ok, input [8*48-1:0] msg);
        begin
            if (ok) $display("PASS  %0s", msg);
            else begin $display("FAIL  %0s", msg); errors = errors + 1; end
        end
    endtask

    // Send one byte through TX -> RX; ok = 1 if received correctly
    task send_loopback(input [7:0] b, output ok);
        begin
            @(posedge clk); tx_data <= b; tx_start <= 1;
            @(posedge clk); tx_start <= 0;
            @(posedge rx_done);
            ok = (rx_data === b);
            @(negedge tx_busy);
        end
    endtask

    task send_and_check(input [7:0] b);
        reg ok;
        begin
            send_loopback(b, ok);
            if (ok) $display("PASS  sent 0x%h ('%c')  received 0x%h", b, b, rx_data);
            else begin
                $display("FAIL  sent 0x%h  received 0x%h", b, rx_data);
                errors = errors + 1;
            end
        end
    endtask

    task wait_bits(input integer n);
        repeat (n * CLKS_PER_BIT) @(posedge clk);
    endtask

    // Drive a frame on 'line': start bit, 8 data bits (LSB first), chosen stop bit
    task drive_frame(input [7:0] b, input stop_bit);
        integer k;
        begin
            line <= 1'b0; wait_bits(1);
            for (k = 0; k < 8; k = k + 1) begin line <= b[k]; wait_bits(1); end
            line <= stop_bit; wait_bits(1);
            line <= 1'b1;
        end
    endtask

    reg ok;
    initial begin
        $dumpfile("sim/uart_tb.vcd");
        $dumpvars(0, uart_tb);

        test_bytes[0] = "S"; test_bytes[1] = "K"; test_bytes[2] = "C";
        test_bytes[3] = 8'h00; test_bytes[4] = 8'hFF; test_bytes[5] = 8'hA5;

        repeat (5) @(posedge clk);
        rst = 0;
        repeat (5) @(posedge clk);

        // Test 1: a few chosen bytes (shown in the waveform)
        for (i = 0; i < 6; i = i + 1)
            send_and_check(test_bytes[i]);
        $dumpoff;   // keep the waveform file small for the long tests below

        // Test 2: every possible byte value
        sweep_errors = 0;
        for (i = 0; i < 256; i = i + 1) begin
            send_loopback(i[7:0], ok);
            if (!ok) sweep_errors = sweep_errors + 1;
        end
        if (sweep_errors > 0) errors = errors + 1;
        $display("%0s  all 256 byte values: %0d errors", sweep_errors == 0 ? "PASS" : "FAIL", sweep_errors);

        // Test 3: a short low glitch (quarter of a bit) must not be taken as a start bit
        n_before = rx2_count;
        line <= 1'b0; repeat (CLKS_PER_BIT/4) @(posedge clk); line <= 1'b1;
        wait_bits(12);
        check(rx2_count == n_before, "noise glitch ignored (no false byte)");

        // A good frame on the same receiver still works afterwards
        n_before = rx2_count;
        drive_frame(8'h3C, 1'b1); wait_bits(2);
        check(rx2_count == n_before + 1 && rx2_data == 8'h3C, "good frame after glitch received (0x3c)");

        // Test 4: a frame whose stop bit is 0 must be rejected
        n_before = rx2_count;
        drive_frame(8'h5A, 1'b0); wait_bits(12);
        check(rx2_count == n_before, "frame with bad stop bit rejected");

        n_before = rx2_count;
        drive_frame(8'hC3, 1'b1); wait_bits(2);
        check(rx2_count == n_before + 1 && rx2_data == 8'hC3, "good frame after bad stop bit received");

        // Test 5: reset in the middle of a byte, then normal operation
        @(posedge clk); tx_data <= 8'h77; tx_start <= 1;
        @(posedge clk); tx_start <= 0;
        wait_bits(4);
        rst = 1; repeat (5) @(posedge clk);
        check(serial_line === 1'b1 && tx_busy === 1'b0, "reset mid-byte returns TX to idle");
        rst = 0; wait_bits(12);
        send_loopback(8'h96, ok);
        check(ok, "byte after reset received correctly (0x96)");

        if (errors == 0) $display("\nALL TESTS PASSED");
        else             $display("\n%0d TEST(S) FAILED", errors);
        $finish;
    end
endmodule
