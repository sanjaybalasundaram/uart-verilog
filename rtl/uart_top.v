`timescale 1ns/1ps
// Top module: transmitter output looped back into receiver
module uart_top #(
    parameter CLKS_PER_BIT = 434
)(
    input  wire       clk,
    input  wire       rst,
    input  wire       tx_start,
    input  wire [7:0] tx_data,
    output wire       tx_busy,
    output wire       tx_done,
    output wire [7:0] rx_data,
    output wire       rx_done,
    output wire       serial_line
);
    uart_tx #(.CLKS_PER_BIT(CLKS_PER_BIT)) u_tx (
        .clk(clk), .rst(rst), .tx_start(tx_start), .tx_data(tx_data),
        .tx(serial_line), .tx_busy(tx_busy), .tx_done(tx_done)
    );
    uart_rx #(.CLKS_PER_BIT(CLKS_PER_BIT)) u_rx (
        .clk(clk), .rst(rst), .rx(serial_line),
        .rx_data(rx_data), .rx_done(rx_done)
    );
endmodule
