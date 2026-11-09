#!/usr/bin/env python3
# [CHANGE: claude-code | 2026-11-07] snappy build — 10 min idle sampler (read-only). Run as root: sudo idle.py <out> [secs] [step]
import os, sys, struct, time, glob, re
OUT = sys.argv[1]; SECS = int(sys.argv[2]) if len(sys.argv) > 2 else 600; STEP = int(sys.argv[3]) if len(sys.argv) > 3 else 10
DBG = '/sys/kernel/debug/dri/0000:65:00.0'; GM = '/sys/class/drm/card2/device/gpu_metrics'
RAPL = '/sys/class/powercap/intel-rapl:0/energy_uj'
def rd(p, d='?'):
    try:
        with open(p) as f: return f.read().strip()
    except OSError: return d
def hw(name):
    for h in glob.glob('/sys/class/hwmon/hwmon*'):
        if rd(h + '/name') == name: return h
    return None
K10, ASUS = hw('k10temp'), hw('asus')
NCPU = len(glob.glob('/sys/devices/system/cpu/cpu[0-9]*/cpuidle'))
def gm():
    b = open(GM, 'rb').read()
    pw = struct.unpack_from('<12H', b, 40); clk = struct.unpack_from('<6H', b, 64); act = struct.unpack_from('<H', b, 28)[0]
    return dict(sockW=pw[0]/1000, socW=pw[2]/1000, coresW=pw[3]/1000, gfxact=act/100, socclk=clk[1], uclk=clk[2], fclk=clk[3])
def pm():
    t = rd(DBG + '/amdgpu_pm_info', ''); g = lambda k: (re.search(r'(\d+) \w+ \(' + k + r'\)', t) or [0, '?'])[1]
    return dict(mclk=g('MCLK'), sclk=g('SCLK'), vddgfx=g('VDDGFX'), vddnb=g('VDDNB'),
                gload=(re.search(r'GPU Load: (\d+)', t) or [0, '?'])[1], dfclk=star('fclk'), dmclk=star('mclk'))
def star(k):
    m = re.findall(r'(\d+)Mhz \*', rd('/sys/class/drm/card2/device/pp_dpm_' + k, '')); return '/'.join(m) or '?'
def idle():
    u = t = c3 = 0
    for c in glob.glob('/sys/devices/system/cpu/cpu[0-9]*/cpuidle'):
        for s in glob.glob(c + '/state[1-9]'):
            u += int(rd(s + '/usage', 0)); tt = int(rd(s + '/time', 0)); t += tt
            if rd(s + '/name') == 'C3': c3 += tt
    return u, c3
def irqs():
    d = {}
    for ln in open('/proc/interrupts').read().splitlines()[1:]:
        p = ln.split()
        if not p: continue
        n = sum(int(x) for x in p[1:NCPU+1] if x.isdigit()); d[p[0].rstrip(':') + ' ' + ' '.join(p[NCPU+1:])[-40:]] = n
    return d
def ctxt():
    for ln in open('/proc/stat'):
        if ln.startswith('ctxt'): return int(ln.split()[1])
def procs():
    d = {}
    for p in glob.glob('/proc/[0-9]*/stat'):
        try:
            s = open(p).read(); r = s.rfind(')'); f = s[r+2:].split()
            d[(p.split('/')[2], f[19])] = (s[s.find('(')+1:r], int(f[11]) + int(f[12]))
        except (OSError, IndexError): pass
    return d
def mhz():
    v = [int(rd(f, 0)) for f in glob.glob('/sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_cur_freq')]
    return sum(v) // max(len(v), 1) // 1000
HZ = os.sysconf('SC_CLK_TCK'); P0 = procs(); I0 = irqs(); T0 = time.time()
o = open(OUT, 'w')
o.write(f"== start {time.strftime('%F %T')} uptime={rd('/proc/uptime').split()[0]}s ac={rd('/sys/class/power_supply/ACAD/online')} "
        f"bat={rd('/sys/class/power_supply/BAT1/capacity')}% bl={rd('/sys/class/backlight/amdgpu_bl2/brightness')} "
        f"suspends={rd('/sys/power/suspend_stats/success')}\n")
hdr = 'time pkgW sockW socW coresW gfx% socclk uclk fclk mclk sclk dfclk dmclk vddnb vddgfx gload tctl fan1 fan2 psr dgpu ppt mhz wake/s c3% ctxt/s irq/s'
o.write(hdr + '\n'); rows = []
e0 = int(rd(RAPL)); u0, c30 = idle(); x0 = ctxt(); i0 = sum(I0.values()); t0 = time.time()
while time.time() - T0 < SECS:
    time.sleep(STEP)
    e1 = int(rd(RAPL)); u1, c31 = idle(); x1 = ctxt(); i1 = sum(irqs().values()); t1 = time.time(); dt = t1 - t0
    g = gm(); m = pm()
    r = [time.strftime('%T'), round((e1-e0)/dt/1e6, 2), g['sockW'], g['socW'], g['coresW'], g['gfxact'], g['socclk'], g['uclk'], g['fclk'],
         m['mclk'], m['sclk'], m['dfclk'], m['dmclk'], m['vddnb'], m['vddgfx'], m['gload'], int(rd(K10 + '/temp1_input', 0))//1000,
         rd(ASUS + '/fan1_input'), rd(ASUS + '/fan2_input'), rd(DBG + '/eDP-2/psr_state'),
         rd('/sys/bus/pci/devices/0000:01:00.0/power/runtime_status')[:4], rd('/sys/devices/platform/asus-nb-wmi/ppt_pl1_spl'), mhz(),
         int((u1-u0)/dt), round((c31-c30)/1e4/dt/NCPU, 1), int((x1-x0)/dt), int((i1-i0)/dt)]
    rows.append(r); o.write(' '.join(map(str, r)) + '\n'); o.flush()
    e0, u0, c30, x0, i0, t0 = e1, u1, c31, x1, i1, t1
W = time.time() - T0; P1 = procs(); I1 = irqs()
avg = lambda k: round(sum(float(r[k]) for r in rows if str(r[k]).replace('.', '').isdigit()) / max(len(rows), 1), 2)
o.write('AVG ' + ' '.join(f"{h}={avg(i)}" for i, h in enumerate(hdr.split()) if i and h not in ('psr', 'dgpu', 'dfclk', 'dmclk')) + '\n')
o.write(f"== per-process CPU over {W:.0f}s (% of one core)\n")
cpu = sorted(((P1[k][1] - P0[k][1]) / HZ / W * 100, P1[k][0], k[0]) for k in P1 if k in P0)
for c, n, p in reversed(cpu[-25:]): o.write(f"  {c:6.2f}  {n}  pid {p}  {rd('/proc/'+p+'/cmdline').replace(chr(0),' ')[:90]}\n")
o.write(f"  total {sum(c for c, _, _ in cpu):.2f}\n== interrupts/s over window (top 15)\n")
for d, n in sorted(((I1[k] - I0.get(k, 0)) / W, k) for k in I1)[-15:][::-1]: o.write(f"  {d:8.1f}  {n}\n")
o.write(f"== end {time.strftime('%F %T')}\n")
