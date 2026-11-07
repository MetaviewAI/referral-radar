#!/usr/bin/env python3
"""Slop detector. Pipe a message in; exit 1 with reasons if it breaks the rules in AGENTS.md.

    echo "Hi, I hope this finds you well..." | python3 slop_check.py
"""
import re
import sys

BANNED = ["i hope this finds you well", "came across your profile", "passionate", "delve", "leverage",
          "excited to", "reach out", "i'd love to connect", "i would love to connect", "synergy", "journey",
          "pick your brain", "esteemed", "kindly"]

# agents write curly apostrophes, which would slip past the banned list
msg = sys.stdin.read().strip().replace("’", "'").replace("‘", "'")
problems = []
words = len(msg.split())
if words > 90:
    problems.append(f"{words} words, limit is 90")
if "!" in msg:
    problems.append("exclamation mark")
if "\u2014" in msg or "\u2013" in msg:
    problems.append("em dash")
if re.search(r"^\s*[-*\u2022]\s", msg, re.M):
    problems.append("bullet list")
low = msg.lower()
for b in BANNED:
    if b in low:
        problems.append(f"banned phrase: '{b}'")
first = re.split(r"(?<=[.?])\s", msg, maxsplit=1)[0]
if len(first.split()) > 30:
    problems.append("first sentence is too long to name the shared thing")
if problems:
    print("SLOP:", "; ".join(problems))
    sys.exit(1)
print(f"ok ({words} words)")
