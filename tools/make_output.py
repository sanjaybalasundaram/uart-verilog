#!/usr/bin/env python3
"""Build sim/output.html: test results, circuit schematics and waveform graphs.

Usage: python3 tools/make_output.py   (run from the project folder; run.sh does this)
"""
import html, json, os, re, shutil, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIM = os.path.join(ROOT, 'sim')
RTL = os.path.join(ROOT, 'rtl')
VCD = os.path.join(SIM, 'uart_tb.vcd')
LOG = os.path.join(SIM, 'sim_log.txt')

# Signals to plot: (label, name in the uart_tb scope or dut sub-scope)
SIGNALS = [('clk', 'uart_tb.clk'), ('rst', 'uart_tb.rst'), ('tx_start', 'uart_tb.tx_start'),
           ('tx_data', 'uart_tb.tx_data'), ('tx_busy', 'uart_tb.tx_busy'), ('tx state', 'uart_tb.dut.u_tx.state'),
           ('serial_line', 'uart_tb.serial_line'), ('rx state', 'uart_tb.dut.u_rx.state'),
           ('rx_done', 'uart_tb.rx_done'), ('rx_data', 'uart_tb.rx_data'), ('tx_done', 'uart_tb.tx_done')]
STATES = ['IDLE', 'START', 'DATA', 'STOP']


# ---------------- waveform ----------------
def read_vcd(path):
    scope, ids, width, changes, t, unit = [], {}, {}, {}, 0, 1
    with open(path) as f:
        in_ts = False
        for line in f:
            s = line.strip()
            if not s:
                continue
            if in_ts:
                m = re.match(r'(\d+)\s*(s|ms|us|ns|ps|fs)', s)
                if m:
                    unit = int(m.group(1)) * {'s': 10**15, 'ms': 10**12, 'us': 10**9, 'ns': 10**6, 'ps': 10**3, 'fs': 1}[m.group(2)]
                in_ts = '$end' not in s
                continue
            if s.startswith('$timescale'):
                rest = s[len('$timescale'):].replace('$end', '').strip()
                if rest:
                    m = re.match(r'(\d+)\s*(s|ms|us|ns|ps|fs)', rest)
                    unit = int(m.group(1)) * {'s': 10**15, 'ms': 10**12, 'us': 10**9, 'ns': 10**6, 'ps': 10**3, 'fs': 1}[m.group(2)]
                else:
                    in_ts = True
            elif s.startswith('$scope'):
                scope.append(s.split()[2])
            elif s.startswith('$upscope'):
                scope.pop()
            elif s.startswith('$var'):
                p = s.split()
                full = '.'.join(scope + [p[4]])
                ids.setdefault(full, p[3]); width[p[3]] = int(p[2]); changes.setdefault(p[3], [])
            elif s[0] == '#':
                t = int(s[1:])
            elif s[0] in '01xzXZ' and s[1:] in changes:
                changes[s[1:]].append((t, s[0].lower()))
            elif s[0] in 'bB':
                v, i = s[1:].split()
                if i in changes:
                    changes[i].append((t, v.lower()))
    return ids, width, changes, t, unit / 1e9  # unit converted to microseconds per tick


def wave_svg(vcd, t0, t1, tick_us, W=1100):
    ids, width, ch, _, us = vcd
    rows = [(lab, ids[n]) for lab, n in SIGNALS if n in ids]
    L, R, rh = 95, 12, 30
    H = len(rows) * rh + 34
    X = lambda t: L + (t - t0) / (t1 - t0) * (W - L - R)
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" class="wave">']
    span_us = (t1 - t0) * us
    k = 0
    while k * tick_us <= span_us + 1e-9:
        x = X(t0 + k * tick_us / us)
        o.append(f'<line x1="{x:.1f}" y1="4" x2="{x:.1f}" y2="{H-24}" class="grid"/>'
                 f'<text x="{x:.1f}" y="{H-8}" text-anchor="middle" class="tick">{t0*us + k*tick_us:g} µs</text>')
        k += 1
    for r, (lab, i) in enumerate(rows):
        y0 = 6 + r * rh; hi, lo = y0 + 3, y0 + rh - 9; mid = (hi + lo) / 2
        o.append(f'<text x="6" y="{mid+4}" class="name">{lab}</text>')
        lst = ch[i]; cur = 'x'
        for t, v in lst:
            if t <= t0: cur = v
            else: break
        segs, ct = [], t0
        for t, v in lst:
            if t <= t0: continue
            if t >= t1: break
            if v != cur: segs.append((ct, t, cur)); ct, cur = t, v
        segs.append((ct, t1, cur))
        if width[i] == 1:
            if lab == 'clk' and len(segs) > (W - L) / 3:   # too fast to draw: show as a band
                o.append(f'<rect x="{L}" y="{hi}" width="{W-L-R}" height="{lo-hi}" class="clkband"/>'
                         f'<text x="{(L+W)/2}" y="{mid+4}" text-anchor="middle" class="val">50 MHz clock (too fast to show at this zoom)</text>')
                continue
            d = ''
            for a, b, v in segs:
                y = hi if v == '1' else lo if v == '0' else mid
                d += f'{"M" if not d else "L"}{X(a):.1f},{y} L{X(b):.1f},{y} '
            o.append(f'<path d="{d}" class="{"line" if lab == "serial_line" else "bit"}"/>')
        else:
            for a, b, v in segs:
                xa, xb = X(a), X(b); s = min(4, (xb - xa) / 2)
                o.append(f'<path d="M{xa:.1f},{mid} L{xa+s:.1f},{hi} L{xb-s:.1f},{hi} L{xb:.1f},{mid} L{xb-s:.1f},{lo} L{xa+s:.1f},{lo} Z" class="bus"/>')
                if any(c in v for c in 'xz'): lab_v = 'x'
                elif 'state' in lab: lab_v = STATES[int(v, 2)]
                else: lab_v = '%02X' % int(v, 2)
                if xb - xa > len(lab_v) * 7 + 6:
                    o.append(f'<text x="{(xa+xb)/2:.1f}" y="{mid+4}" text-anchor="middle" class="val">{lab_v}</text>')
    o.append('</svg>')
    return '\n'.join(o)


