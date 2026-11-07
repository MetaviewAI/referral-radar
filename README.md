# Your Way In — an agent that finds your referral

Applications go into a black hole. A person who shares something real with you, inside the
company, is a route in. This kit finds those people and helps you write the one message they
would actually answer. Recruiters have tools like this (we build one at Metaview). Now you do.

## 30-second setup

```bash
git clone https://github.com/MetaviewAI/referral-radar && cd referral-radar
pip install requests
export GITHUB_TOKEN=$(gh auth token)          # 5,000 GitHub calls/hr for you instead of 60/hr for the whole room
export EXA_API_KEY=<your key: dashboard.exa.ai, Google sign-in, free, no card. Finish onboarding: Skip loses the $10 credit. Stuck? fallback key on the cheat sheet>
export ANTHROPIC_API_KEY=<yours>              # or GEMINI_API_KEY (free: aistudio.google.com) or OPENAI_API_KEY (+ OPENAI_BASE_URL for Groq / OpenRouter / Ollama)
python3 agent.py                              # watch it search, read, draft, check, save routes.md
```

Write `profile.json` first (copy `profile.example.json`, or paste **Prompt 1** from
[PROMPTS.md](PROMPTS.md) into your coding tool and let it interview you). Then run the agent.

## The agent

`agent.py` is one loop, 130 lines: the model picks a tool, we run it, it reads the result, repeat
until it calls `save_routes`. Nothing in it says *which* searches to run. The model reads your
profile and decides. The tools are in `tools.py`:

| Tool | What it does |
|---|---|
| `search_people(query, exact)` | Exa people search, semantic or exact-phrase |
| `search_jobs(company, ats, slug)` | a company's public job board |
| `github_org_members(org)` | public members of a GitHub org, with bio and location |
| `check_message(text)` | the slop detector, so it fixes its own drafts |
| `save_routes(markdown)` | writes `routes.md` and stops |

Adding a tool is a function with a docstring and `@tool`. The schema the model sees is built
from the signature, so the docstring is the whole spec.

## Your task (the workshop)

Run it once as is. Read `routes.md`. Then make the agent better than ours by changing what it
can do, not by telling it what to do. Pick one:

1. **Add a tool.** Ideas, easiest first:
   - `search_web(query)`: Exa web search (same endpoint, drop `category`) so it can find a
     person's talks, blog posts or hackathon write-ups and quote them.
   - `github_contributors(repo)`: who contributed to a repo you starred (`GET /repos/{owner}/{repo}/contributors`).
   - `read_page(url)`: fetch a URL and return its text, so it can read a job ad or a personal site
     before writing.
   - `company_news(company)`: Exa search with `category: "news"`, so the message can mention
     something that happened this month.
   - `ask_me(question)`: `input()` on the terminal. Let the agent ask *you* when it is unsure
     whether a shared thing is real.
2. **Change a tool.** `search_people` returns 8 results. Make it 20 and see if the ranking
   changes. Make `check_message` stricter (ban "I noticed", cap at 60 words) and watch the
   drafts change. Make `save_routes` refuse a route with no quoted evidence.
3. **Change nothing but the system prompt** in `agent.py` and see how little it takes to make
   the messages sound like you.

Ship: a diff, a `routes.md`, and one message you would actually send. Show us at the booth.

No LLM key? `python3 engine.py` runs the old fixed pipeline, then paste **Prompt 2** into your
coding tool. Same output, you do the planning. No wifi? `OFFLINE=1 python3 engine.py` uses the
bundled `fixtures/`.

No wifi? `OFFLINE=1 python3 engine.py` uses the bundled `fixtures/`: job board snapshots for
Metaview, Monzo and Wordsmith taken on 6 Nov 2026. People are not bundled (they are real people),
so finding routes needs a live run with your Exa key.

## What it does

```
profile.json ─► agent.py ◄──► tools.py ─► routes.md
   you          decides what   jobs, people,   ranked routes, quoted evidence,
                to search      GitHub, slop    one 90-word message each
```

## Rules of the game

- Public data only. No LinkedIn scraping, no guessed emails.
- Every route needs evidence you can quote. No evidence, no route.
- You send every message yourself, by hand. Max 5 this weekend.
- Delete `research.json` and `cache/` when you are done; it is other people's public data.

## Files

`agent.py` the loop · `tools.py` what it can call · `engine.py` the fixed pipeline, no LLM key needed · `slop_check.py` pipe a message in, get told why it sounds like a bot · `profile.json` you, gitignored; copy `profile.example.json` (fields: unis, course, school, societies, hometown, city, locations, past_employers, github, hackathons, targets) · `PROMPTS.md` what to paste · `AGENTS.md` context for your coding agent · `fixtures/` offline job boards

Built for HackTheBurgh XIII by Metaview. Questions: find us at the booth.
