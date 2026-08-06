#!/usr/bin/env python
"""Prove the jobhunt stack can actually reach and READ the live web.
[CHANGE: claude-code | 2026-08-05] Phase 0b verification, PLAN.md

WHY THIS EXISTS: "the network is up" is not the property we need. Phase 4 has to
open a real job board, wait for JavaScript to build the page, and pull structured
fields out of the DOM. Any of those can fail while ping and curl both succeed:

  - plain HTTP works but the board renders client-side, so curl sees an empty shell
  - the browser launches but its build does not match the playwright wheel
  - the site serves a bot wall instead of the listing, with HTTP 200

So this asserts on CONTENT, never on a status code. If a check here can pass while
returning nothing useful, it is worthless — same rule as verify-cuda-venv.sh.

Runs headless on the iGPU. It must NOT need the dGPU gate; if this ever starts
requiring dgpu-exec-v2, something is wrong.
"""
import sys
from playwright.sync_api import sync_playwright

# Greenhouse is the first ATS in the Phase 4 queue, so it is the honest target.
# A board that is public, stable, and known to render its listing client-side.
TARGET = "https://boards.greenhouse.io/embed/job_board?for=gitlab"
FALLBACK = "https://job-boards.greenhouse.io/gitlab"

failures = []


def check(name, ok, detail=""):
    print(f"  {'ok  ' if ok else 'FAIL'}: {name}{' — ' + detail if detail else ''}")
    if not ok:
        failures.append(name)


with sync_playwright() as p:
    print("=== launching headless chromium")
    browser = p.chromium.launch(headless=True)
    # A default playwright UA advertises HeadlessChrome and gets walled by some
    # boards. Phase 4 will need a real one anyway; test what we will ship.
    page = browser.new_page(
        user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
    )

    print(f"=== GET {TARGET}")
    resp = page.goto(TARGET, wait_until="domcontentloaded", timeout=45000)
    check("page responded", resp is not None and resp.status < 400,
          f"HTTP {resp.status if resp else 'none'}")

    page.wait_for_timeout(3000)  # let client-side rendering settle
    text = page.inner_text("body")
    check("page has real text", len(text) > 500, f"{len(text)} chars")

    # The whole point: can we pull structured job data out of the DOM?
    links = page.eval_on_selector_all(
        "a[href*='/jobs/'], a[href*='job_app']",
        "els => els.map(e => e.textContent.trim()).filter(t => t.length > 2)",
    )
    if not links:
        print(f"=== no listings at embed URL, trying {FALLBACK}")
        page.goto(FALLBACK, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(3000)
        text = page.inner_text("body")
        links = page.eval_on_selector_all(
            "a[href*='/jobs/']",
            "els => els.map(e => e.textContent.trim()).filter(t => t.length > 2)",
        )

    check("extracted job titles from the DOM", len(links) > 0, f"{len(links)} found")
    for t in links[:5]:
        print(f"       · {t[:78]}")

    # A bot wall returns 200 with a challenge page. Catch that explicitly rather
    # than letting it masquerade as success.
    low = text.lower()
    walled = any(s in low for s in
                 ("verify you are human", "enable javascript and cookies",
                  "checking your browser", "access denied"))
    check("not a bot wall", not walled)

    browser.close()

print("=== PASS: the stack can reach, render, and read the live web."
      if not failures else f"=== FAIL: {', '.join(failures)}")
sys.exit(1 if failures else 0)
