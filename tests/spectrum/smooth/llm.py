#!/usr/bin/env python3
# Sudden heavy CPU load: a real 7B model on the CPU (8 threads). Prints load time, time to first token, tok/s.
import time,json,sys
from llama_cpp import Llama
t=time.time()
m=Llama("/home/shawn/.local/share/luminos/models/hive/Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf",n_gpu_layers=0,n_threads=8,n_ctx=1024,verbose=False)
load=time.time()-t; t=time.time(); n=0; first=None
for c in m("Write a detailed essay about mountains, rivers and weather.",max_tokens=int(sys.argv[1]),stream=True):
    n+=1
    if first is None: first=time.time()-t
print(json.dumps({"load_s":round(load,1),"ttft_s":round(first,2),"tok":n,"tok_s":round((n-1)/(time.time()-t-first),2)}))
