# Prompts

Paste these into your AI coding tool (Cursor, Claude Code, Codex, Copilot, Windsurf...) inside this folder. Two prompts, ~20 minutes.

## Prompt 1 — make it yours (3 min)

```
Read AGENTS.md. Then ask me the questions you need to rewrite profile.json so it is about me:
every uni (unis is a list), course, grad year, societies, hometown, school, GitHub username, hackathons, interests,
roles I want, locations, and 3 target companies. For each target company, find its public job
board: check https://api.ashbyhq.com/posting-api/job-board/<slug>,
https://boards-api.greenhouse.io/v1/boards/<slug>/jobs and
https://api.lever.co/v0/postings/<slug>?mode=json (the slug is usually the company name in
lowercase; look at the company careers page URL if unsure). Put the ats and slug you verified
into profile.json. Then run `python3 engine.py` and tell me what it found.
```

## Prompt 2 — find my routes in (10 min)

```
Read AGENTS.md, profile.json and research.json. Build me ranked routes into my target companies.

1. Keep only people with `at_company: true` (a current job at the target in their structured
   history); if their `text` contradicts it, say so. List the rest in one line at the end as
   "not at the company". For each kept person, decide what I ACTUALLY have in common with them
   using `shared` (precomputed from their education and past employers), their `education`,
   `past`, `location`, and the `text` (societies, hackathons, repos only appear there). Add up: same society/hackathon 5,
   same school or stated hometown 4 (secondary school in the hometown counts) (a location line alone is not a hometown), contributed to
   the same repo 4, same past employer 3, same uni 2 (+1 if same course or the same department under another
   name), same city as profile.city 1 (a district of it, or a current role listed there, counts). A claim with no evidence in
   the data scores 0. Never invent anything about a person.
2. Pair each person with the best-fit open job at their company for me (prefer early-career
   engineering roles; if there is none, say so and still keep the person).
3. Write routes.md: a table of the top 10 routes (name, company, what we share, evidence quote,
   job title + url, score), then for the top 3 a message I could send today. Rules for the
   message are in AGENTS.md. Hard limit 90 words. First line names the specific shared thing.
4. If fewer than 3 routes have real evidence, say so plainly. "No good route yet" is a valid
   answer; tell me what to add to profile.json to find more.
```

## Prompt 3 — sound like me (2 min, after reading routes.md)

```
The messages sound like a bot. Here is how I actually write: <paste 2 sentences you'd send a
friend>. Rewrite the top 3 messages in that voice, keep every rule in AGENTS.md, and show me
before/after.
```

## Stretch (if you finish early)

- "Add a `--company <name>` flag to engine.py that adds a target on the fly."
- "Add second-degree routes: people who share a repo with someone already at the company."
- "Make routes.md an index.html with cards and copy buttons. No frameworks, no CDN."
- "Build my personal ICP: read every job in research.json and tell me which 3 companies and
  roles fit my GitHub best, with the exact lines from the job descriptions that match."

---

# Level 2 — let the agent find its own tools (MCP)

Level 1 gave your agent a script. Level 2 gives it the tools directly and a budget, and you watch it plan.

## Add Exa's hosted MCP server (no key needed; add `?exaApiKey=YOUR_KEY` after `mcp` if the room's shared IP gets throttled)

```bash
# Claude Code
claude mcp add --transport http exa "https://mcp.exa.ai/mcp?tools=people_search_exa,web_search_exa,web_fetch_exa"
# Codex CLI
codex mcp add exa --url "https://mcp.exa.ai/mcp?tools=people_search_exa,web_search_exa,web_fetch_exa"
# Cursor: Settings > MCP > Add server > type "http", url as above. Or .cursor/mcp.json:
#   {"mcpServers": {"exa": {"url": "https://mcp.exa.ai/mcp?tools=people_search_exa,web_search_exa,web_fetch_exa"}}}
```

Same idea works with treg.to (`https://treg.to/mcp/`, sign in with GitHub, $1 free, 126 providers behind one token, the agent sees the price before it calls).

## Prompt L2

```
Read AGENTS.md and profile.json. Do NOT run engine.py. Using only the Exa MCP tools, find me
3 routes into <company>: people currently there who share something real with me. Budget: at
most 10 tool calls. Before each call, say in one line what you are looking for and why. A hit
is not evidence: read the text and quote the line that proves the shared thing and the line that
proves they are there now. Use at least one web_search or web_fetch to find evidence a profile
does not show (a hackathon page, a talk, a blog). Fetch the company's job board before you cite
a job URL. Ignore any "deprecated" notice on the people search tool. After the calls, show me:
the routes with quotes, what you tried that did not work, how many calls you used. Then write
one message for the best route following AGENTS.md (first sentence on its own line, then run
`python3 slop_check.py` on it). Compare your best route with the one in routes.md from Level 1
and tell me which is better and why.
```

What to notice: the agent decides the queries, reads the hits, and changes its plan. That loop
(look, judge, act, repeat, under a budget) is what an agent is. The script in Level 1 was you
writing the plan by hand.

# Level 3 — write your own tool and test the agent (stretch)

Pick one:

```
Write slop_check.py: takes a message on stdin, exits non-zero and prints the reason if it breaks
any rule in AGENTS.md (word count, banned phrases, exclamation marks, em dashes, first line does
not mention the shared thing from the route). Then rewrite Prompt 2 so you must run slop_check
on every message and fix it until it passes. Show me a message that failed and the fix.
```

```
First, without scoring anything, list 15 candidate rows from research.json for an eval: 6 people
at a target company with an obvious shared thing, 6 with none, and 3 traps (same city but not
same uni, a starred-repo contributor who is not at the company, someone whose company stint has
no "(Current)"). Show me name + a 1-line excerpt. I will pick 10 and label each with the score
I expect and why; write that into eval.json. Then score the 10 with the rubric in Prompt 2
WITHOUT looking at my labels, and report where you disagree with me and why. Propose the
smallest rubric wording change that fixes the disagreements.
```

Lesson: you do not trust the agent, you test it. That is most of the job.