# ---------------- schematic ----------------
def schematics():
    if not (shutil.which('yosys') and shutil.which('netlistsvg')):
        return None
    out = {}
    src = ' '.join(os.path.join(RTL, f) for f in sorted(os.listdir(RTL)) if f.endswith('.v'))
    for mod in ['uart_top', 'uart_tx', 'uart_rx']:
        js = os.path.join(SIM, f'schematic_{mod}.json')
        svg = os.path.join(SIM, f'schematic_{mod}.svg')
        cmd = f'read_verilog {src}; hierarchy -top {mod}; proc; opt -full; clean -purge; write_json {js}'
        if mod == 'uart_top':
            cmd = f'read_verilog {src}; hierarchy -top uart_top; proc; opt -full; clean -purge; select -module uart_top; write_json -selected {js}'
        r = subprocess.run(['yosys', '-q', '-p', cmd], capture_output=True, text=True)
        if r.returncode:
            out[mod] = f'<p class="err">Yosys error: {html.escape(r.stderr.strip()[-400:])}</p>'; continue
        d = json.load(open(js))
        for m in d['modules'].values():   # show "uart_tx" instead of the long "$paramod\uart_tx\..." name
            for c in m.get('cells', {}).values():
                c['type'] = re.sub(r'^\$paramod\\(\w+)\\.*$', r'\1', c['type'])
        json.dump(d, open(js, 'w'))
        subprocess.run(['netlistsvg', js, '-o', svg], capture_output=True)
        out[mod] = open(svg).read() if os.path.exists(svg) else '<p class="err">netlistsvg failed</p>'
    r = subprocess.run(['yosys', '-q', '-p', f'read_verilog {src}; synth -top uart_top -flatten; tee -o {SIM}/synth_stat.txt stat'],
                       capture_output=True, text=True)
    out['stat'] = open(f'{SIM}/synth_stat.txt').read() if os.path.exists(f'{SIM}/synth_stat.txt') else ''
    return out


