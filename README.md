# UART Transmitter and Receiver (Verilog)

A small, parameterised UART core (8 data bits, no parity, 1 stop bit — "8N1"),
written in Verilog and checked with a self-checking testbench.

```
tx_data ──► uart_tx ──► serial line ──► uart_rx ──► rx_data
```

## Specs

| Item | Value |
|---|---|
| Frame | 8N1: start bit, 8 data bits (LSB first), stop bit |
| Clock / baud | 50 MHz / 115200 baud (`CLKS_PER_BIT = 434`, set by one parameter) |
| Transmitter | 4-state FSM: IDLE → START → DATA → STOP |
| Receiver | 2-flip-flop synchroniser, start bit checked at its middle (rejects glitches), each bit sampled at its centre, byte accepted only if the stop bit is 1 |
| Size (Yosys, generic gates) | 378 cells, 68 flip-flops (~69 LUTs on Xilinx Artix-7) |

## Tests (`tb/uart_tb.v`)

| Test | Result |
|---|---|
| Chosen bytes (`S`, `K`, `C`, 0x00, 0xFF, 0xA5) | PASS |
| All 256 byte values, transmitter looped back to receiver | PASS, 0 errors |
| Short noise glitch on the line | Ignored, no false byte |
| Frame with a bad stop bit (0) | Rejected |
| Reset in the middle of a byte | TX returns to idle, next byte received correctly |

## Run it

```sh
./run.sh
```

Needs Icarus Verilog (`brew install icarus-verilog`). It runs the testbench, prints PASS/FAIL,
and builds `sim/output.html` with the results, circuit schematics and waveforms
(schematics also need Yosys and `npm install -g netlistsvg`).

## Files

| Path | What it is |
|---|---|
| `rtl/uart_tx.v` | Transmitter |
| `rtl/uart_rx.v` | Receiver |
| `rtl/uart_top.v` | Transmitter looped back into receiver |
| `tb/uart_tb.v` | Self-checking testbench |
| `tools/make_output.py` | Builds the results page |
| `docs/` | Top-level schematic and synthesis statistics |
