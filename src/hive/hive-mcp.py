#!/home/shawn/.pyenv/versions/3.12.13/bin/python3
# [CHANGE: claude-code | 2026-05-09] HIVE Brain MCP Wrapper
# Zero overhead stdio MCP bridge to luminos-brain CLI.

import sys
import json
import subprocess

LUMINOS_BRAIN = "/usr/local/bin/luminos-brain"

def run_brain(command, arg=None):
    cmd = [LUMINOS_BRAIN, command]
    if arg:
        cmd.append(arg)
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return f"ERROR: {e.stderr.strip()}"
    except Exception as e:
        return f"EXCEPTION: {str(e)}"

def main():
    # Read one line of JSON from stdin
    line = sys.stdin.readline()
    if not line:
        return

    try:
        data = json.loads(line)
        tool = data.get("tool")
        params = data.get("params", {})
        
        output = {"ok": True}
        
        if tool == "safe":
            output["result"] = run_brain("safe", params.get("action"))
        elif tool == "log":
            output["result"] = run_brain("log", params.get("message"))
        elif tool == "query":
            output["result"] = run_brain("query", params.get("question"))
        elif tool == "think":
            output["result"] = run_brain("think", params.get("question"))
        elif tool == "status":
            output["result"] = run_brain("status")
        else:
            output = {"ok": False, "error": f"Tool '{tool}' not found"}
            
        print(json.dumps(output))
        
    except json.JSONDecodeError:
        print(json.dumps({"ok": False, "error": "Invalid JSON input"}))
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}))

if __name__ == "__main__":
    main()
