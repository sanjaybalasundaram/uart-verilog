#!/bin/sh
# Compile and run the UART simulation, then show results, circuit and waveform
cd "$(dirname "$0")"
mkdir -p sim
iverilog -g2012 -o sim/uart_tb.vvp rtl/*.v tb/uart_tb.v || exit 1
vvp sim/uart_tb.vvp | tee sim/sim_log.txt

# Build sim/output.html (test results + circuit + waveform) and open it
python3 tools/make_output.py && open sim/output.html
