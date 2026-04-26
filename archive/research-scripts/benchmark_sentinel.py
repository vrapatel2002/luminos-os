import sys
import os
import time
import threading
import subprocess

# Add src to path
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from npu.hats_kernel import HATSSentinel

def get_cpu_usage():
    # Returns average CPU usage over 1 second
    try:
        cmd = "top -bn2 -d1 | grep 'Cpu(s)' | tail -n1 | awk '{print $2 + $4}'"
        return float(subprocess.check_output(cmd, shell=True).decode().strip())
    except:
        return 0.0

def run_test(sentinel, iterations=50):
    test_text = "Checking system calls for suspicious wine activity and possible DLL injection in registry."
    
    # Warmup
    for _ in range(5):
        sentinel.classify(test_text)
    
    cpu_measurements = []
    stop_event = threading.Event()
    
    def monitor_cpu():
        while not stop_event.is_set():
            cpu_measurements.append(get_cpu_usage())
            time.sleep(0.5)
            
    monitor_thread = threading.Thread(target=monitor_cpu)
    monitor_thread.start()
    
    start = time.perf_counter()
    for _ in range(iterations):
        sentinel.classify(test_text)
    end = time.perf_counter()
    
    stop_event.set()
    monitor_thread.join()
    
    duration = end - start
    tps = iterations / duration
    avg_cpu = sum(cpu_measurements) / len(cpu_measurements) if cpu_measurements else 0.0
    
    return tps, avg_cpu

def benchmark():
    sentinel = HATSSentinel()
    sentinel.load_weights()
    
    print("Starting NPU Benchmark...")
    npu_tps, npu_cpu = run_test(sentinel)
    
    print("Starting CPU Benchmark (Forcing fallback)...")
    import npu.hats_kernel
    npu.hats_kernel._HAS_TRITON = False
    cpu_tps, cpu_cpu = run_test(sentinel)
    
    print("\n" + "="*40)
    print("SENTINEL PERFORMANCE REPORT")
    print("="*40)
    print(f"Target: MobileLLM-R1-140M INT8")
    print("-" * 40)
    print(f"NPU (HATS) TPS:  {npu_tps:6.2f} | CPU Usage: {npu_cpu:5.1f}%")
    print(f"CPU (Fallback) TPS: {cpu_tps:6.2f} | CPU Usage: {cpu_cpu:5.1f}%")
    print("-" * 40)
    print(f"NPU Speedup:    {npu_tps/cpu_tps:6.2f}x")
    print(f"CPU Relief:     {cpu_cpu - npu_cpu:6.1f}% reduction")
    print("="*40)

if __name__ == "__main__":
    benchmark()
