#!/bin/bash
# [CHANGE: claude-code | 2026-10-24] Repeat original vs Heretic Qwen3.6 writer with nothing else on the CPU (81 vs 91 was n=1,
# and the Heretic run overlapped a quantize). Waits for the running reviewer test first.
export XDG_RUNTIME_DIR=/run/user/$(id -u)
while systemctl --user is-active --quiet heretic-review; do sleep 20; done
D=~/.config/systemd/user/luminos-coder-gateway.service.d/heretic-test.conf
P=~/luminos-os/tests/coder/proof/proof.py; cd ~/luminos-os/tests/coder/proof
rm -f $D; systemctl --user daemon-reload; systemctl --user restart luminos-coder-gateway
~/.pyenv/shims/python3 $P origW2 --arms none
printf '[Service]\nEnvironment=CODER_WRITER_GGUF=%s\n' "$HOME/.local/share/luminos/models/abliterated/Qwen3.6-35B-A3B-heretic-UD-Q3_K_XL.gguf" > $D
systemctl --user daemon-reload; systemctl --user restart luminos-coder-gateway
~/.pyenv/shims/python3 $P hereticW2 --arms none
rm -f $D; systemctl --user daemon-reload; systemctl --user stop luminos-coder-gateway   # back to defaults, model unloaded, powerd masked
echo WRITER-REPEAT-DONE
