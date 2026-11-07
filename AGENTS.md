# Referral radar — context for AI coding agents

This is a tiny tool for a student finding a *route in* to a company: a person they share
something real with, who can refer them. It mirrors what recruiters do with sourcing tools,
flipped around. Keep it small.

## Files

- `profile.json` — the student (gitignored; start from the demo `profile.example.json`). `unis[]` is every university they went to. `targets[]` are companies with `ats` (`ashby` | `greenhouse` | `lever`) and `slug`.
- `agent.py` — the agent: a tool-use loop over `tools.py` (Anthropic or any OpenAI-compatible API, stdlib only). It decides what to search; nothing is hardcoded. Writes `routes.md` via `save_routes`.
- `tools.py` — the tools. `@tool` registers a function; the model's schema is built from the signature and docstring. Keep each tool one job, return JSON-able data, never raise.
- `engine.py` — Python 3.9+, **standard library only, no pip installs**. Fetches jobs, people, GitHub overlap into `research.json`. `OFFLINE=1` reads `fixtures/` instead of the network. Each HTTP call times out at 8s and falls back to a fixture; never let one failing source crash the run.
- `research.json` — raw material. `companies[].jobs` (the 25 most relevant per board: engineering first, then `in_my_locations`, then `early_career`); `companies[].people` from Exa people search, each with structured `current` / `past` jobs (company, title, dates), `education` (institution, degree, dates), `location`, the public profile `text` (engine.py drops the generated company and school descriptions Exa adds, so what is left is about the person), and two hints computed by engine.py: `at_company` (a current job at the target with no end date) and `shared` (uni / school / past employer matched from the structured history, societies and hackathons matched in the text). Societies, hackathons and repos only show up in `text`, so read it. About a third of the people returned do not work at the target company; `at_company` is the filter. A person with an empty `current` list is unverified, not gone: check the `text` headline before dropping them. `github`: contributors to repos the student starred, public org members.
- `routes.md` — the output: ranked routes + messages. The coding agent writes this (gitignored).

## Data sources

| Source | Endpoint | Auth |
|---|---|---|
| Ashby job board | `GET https://api.ashbyhq.com/posting-api/job-board/{slug}` | none |
| Greenhouse job board | `GET https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true` | none (content is HTML-escaped) |
| Lever postings | `GET https://api.lever.co/v0/postings/{slug}?mode=json` | none (returns a bare array) |
| Exa people search (semantic) | `POST https://api.exa.ai/search` body `{"query","category":"people","numResults","contents":{"text":{"maxCharacters":8000}}}`. Results carry `entities[0].properties.workHistory` / `educationHistory`. Ask for 8000+ chars or the text is cut before Education. | `x-api-key: $EXA_API_KEY` |
| Exa keyword search over profiles | same endpoint, body `{"query":"\"Monzo\" \"University of Edinburgh\"","type":"keyword","includeDomains":["linkedin.com/in","uk.linkedin.com/in"],...}`. Exact phrases; same entities. engine.py runs both per hook. | same |
| GitHub | `GET https://api.github.com/...` | optional `Authorization: Bearer $GITHUB_TOKEN` (60/hr per IP without it; the venue shares one IP, so set it: `export GITHUB_TOKEN=$(gh auth token)`) |

Do not scrape LinkedIn. Exa's people index is the substitute. Do not guess emails. Do not send anything automatically; the student sends every message by hand.

## Evidence rule

A shared thing counts only if it is visible in the data (`text`, `bio`, `location`, `repo`). Quote it. "Lives in Edinburgh" is not "studied at Edinburgh". A starred repo is interest, not a contribution. If the data does not support a route, drop it.

## Message rules

- 90 words max. One ask, costing the reader 15 minutes or less. Ask for advice before asking for a referral; mention a specific job URL only if there is a fitting one.
- First sentence names the specific shared thing with a detail only a real person would mention.
- No exclamation marks. No em dashes. No bullet lists.
- Banned: "I hope this finds you well", "came across your profile", "passionate", "delve", "leverage", "excited to", "reach out", "I'd love to connect", "synergy", "journey", "pick your brain".
- Sounds like the student (`profile.how_i_talk`), not like a cover letter.
