import sys
sys.path.insert(0,'/home/shawn/luminos-os/src')

# Test Option B
try:
    from npu.hats_kernel import HATSSentinel
    import os
    model_dir = os.path.expanduser(
      "~/.local/share/luminos/models/mobilellm-int8")
    if os.path.exists(model_dir):
        s = HATSSentinel(model_dir)
        s.load_weights()
        tests = [
          ("wine ~/.ssh/id_rsa","sentinel"),
          ("firefox /tmp/cache","sentinel"),
          ("game.exe easyanticheat","router"),
          ("notepad.exe win32","router"),
        ]
        for text, task in tests:
            r = s.classify_with_threshold(
                text, 0.7, task)
            print(f"{task}: {r['label']} "
                  f"via {r['source']} "
                  f"({r['confidence']:.2f})")
    print("Option B: OK")
except Exception as e:
    print(f"Option B: FAIL — {e}")

# Test Option A
try:
    from npu.training_collector import (
        log_sentinel, status)
    log_sentinel("test","test","normal","rules",1.0)
    print("Option A:", status())
except Exception as e:
    print(f"Option A: FAIL — {e}")

# Test Option C
try:
    from hive.nexus import Nexus
    n = Nexus()
    print(f"Option C: OK — {n.name} ready={n.is_ready()}")
except Exception as e:
    print(f"Option C: FAIL — {e}")
