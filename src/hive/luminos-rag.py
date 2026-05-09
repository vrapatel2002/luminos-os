#!/home/shawn/.pyenv/versions/3.12.13/bin/python3
# [CHANGE: gemini-cli | 2026-05-09] HIVE Brain RAG system
# Step 3: Semantic search using nomic-embed + FAISS

import os
import sys
import json
import time
import numpy as np
import faiss
from llama_cpp import Llama

# Paths
BRAIN_FILE = os.path.expanduser("~/.local/share/luminos/hive-brain.md")
MODELS_DIR = os.path.expanduser("~/.local/share/luminos/models/hive")
INDEX_FILE = os.path.expanduser("~/.local/share/luminos/hive-rag.index")
CHUNKS_FILE = os.path.expanduser("~/.local/share/luminos/hive-rag-chunks.json")
NOMIC_MODEL = os.path.join(MODELS_DIR, "nomic-embed-text-v1.5.Q4_K_M.gguf")

# Configuration
EMBED_DIM = 768

def get_embed_model():
    if not os.path.exists(NOMIC_MODEL):
        raise FileNotFoundError(f"Nomic model not found at {NOMIC_MODEL}")
    
    return Llama(
        model_path=NOMIC_MODEL,
        embedding=True,
        n_ctx=2048,
        verbose=False
    )

def chunk_brain():
    if not os.path.exists(BRAIN_FILE):
        return []
    
    with open(BRAIN_FILE, "r") as f:
        lines = f.readlines()
    
    chunks = []
    current_chunk = []
    current_title = "Header"
    start_line = 1
    
    for i, line in enumerate(lines):
        if line.startswith("## "):
            if current_chunk:
                chunks.append({
                    "title": current_title,
                    "content": "".join(current_chunk).strip(),
                    "start_line": start_line,
                    "end_line": i
                })
            current_title = line.strip("# ").strip()
            current_chunk = [line]
            start_line = i + 1
        else:
            current_chunk.append(line)
            
    if current_chunk:
        chunks.append({
            "title": current_title,
            "content": "".join(current_chunk).strip(),
            "start_line": start_line,
            "end_line": len(lines)
        })
        
    return chunks

def build_index():
    print(f"Building RAG index from {BRAIN_FILE}...")
    chunks = chunk_brain()
    if not chunks:
        print("No chunks found.")
        return
    
    model = get_embed_model()
    embeddings = []
    
    for chunk in chunks:
        # Nomic prefix requirement
        text = f"search_document: {chunk['content']}"
        emb = model.create_embedding(text)
        embeddings.append(emb['data'][0]['embedding'])
        
    embeddings = np.array(embeddings).astype('float32')
    
    index = faiss.IndexFlatL2(EMBED_DIM)
    index.add(embeddings)
    
    faiss.write_index(index, INDEX_FILE)
    with open(CHUNKS_FILE, "w") as f:
        json.dump(chunks, f, indent=2)
        
    print(f"Index built with {len(chunks)} chunks.")

def query_rag(question):
    if not os.path.exists(INDEX_FILE) or not os.path.exists(CHUNKS_FILE):
        print("Index not found. Run 'build' first.")
        return
    
    # Check if index needs update (simple mtime check)
    if os.path.getmtime(BRAIN_FILE) > os.path.getmtime(INDEX_FILE):
        build_index()
        
    index = faiss.read_index(INDEX_FILE)
    with open(CHUNKS_FILE, "r") as f:
        chunks = json.load(f)
        
    model = get_embed_model()
    # Nomic prefix for query
    text = f"search_query: {question}"
    query_emb = np.array([model.create_embedding(text)['data'][0]['embedding']]).astype('float32')
    
    D, I = index.search(query_emb, 3)
    
    results = []
    for idx in I[0]:
        if idx != -1 and idx < len(chunks):
            results.append(chunks[idx]['content'])
            
    print("\n\n".join(results))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: luminos-rag.py {build|query} [question]")
        sys.exit(1)
        
    cmd = sys.argv[1]
    
    try:
        if cmd == "build":
            build_index()
        elif cmd == "query":
            if len(sys.argv) < 3:
                print("Provide a question.")
            else:
                query_rag(sys.argv[2])
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
