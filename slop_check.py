#!/usr/bin/env python3
"""Slop detector. Pipe a message in; exit 1 with reasons if it breaks the rules in AGENTS.md.

    echo "Hi, I hope this finds you well..." | python3 slop_check.py
"""
import re
import sys

BANNED = ["i hope this finds you well", "came across your profile", "passionate", "delve", "leverage",
          "excited to", "reach out", "i'd love to connect", "i would love to connect", "synergy", "journey",
          "pick your brain", "esteemed", "kindly"]


def problems(msg):
    """Every reason the message sounds like a bot. Empty list means it passes."""
    # agents write curly apostrophes, which would slip past the banned list
    msg = msg.strip().replace("\u2019", "'").replace("\u2018", "'")
    out = []
    words = len(msg.split())
    if words > 90:
        out.append(f"{words} words, limit is 90")
    if "!" in msg:
        out.append("exclamation mark")
    if "\u2014" in msg or "\u2013" in msg:
        out.append("em dash")
    if re.search(r"^\s*[-*\u2022]\s", msg, re.M):
        out.append("bullet list")
    low = msg.lower()
    out += [f"banned phrase: '{b}'" for b in BANNED if b in low]
    first = re.split(r"(?<=[.?])\s", msg, maxsplit=1)[0]
    if len(first.split()) > 30:
        out.append("first sentence is too long to name the shared thing")
    return out


if __name__ == "__main__":
    msg = sys.stdin.read()
    found = problems(msg)
    if found:
        print("SLOP:", "; ".join(found))
        sys.exit(1)
    print(f"ok ({len(msg.split())} words)")
