#!/usr/bin/env python3
# [CHANGE: gemini-cli | 2026-05-09] System Telemetry Reporter
# Analyzes /var/log/luminos-telemetry.csv to provide insights into system behavior.

import csv
import os
import sys
from datetime import datetime

CSV_PATH = "/var/log/luminos-telemetry.csv"

def main():
    if not os.path.exists(CSV_PATH):
        print(f"Error: Telemetry log not found at {CSV_PATH}")
        return

    data = []
    with open(CSV_PATH, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)

    if not data:
        print("No data recorded yet.")
        return

    print("Luminos OS System Behavior Report")
    print("=================================")
    print(f"Period: {data[0]['Timestamp']} to {data[-1]['Timestamp']}")
    print(f"Total samples: {len(data)}")
    print()

    # Temperature Analysis
    temps = [float(d['CPU_Temp_C']) for d in data]
    avg_temp = sum(temps) / len(temps)
    print(f"--- Temperature ---")
    print(f"Avg: {avg_temp:.1f}°C | Min: {min(temps):.1f}°C | Max: {max(temps):.1f}°C")
    
    # RAM Analysis
    used_ram = [float(d['RAM_Used_GB']) for d in data]
    avg_used = sum(used_ram) / len(used_ram)
    print(f"--- RAM Usage ---")
    print(f"Avg Used: {avg_used:.2f} GB | Peak: {max(used_ram):.2f} GB")

    # ZRAM Analysis
    orig_zram = [float(d['ZRAM_Orig_GB']) for d in data]
    compr_zram = [float(d['ZRAM_Compr_GB']) for d in data]
    
    avg_orig = sum(orig_zram) / len(orig_zram)
    avg_compr = sum(compr_zram) / len(compr_zram)
    
    print(f"--- ZRAM Behavior ---")
    print(f"Avg Stored Data: {avg_orig:.2f} GB")
    if avg_compr > 0:
        ratio = avg_orig / avg_compr
        saved = avg_orig - avg_compr
        print(f"Avg Compression Ratio: {ratio:.2f}:1")
        print(f"Avg RAM Saved: {saved:.2f} GB")
    else:
        print("ZRAM not significantly utilized yet.")

    # Hot/Cold Analysis
    hot = [int(d['Hot_Set']) for d in data]
    cold = [int(d['Cold_Set']) for d in data]
    print(f"--- LIRS Sets ---")
    print(f"Avg Hot Windows: {sum(hot)/len(hot):.1f} | Avg Cold Processes: {sum(cold)/len(cold):.1f}")

    print()
    print("Insight: High 'ZRAM_Orig' combined with high 'CPU_Temp' confirms compression overhead.")
    print("If Max Temperature > 80°C regularly, consider switching to 'lz4' algorithm.")

if __name__ == "__main__":
    main()
