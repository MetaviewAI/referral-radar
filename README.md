# Your Way In — build a referral radar in 20 minutes

Applications go into a black hole. A person who shares something real with you, inside the
company, is a route in. This kit finds those people and helps you write the one message they
would actually answer. Recruiters have tools like this (we build one at Metaview). Now you do.

## 30-second setup

```bash
git clone https://github.com/MetaviewAI/referral-radar && cd referral-radar
export GITHUB_TOKEN=$(gh auth token)          # 5,000 GitHub calls/hr for you instead of 60/hr for the whole room
export EXA_API_KEY=<your key: dashboard.exa.ai, Google sign-in, free, no card. Finish onboarding: Skip loses the $10 credit. Stuck? fallback key on the cheat sheet>
python3 engine.py                             # live. Or: OFFLINE=1 python3 engine.py
```

Then open the folder in your AI coding tool and paste **Prompt 1**, then **Prompt 2** from
[PROMPTS.md](PROMPTS.md). Output lands in `routes.md`. That is Level 1. Level 2 (give the agent
the tools directly over MCP and watch it plan) and Level 3 (test the agent) are in the same file.

No wifi? `OFFLINE=1 python3 engine.py` uses the bundled `fixtures/`: job board snapshots for
Metaview, Monzo and Wordsmith taken on 6 Nov 2026. People are not bundled (they are real people),
so finding routes needs a live run with your Exa key.

## What it does

```
profile.json ─► engine.py ─► research.json ─► your coding agent ─► routes.md
   you          jobs (Ashby/Greenhouse/Lever, no auth)   ranks by real overlap
                people (Exa people search)               quotes the evidence
                GitHub (shared repos, org members)       writes a 90-word message
```

## Rules of the game

- Public data only. No LinkedIn scraping, no guessed emails.
- Every route needs evidence you can quote. No evidence, no route.
- You send every message yourself, by hand. Max 5 this weekend.
- Delete `research.json` and `cache/` when you are done; it is other people's public data.

## Files

`engine.py` fetch · `slop_check.py` pipe a message in, get told why it sounds like a bot · `profile.json` you (fields: uni, course, school, societies, hometown, city, past_employers, github, hackathons, targets) · `PROMPTS.md` what to paste · `AGENTS.md` context for your coding agent · `fixtures/` offline job boards

Built for HackTheBurgh XIII by Metaview. Questions: find us at the booth.
