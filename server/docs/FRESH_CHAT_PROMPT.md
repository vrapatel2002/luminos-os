# Fresh-chat prompt — media server LLM speed

Paste everything in the box below into a new chat.

---

## THE GOAL

I want to run a large, coding-capable LLM at a genuinely usable speed on my media
server — **on the hardware I already own, unchanged.**

"Usable" means: I can ask it a real coding question about a real file and not walk away
while it answers. Both halves matter and they are different problems:

- **Prefill** — how long before the first token appears (I send big prompts: whole files)
- **Generation** — how fast tokens come out after that

Speeding up one and ignoring the other is not a win. I want both attacked.

## THE MACHINE

- Dell Inspiron 3590, Intel i5-10210U (4 cores / 8 threads), 16 GB DDR4
- Intel UHD 620 integrated GPU, shares system RAM
- **No SSD** — both drives are rotational
- Runs Jellyfin + sonarr/radarr/prowlarr 24/7. These must keep working.
- Arch Linux. `ssh -i ~/.ssh/luminos-server shawn@192.168.2.61`
- llama.cpp built from source at `~/llama.cpp`. Models in `/srv/media/_llmtest/`.
- NO DOCKER, NO OLLAMA.

## THE RULES

1. **Never propose a purchase.** No "if you added RAM," no "an SSD would," no "on a
   newer CPU." The entire point is to push *this* device to its limit first. If a
   hardware limit is genuinely the wall, say so as a measured fact and stop — do not
   turn it into a shopping suggestion.

2. **Separate measured from predicted, always.** Never put a prediction in a results
   table next to a measurement. Label estimates as estimates, out loud.

3. **I want to use the CPU and the iGPU together on the same task.** That is a standing
   goal, not a suggestion. If you conclude it can't win, prove it with numbers.

4. **Inform, don't ask.** Don't stop to request approval before each step. Go do the
   work, tell me what you did and what it measured. Keep any code small enough that I
   can read it.

5. Tell me when you're wrong. If a number contradicts something you said earlier, say
   so plainly rather than quietly moving on.

## WHAT I WANT FROM YOU

Fresh ideas. Approaches to making this machine fast at inference that I may not have
considered. Think it through from first principles: what is actually limiting this
box, and what are all the ways — software, config, model choice, scheduling,
architecture — to get around that limit without changing the hardware.

Give me the reasoning, not just a list.

## IMPORTANT — READ THIS ONLY AFTER YOU'VE FORMED YOUR OWN IDEAS

A lot of measurement has already been done on this machine in a previous session, and
several approaches have already been built, benchmarked, and ruled out. I am
deliberately not telling you what those were, because I want your independent thinking
first.

**Once you have your own ideas written down**, go read the prior work so you don't
rebuild something that was already proven not to work:

- Memory file: `.auto-memory/project_server_llm_perf.md` (the detailed measured record)
- Full transcript: `/home/shawn/.local/share/claude-cowork/sessions/intelligent-admiring-sagan/mnt/.claude/projects/-home-shawn-luminos-os/c1394ad8-8472-4383-8301-69f19923e6b9.jsonl`
  - session name: `intelligent-admiring-sagan`
  - session id: `c1394ad8-8472-4383-8301-69f19923e6b9`
- Repo context: `server/README.md`, `server/STATUS.md`, `server/DECISIONS.md`

Then tell me: **which of your ideas survived contact with the prior results, and which
are genuinely new.** That comparison is the most valuable thing you can give me.

Note: that record contains at least one stale claim about memory bandwidth in
`server/README.md`. Verify numbers before you build on them.
