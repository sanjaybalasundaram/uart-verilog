`timescale 1ns/1ps
// UART Transmitter: 8 data bits, no parity, 1 stop bit (8N1)
module uart_tx #(
    parameter CLKS_PER_BIT = 434   // 50 MHz clock / 115200 baud
)(
    input  wire       clk,
    input  wire       rst,
    input  wire       tx_start,   // pulse high for 1 clock to send tx_data
    input  wire [7:0] tx_data,
    output reg        tx,         // serial output line (idle = 1)
    output reg        tx_busy,
    output reg        tx_done     // high for 1 clock when byte is sent
);
    localparam IDLE = 2'd0, START = 2'd1, DATA = 2'd2, STOP = 2'd3;

    reg [1:0]  state;
    reg [15:0] clk_count;
    reg [2:0]  bit_index;
    reg [7:0]  data_reg;

    always @(posedge clk) begin
        if (rst) begin
            state <= IDLE; tx <= 1'b1; tx_busy <= 1'b0; tx_done <= 1'b0;
            clk_count <= 0; bit_index <= 0; data_reg <= 0;
        end else begin
            tx_done <= 1'b0;
            case (state)
                IDLE: begin
                    tx <= 1'b1;
                    clk_count <= 0;
                    bit_index <= 0;
                    if (tx_start) begin
                        data_reg <= tx_data;
                        tx_busy  <= 1'b1;
                        state    <= START;
                    end
                end
                START: begin                       // send start bit (0)
                    tx <= 1'b0;
                    if (clk_count == CLKS_PER_BIT-1) begin
                        clk_count <= 0; state <= DATA;
                    end else clk_count <= clk_count + 1;
                end
                DATA: begin                        // send 8 bits, LSB first
                    tx <= data_reg[bit_index];
                    if (clk_count == CLKS_PER_BIT-1) begin
                        clk_count <= 0;
                        if (bit_index == 7) state <= STOP;
                        else bit_index <= bit_index + 1;
                    end else clk_count <= clk_count + 1;
                end
                STOP: begin                        // send stop bit (1)
                    tx <= 1'b1;
                    if (clk_count == CLKS_PER_BIT-1) begin
                        clk_count <= 0; tx_busy <= 1'b0; tx_done <= 1'b1;
                        state <= IDLE;
                    end else clk_count <= clk_count + 1;
                end
            endcase
        end
    end
endmodule
