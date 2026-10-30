
---

## On the GLM window (Luminos) — read this before step 5
<!-- [CHANGE: cowork | 2026-10-30] DECISION 162 — appended only to the GLM window's copy of this skill. -->
You are running on GLM-5.3, not Claude. Your own Bash runs in a sandbox, so **start workers on the laptop** with
`mcp__host-shell__run_command` and the `luminos-worker` command, which runs any model — several at once is fine:

```
luminos-worker <model> --cwd <build_dir> --tools "Read,Write,Edit,Bash(go:*)" --max-turns 30 [--effort high] "@<brief_file>"
luminos-worker <model> --resume <session_id> "<follow-up>"      # same worker, full memory
BATCH_OPTS="--cwd <build_dir> --max-turns 30" luminos-worker --batch jobs.txt   # many at once: "<model> <brief>" per line
```

| model | what it is | use it for |
|---|---|---|
| `fable` / `opus` | real Claude on Shawn's Max plan (strongest) | implementer of hard modules, the **reviewer** (step 8), third-failure rewrites |
| `sonnet` | real Claude, mid tier | tests, ordinary modules |
| `glm` | GLM-5.3 (you), pay-per-token | bulk / simple modules, second opinions |
| `glm-cheap` / `haiku` | cheapest | file listing, formatting, trivial edits |

Rules carried over from this skill: at least one worker must be `opus` or `fable` (Shawn's standing rule —
never GLM-only or haiku-only); the reviewer must not be the same model that wrote the code; parse
`session_id` from the JSON result. For parallel workers use `--batch` (GLM tends to run separate calls one after another).
If `~/builds/build-monitor/bm.py` is used, only Claude models go through it; start GLM workers with `luminos-worker`.