# ---------------- page ----------------
def main():
    log = open(LOG, errors='replace').read() if os.path.exists(LOG) else '(no simulation log)'
    log = ''.join(c if c == '\n' or 32 <= ord(c) < 127 else '?' for c in log)
    log_html = '\n'.join(
        f'<span class="{"pass" if l.startswith("PASS") or "ALL TESTS PASSED" in l else "fail" if "FAIL" in l else ""}">{html.escape(l)}</span>'
        for l in log.rstrip().splitlines())
    ok = 'ALL TESTS PASSED' in log

    waves = ''
    if os.path.exists(VCD):
        vcd = read_vcd(VCD)
        ids, _, ch, tend, us = vcd
        starts = [t for t, v in ch.get(ids.get('uart_tb.tx_start'), []) if v == '1']
        if starts:
            a = starts[0]; nxt = starts[1] if len(starts) > 1 else tend
            span = (nxt - a) * 1.12
            waves += '<h3>One byte, close up</h3><p class="hint">The first byte sent. On <b>serial_line</b> you can read the start bit (low), 8 data bits (lowest bit first) and the stop bit (high).</p>'
            waves += '<div class="box">' + wave_svg(vcd, max(0, a - span * 0.03), a + span, 10) + '</div>'
        waves += '<h3>Whole simulation</h3><div class="box">' + wave_svg(vcd, 0, tend, 50) + '</div>'

    sch = schematics()
    if sch is None:
        circ = '<p class="err">Install Yosys and netlistsvg to draw the circuit: <code>brew install yosys</code> and <code>npm install -g netlistsvg</code></p>'
    else:
        ffs = sum(int(n) for n in re.findall(r'(\d+)\s+\$_S?DFFE?_\w+', sch['stat']))
        cells = re.search(r'(\d+) cells', sch['stat']); scope = re.search(r'(\d+)\s+\$scopeinfo', sch['stat'])
        circ = f'''<h3>Top level: transmitter looped back into receiver</h3><div class="box top">{sch['uart_top']}</div>
<h3>Transmitter (uart_tx), detailed logic</h3><p class="hint">Use the zoom buttons or scroll inside the box.</p><div class="box zoom">{sch['uart_tx']}</div>
<h3>Receiver (uart_rx), detailed logic</h3><div class="box zoom">{sch['uart_rx']}</div>
<h3>Size after synthesis (generic gates, Yosys)</h3>
<p>{int(cells.group(1)) - (int(scope.group(1)) if scope else 0) if cells else '?'} logic cells in total, of which {ffs} are flip-flops.</p>
<details><summary>Full Yosys statistics</summary><pre>{html.escape(sch['stat'])}</pre></details>'''

    page = f'''<!doctype html><html><head><meta charset="utf-8"><title>UART Simulation Output</title>
<style>
body{{font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;margin:0;background:#f6f7f9;color:#1d1f23}}
header{{background:#1d2633;color:#fff;padding:18px 28px}} header h1{{margin:0;font-size:22px}}
.badge{{display:inline-block;margin-left:12px;padding:3px 10px;border-radius:12px;font-size:14px;background:{'#1f9d55' if ok else '#c53030'}}}
nav{{padding:10px 28px;background:#fff;border-bottom:1px solid #dde1e6;position:sticky;top:0;z-index:2}} nav a{{margin-right:18px;color:#2257a8;text-decoration:none;font-weight:600}}
main{{padding:8px 28px 40px;max-width:1300px}} h2{{margin-top:30px;border-bottom:2px solid #dde1e6;padding-bottom:6px}} h3{{margin:22px 0 6px}}
.hint{{color:#555;margin:2px 0 8px}} .err{{color:#c53030}}
pre.log{{background:#16191d;color:#ddd;padding:14px 16px;border-radius:6px;font-size:13px;overflow-x:auto}}
.pass{{color:#5ee28f}} .fail{{color:#ff7b7b}}
.box{{background:#fff;border:1px solid #d5d9df;border-radius:6px;padding:8px;overflow:auto}}
.box.zoom{{height:560px}} .box.zoom svg{{width:100%;height:auto}} .box.top svg{{width:760px;max-width:100%;height:auto}} .box svg{{max-width:none}}
svg.wave{{width:100%;height:auto;font-family:Menlo,Consolas,monospace;font-size:11px}}
.grid{{stroke:#e3e6ea;stroke-dasharray:2 3}} .tick{{fill:#555}} .name{{font-weight:bold;fill:#222}}
.bit{{fill:none;stroke:#2267c9;stroke-width:1.5}} .line{{fill:none;stroke:#13925b;stroke-width:2}}
.bus{{fill:#edf3fd;stroke:#2267c9;stroke-width:1.1}} .val{{fill:#222}} .clkband{{fill:#e9eef6}}
.zbtn{{margin:0 4px 6px 0;padding:3px 10px;cursor:pointer}}
</style></head><body>
<header><h1>UART simulation output <span class="badge">{'ALL TESTS PASSED' if ok else 'CHECK RESULTS'}</span></h1></header>
<nav><a href="#results">Test results</a><a href="#circuit">Circuit</a><a href="#graph">Waveform graph</a></nav>
<main>
<h2 id="results">Test results</h2><pre class="log">{log_html}</pre>
<h2 id="circuit">Circuit</h2>{circ}
<h2 id="graph">Waveform graph</h2>{waves or '<p class="err">No waveform file found.</p>'}
</main>
<script>
document.querySelectorAll('.box.zoom').forEach(b => {{
  let z = 100; const bar = document.createElement('div');
  for (const [t, d] of [['−', -50], ['+', 50], ['Fit', 0]]) {{
    const btn = document.createElement('button'); btn.textContent = t; btn.className = 'zbtn';
    btn.onclick = () => {{ z = d ? Math.max(50, z + d) : 100; b.querySelector('svg').style.width = z + '%'; }};
    bar.appendChild(btn);
  }}
  b.parentNode.insertBefore(bar, b);
}});
</script></body></html>'''
    open(os.path.join(SIM, 'output.html'), 'w').write(page)
    print('Output page: sim/output.html')


if __name__ == '__main__':
    main()
