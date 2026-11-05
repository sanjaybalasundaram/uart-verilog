`timescale 1ns/1ps
// UART Receiver: 8N1, samples each bit in the middle
module uart_rx #(
    parameter CLKS_PER_BIT = 434
)(
    input  wire       clk,
    input  wire       rst,
    input  wire       rx,         // serial input line
    output reg  [7:0] rx_data,
    output reg        rx_done     // high for 1 clock when a byte is received
);
    localparam IDLE = 2'd0, START = 2'd1, DATA = 2'd2, STOP = 2'd3;

    // two flip-flops to safely bring the async rx line into our clock domain
    reg rx_s1, rx_s2;
    always @(posedge clk) begin
        rx_s1 <= rx;
        rx_s2 <= rx_s1;
    end

    reg [1:0]  state;
    reg [15:0] clk_count;
    reg [2:0]  bit_index;

    always @(posedge clk) begin
        if (rst) begin
            state <= IDLE; rx_data <= 0; rx_done <= 1'b0;
            clk_count <= 0; bit_index <= 0;
        end else begin
            rx_done <= 1'b0;
            case (state)
                IDLE: begin
                    clk_count <= 0; bit_index <= 0;
                    if (rx_s2 == 1'b0) state <= START;   // falling edge = start bit
                end
                START: begin                              // check middle of start bit
                    if (clk_count == (CLKS_PER_BIT-1)/2) begin
                        clk_count <= 0;
                        state <= (rx_s2 == 1'b0) ? DATA : IDLE;  // reject glitches
                    end else clk_count <= clk_count + 1;
                end
                DATA: begin                               // sample each bit at its middle
                    if (clk_count == CLKS_PER_BIT-1) begin
                        clk_count <= 0;
                        rx_data[bit_index] <= rx_s2;
                        if (bit_index == 7) state <= STOP;
                        else bit_index <= bit_index + 1;
                    end else clk_count <= clk_count + 1;
                end
                STOP: begin
                    if (clk_count == CLKS_PER_BIT-1) begin
                        clk_count <= 0;
                        rx_done <= rx_s2;                 // valid only if stop bit is 1
                        state <= IDLE;
                    end else clk_count <= clk_count + 1;
                end
            endcase
        end
    end
endmodule
