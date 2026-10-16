#!/usr/bin/env python3
# Per-phase summary of a run.sh output dir.
import json,csv,sys,os,collections
d=sys.argv[1]
rows=[json.loads(l) for l in open(f"{d}/page.jsonl") if l.strip()] if os.path.exists(f"{d}/page.jsonl") else []
S=list(csv.DictReader(open(f"{d}/samples.csv")))
order=[]; [order.append(r['phase']) for r in S if r['phase'] not in order]
print(f"{'phase':10} {'secs':>4} {'pkgW avg/max':>13} {'temp max':>8} {'ppt min-max':>11} {'MHz max':>7}  vid_dropped/total  late_screen_frames worst_ms  dgpu")
for ph in order:
    s=[r for r in S if r['phase']==ph]; p=[r for r in rows if r['phase']==ph]
    w=[float(r['pkg_w']) for r in s]; tc=[float(r['tctl_c']) for r in s]; pp=[int(r['ppt_pl1']) for r in s]
    vd=f"{p[-1]['vid_dropped']-p[0]['vid_dropped']}/{p[-1]['vid_total']-p[0]['vid_total']}" if len(p)>1 else "-"
    late=sum(r['raf_late'] for r in p); worst=max([r['raf_max_ms'] for r in p],default=0); fr=sum(r['raf_frames'] for r in p)
    dg=sorted(set(r['dgpu'] for r in s))
    print(f"{ph:10} {len(s)/2:4.0f} {sum(w)/len(w):6.1f}/{max(w):5.1f} {max(tc):8.1f} {min(pp):5}-{max(pp):<5} {max(int(r['mhz_max']) for r in s):7}  {vd:>17}  {late:>5} of {fr:<6} {worst:>5}  {','.join(dg)}")
tr=open(f"{d}/trace.txt").read() if os.path.exists(f"{d}/trace.txt") else ""
print("ACPI notifies:",tr.count("smooth/notify") if "smooth/notify" in tr else tr.count("notify:"), " dGPU wakes:",tr.count("rpm_resume"))
for l in open(f"{d}/wmi_hist.txt") if os.path.exists(f"{d}/wmi_hist.txt") else []:
    if l.startswith('{'): print("WMI",l.strip())
if os.path.exists(f"{d}/llm.json"): print("LLM:",open(f"{d}/llm.json").read().strip() or open(f"{d}/llm.err").read()[-300:])
