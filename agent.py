#!/usr/bin/env python3
"""Referral radar, the agent. One loop: the model picks a tool, we run it, it sees the result.

Nothing about *how* to search is written down here. The model reads your profile, decides which
queries to run, reads what comes back, and writes routes.md when it has evidence.

    export EXA_API_KEY=...            # people search (dashboard.exa.ai, free)
    export ANTHROPIC_API_KEY=...      # or GEMINI_API_KEY (free at aistudio.google.com), or OPENAI_API_KEY
    #                                 (+ OPENAI_BASE_URL for Groq, OpenRouter, Ollama...). MODEL overrides the default.
    python3 agent.py

Python 3.9+ and `requests`. Tools live in tools.py; add yours there.
"""
import json
import os
import sys

import sources
import tools

MAX_STEPS = int(os.environ.get("MAX_STEPS", "30"))
ANTHROPIC = os.environ.get("ANTHROPIC_API_KEY")
GEMINI = os.environ.get("GEMINI_API_KEY")
# Gemini speaks the OpenAI chat API, so it is the OpenAI path with a different base URL.
OPENAI = os.environ.get("OPENAI_API_KEY") or GEMINI
BASE = (os.environ.get("OPENAI_BASE_URL")
        or ("https://generativelanguage.googleapis.com/v1beta/openai" if GEMINI and not os.environ.get("OPENAI_API_KEY") else "https://api.openai.com/v1")).rstrip("/")
MODEL = os.environ.get("MODEL") or ("claude-sonnet-4-5" if ANTHROPIC else "gemini-3.8-flash" if OPENAI == GEMINI else "gpt-4.1")
ROUTES = os.path.join(sources.ROOT, "routes.md")

SYSTEM = """You are a referral radar for a student. Find the people inside their target companies who
share something real with them, prove it with evidence, and write one message per route.

How to work:
- Read the profile. Decide for yourself which overlaps are worth searching (society, hackathon, school,
  hometown, past employer, uni, city) and in which order. Search for each; vary the phrasing; try exact
  keyword searches too. Stop a line of search when it stops finding new people.
- Only people whose current job (no end date) is at the target count. If a profile's text contradicts
  the structured history, say so.
- Score what you actually have in common: same society or hackathon 5, same school or hometown 4,
  contributed to the same repo 4, same past employer 3, same uni 2 (+1 same course), same city 1.
  A claim with no quote from the data scores 0. "Lives in Edinburgh" is not "studied at Edinburgh".
- Pull the jobs for each target and name a fitting job URL only when there is one.
- Write each message in the student's voice (profile.how_i_talk). 90 words max. First sentence names
  the specific shared thing with a detail only a real person would mention. One ask, 15 minutes of the
  reader's time or less; ask for advice before asking for a referral. No exclamation marks, no em
  dashes, no bullet lists, no "I hope this finds you well", "came across your profile", "passionate",
  "delve", "leverage", "excited to", "reach out", "I'd love to connect", "synergy", "journey",
  "pick your brain". Run every message through check_message and fix what it flags.
- Finish by calling save_routes with: per company, the top 3 routes ranked by score, each with name,
  profile url, score, the quoted evidence, and the message. Then a one-line list of people found who
  are not at the company. Public data only; the student sends every message by hand. After saving,
  reply with one line and stop.
"""


def llm(url, body, headers):
    try:
        return sources.http(url, body, headers, timeout=120)
    except sources.requests.HTTPError as e:
        sys.exit(f"{url}: HTTP {e.response.status_code} {e.response.text[:300]}")


def run_tool(name, args):
    print(f"  -> {name}({', '.join(f'{k}={str(v)[:60]!r}' for k, v in args.items())})", file=sys.stderr)
    try:
        out = tools.call(name, args)
    except Exception as e:  # noqa: BLE001
        out = {"error": f"{type(e).__name__}: {e}"}
    return json.dumps(out)


# ---------- Anthropic ----------

def anthropic_loop(task):
    specs = [{"name": n, "description": t["description"], "input_schema": t["schema"]} for n, t in tools.TOOLS.items()]
    messages = [{"role": "user", "content": task}]
    for _ in range(MAX_STEPS):
        r = llm("https://api.anthropic.com/v1/messages",
                {"model": MODEL, "max_tokens": 8000, "system": SYSTEM, "tools": specs, "messages": messages},
                {"x-api-key": ANTHROPIC, "anthropic-version": "2023-06-01"})
        messages.append({"role": "assistant", "content": r["content"]})
        for b in r["content"]:
            if b["type"] == "text" and b["text"].strip():
                print(b["text"].strip(), file=sys.stderr)
        calls = [b for b in r["content"] if b["type"] == "tool_use"]
        if not calls:
            return True
        messages.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": c["id"], "content": run_tool(c["name"], c["input"])} for c in calls]})
    return False


# ---------- OpenAI-compatible ----------

def openai_loop(task):
    specs = [{"type": "function", "function": {"name": n, "description": t["description"], "parameters": t["schema"]}}
             for n, t in tools.TOOLS.items()]
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": task}]
    for _ in range(MAX_STEPS):
        r = llm(f"{BASE}/chat/completions", {"model": MODEL, "messages": messages, "tools": specs}, {"Authorization": f"Bearer {OPENAI}"})
        msg = r["choices"][0]["message"]
        messages.append(msg)
        if msg.get("content"):
            print(msg["content"].strip(), file=sys.stderr)
        calls = msg.get("tool_calls") or []
        if not calls:
            return True
        for c in calls:
            messages.append({"role": "tool", "tool_call_id": c["id"], "content": run_tool(c["function"]["name"], json.loads(c["function"]["arguments"] or "{}"))})
    return False


def main():
    if not (ANTHROPIC or OPENAI):
        sys.exit("Set ANTHROPIC_API_KEY, GEMINI_API_KEY or OPENAI_API_KEY (any OpenAI-compatible endpoint works with OPENAI_BASE_URL).")
    if not sources.EXA_KEY:
        print(sources.NO_KEY_WARNING, file=sys.stderr)
    if os.path.exists(ROUTES):
        os.remove(ROUTES)
    profile = sources.load_profile()
    task = f"Here is the student's profile:\n{json.dumps(profile, indent=1)}\n\nFind their routes into every target and save routes.md."
    print(f"Referral radar agent: {MODEL}, tools: {', '.join(tools.TOOLS)}", file=sys.stderr)
    finished = (anthropic_loop if ANTHROPIC else openai_loop)(task)
    if not finished:
        print(f"Stopped after MAX_STEPS={MAX_STEPS} tool rounds; raise MAX_STEPS or tighten the task.", file=sys.stderr)
    if os.path.exists(ROUTES):
        print("\nWrote routes.md. Read it, then send the messages you believe in, by hand.")
    else:
        print("\nNo routes.md written.")


if __name__ == "__main__":
    main()
