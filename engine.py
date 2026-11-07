#!/usr/bin/env python3
"""Referral radar: gather the raw material for finding your route into a company.

Reads profile.json, fetches open jobs, people with something in common with you,
and GitHub overlap, and writes research.json. Your AI coding agent then does the
ranking and the writing (see PROMPTS.md).

Python 3.9+, standard library only. Set OFFLINE=1 to use fixtures/ instead of the network.
"""
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
OFFLINE = os.environ.get("OFFLINE") == "1"
EXA_KEY = os.environ.get("EXA_API_KEY", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
TIMEOUT = 8
JOBS_TIMEOUT = 45  # big Lever boards (e.g. palantir, ~6 MB) take 15-25s
EARLY_CAREER = re.compile(r"\b(grad|graduate|intern(s|ships?)?|junior|early[- ]career|entry[- ]level|placement|apprentice(ship)?)\b", re.I)
ENGINEERING = re.compile(r"\b(engineer(ing)?|developer|software|ml|machine learning|scientist|devops|sre)\b", re.I)
# Exa appends a generated description after each job and school ("Monzo is a Banking company. ... workforce in Germany ...").
ORG_BLURB = re.compile(r"^.{1,150}? is an? [\w ,&()-]{0,60}?\b(company|institution|organi[sz]ation|agency)\b")

NO_KEY_WARNING = """
!! EXA_API_KEY is not set, so no people search: every company will show 0 people
!! and there is nothing to find routes with.
!! Get a free key at dashboard.exa.ai (sign in and finish onboarding; skipping it loses
!! the $10 free credit), then: export EXA_API_KEY=<key> and run this again.
"""

log_lines = []


def log(msg):
    log_lines.append(msg)
    print(msg, file=sys.stderr)


def http(url, body=None, headers=None, timeout=TIMEOUT):
    req = urllib.request.Request(url, headers={"User-Agent": "referral-radar/1.0", **(headers or {})})
    if body is not None:
        req.data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def fixture(name):
    path = os.path.join(ROOT, "fixtures", name)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def fetch(name, url, body=None, headers=None, timeout=TIMEOUT):
    """Fetch url, falling back to fixtures/<name>.json when offline or the call fails."""
    if not OFFLINE:
        for attempt in range(4):
            try:
                data = http(url, body, headers, timeout)
                os.makedirs(os.path.join(ROOT, "cache"), exist_ok=True)
                with open(os.path.join(ROOT, "cache", name + ".json"), "w") as f:
                    json.dump(data, f)
                return data, "live"
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < 3:
                    time.sleep(2 ** attempt)
                    continue
                log(f"  ! {name}: HTTP {e.code}")
                break
            except Exception as e:  # noqa: BLE001
                log(f"  ! {name}: {type(e).__name__}: {str(e)[:80]}")
                break
    data = fixture(name + ".json")
    if data is None:
        log(f"  ! {name}: no fixture, skipping")
        return None, "missing"
    return data, "fixture"


# ---------- jobs ----------

def strip_html(s):
    return re.sub(r"<[^>]+>", " ", html.unescape(s or "")).strip()


def norm(x):
    return re.sub(r"[^a-z0-9]+", " ", (x or "").lower()).replace("the university of", "university of").strip()


def jobs_for(target, locations):
    ats, slug = target.get("ats"), target.get("slug")
    name = f"jobs_{slug}"
    if ats == "greenhouse":
        data, src = fetch(name, f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true", timeout=JOBS_TIMEOUT)
        raw = (data or {}).get("jobs", [])
        jobs = [{"title": j["title"], "location": (j.get("location") or {}).get("name"), "url": j["absolute_url"],
                 "posted": j.get("updated_at"), "description": strip_html(j.get("content"))[:1500]} for j in raw]
    elif ats == "lever":
        data, src = fetch(name, f"https://api.lever.co/v0/postings/{slug}?mode=json", timeout=JOBS_TIMEOUT)
        jobs = [{"title": j["text"], "location": (j.get("categories") or {}).get("location"), "url": j["hostedUrl"],
                 "team": (j.get("categories") or {}).get("team"), "description": (j.get("descriptionPlain") or "")[:1500]}
                for j in (data or [])]
    elif ats == "ashby":
        data, src = fetch(name, f"https://api.ashbyhq.com/posting-api/job-board/{slug}", timeout=JOBS_TIMEOUT)
        jobs = [{"title": j["title"], "location": j.get("location"), "url": j.get("jobUrl"), "team": j.get("team"),
                 "department": j.get("department"), "posted": j.get("publishedAt"),
                 "description": (j.get("descriptionPlain") or "")[:1500]}
                for j in (data or {}).get("jobs", []) if j.get("isListed", True)]
    else:
        log(f"  ! unknown ats {ats!r} for {target.get('name')}")
        return [], "skipped"
    wanted = [norm(loc) for loc in locations if loc]
    for j in jobs:
        j["early_career"] = bool(EARLY_CAREER.search(j["title"]))
        j["engineering"] = bool(ENGINEERING.search(j["title"]))
        j["in_my_locations"] = any(loc in norm(j["location"]) for loc in wanted)
    jobs.sort(key=lambda j: (not j["engineering"], not j["in_my_locations"], not j["early_career"]))
    return jobs, src


# ---------- people ----------

def strip_org_blurbs(text):
    return "\n\n".join(p for p in re.split(r"\n\s*\n", text) if not ORG_BLURB.match(p.strip()))


def exa_people(name, query, n=8, keyword=False):
    """Two ways to hit Exa's profile index: semantic (category=people) or exact phrases (keyword
    search restricted to linkedin.com/in). Both return the same structured entities."""
    body = {"query": query, "numResults": n, "contents": {"text": {"maxCharacters": 8000}}}
    if keyword:
        body.update({"type": "keyword", "includeDomains": ["linkedin.com/in", "uk.linkedin.com/in"]})
    else:
        body["category"] = "people"
    if EXA_KEY and not OFFLINE:
        data, src = fetch(name, "https://api.exa.ai/search", body=body, headers={"x-api-key": EXA_KEY})
    else:
        # people are never bundled (they are real people), so offline or keyless means none
        data = fixture(name + ".json")
        src = "fixture" if data else ("offline" if OFFLINE else "no key")
    people = []
    for r in (data or {}).get("results", []):
        props = ((r.get("entities") or [{}])[0].get("properties") or {})
        work = [{"title": w.get("title"), "company": (w.get("company") or {}).get("name"),
                 "from": (w.get("dates") or {}).get("from"), "to": (w.get("dates") or {}).get("to")}
                for w in props.get("workHistory") or []]
        edu = [{"institution": (e.get("institution") or {}).get("name"), "degree": e.get("degree"),
                "from": (e.get("dates") or {}).get("from"), "to": (e.get("dates") or {}).get("to")}
               for e in props.get("educationHistory") or []]
        people.append({"name": props.get("name") or (r.get("title") or "").split(" - ")[0].split(" | ")[0].strip(), "url": r.get("url"), "location": props.get("location"),
                       "current": [w for w in work if w["company"] and not w["to"]],
                       "past": [w for w in work if w["company"] and w["to"]],
                       "education": edu, "text": strip_org_blurbs(r.get("text") or ""), "query": query})
    return people, src


def found(wants, haystack):
    return [w for w in wants if w and any(norm(w) in h for h in haystack)]


def people_for(profile, target):
    """Exa people search, one query per hook, then deterministic flags from the structured history.

    The flags are hints for the agent: `at_company` from workHistory with no end date, `shared`
    from educationHistory / past employers / the profile text. Societies and repos only show up in
    the text, so the agent still has to read it."""
    company = target["name"]
    # Highest-scoring overlaps in the Prompt 2 rubric first, since only the first five are searched.
    hooks = [(s, "who were in") for s in profile.get("societies", [])[:1]] \
        + [(profile.get("school"), "who went to school at")] \
        + [(profile.get("hometown"), "who grew up in")] \
        + [(e, "who previously worked at") for e in profile.get("past_employers", [])[:1]] \
        + [(u, "who studied at") for u in profile.get("unis", [])]
    hooks = [(h, verb) for h, verb in hooks if h]
    out, srcs = [], []
    for hook, verb in hooks[:5]:
        slug = re.sub(r"[^a-z0-9]+", "_", f"{company}_{hook}".lower())
        people, src = exa_people(f"people_{slug}", f"People working at {company} {verb} {hook}")
        out += people
        srcs.append(src)
        people, src = exa_people(f"people_kw_{slug}", f'"{company}" "{hook}"', keyword=True)
        out += people
        srcs.append(src)
    seen, dedup = set(), []
    for p in out:
        key = norm(p["name"]) or p["url"]
        if not p["url"] or key in seen:
            continue
        seen.add(key)
        p["at_company"] = any(norm(company) in norm(w["company"]) for w in p["current"])
        institutions = [norm(e["institution"]) for e in p["education"]]
        employers = [norm(w["company"]) for w in p["past"] + p["current"]]
        p["shared"] = [f"uni: {u}" for u in found(profile.get("unis", []), institutions)] \
            + [f"school: {s}" for s in found([profile.get("school")], institutions)] \
            + [f"past employer: {e}" for e in found(profile.get("past_employers", []), employers)] \
            + [f"in text: {h}" for h in found(profile.get("societies", []) + profile.get("hackathons", []), [norm(p["text"])])]
        dedup.append(p)
    dedup.sort(key=lambda p: (not p["at_company"], -len(p["shared"])))
    return dedup, srcs


# ---------- github ----------

def gh(name, path):
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return fetch(name, f"https://api.github.com{path}", headers=headers)


def github_overlap(profile, targets):
    me = profile.get("github")
    result = {"my_starred_repos": [], "contributors_of_my_starred": [], "org_members": {}}
    if not me:
        return result
    starred, _ = gh(f"gh_starred_{me}", f"/users/{me}/starred?per_page=5")
    for repo in (starred or [])[:3]:
        full = repo["full_name"]
        result["my_starred_repos"].append(full)
        contribs, _ = gh(f"gh_contrib_{full.replace('/', '__')}", f"/repos/{full}/contributors?per_page=15")
        for c in contribs or []:
            result["contributors_of_my_starred"].append({"login": c["login"], "repo": full, "url": c["html_url"]})
    for t in targets:
        org = t.get("github_org")
        if not org:
            continue
        members, _ = gh(f"gh_members_{org}", f"/orgs/{org}/public_members?per_page=50")
        result["org_members"][t["name"]] = [{"login": m["login"], "url": m["html_url"]} for m in (members or [])]
    # enrich: a few profiles of org members so the agent can spot uni/location
    for company, members in result["org_members"].items():
        for m in members[:8]:
            u, _ = gh(f"gh_user_{m['login']}", f"/users/{m['login']}")
            if u:
                m.update({"name": u.get("name"), "location": u.get("location"), "bio": u.get("bio"), "company": u.get("company")})
    return result


# ---------- main ----------

def main():
    with open(os.path.join(ROOT, "profile.json")) as f:
        profile = json.load(f)
    log(f"Referral radar for {profile.get('name', 'you')} ({'OFFLINE' if OFFLINE else 'live'})")
    no_key = not EXA_KEY and not OFFLINE
    if no_key:
        log(NO_KEY_WARNING)
    research = {"profile": profile, "generated_at": time.strftime("%Y-%m-%d %H:%M"), "mode": "offline" if OFFLINE else "live",
                "companies": [], "github": {}, "sources": []}
    for t in profile.get("targets", []):
        log(f"- {t['name']}: jobs ...")
        jobs, jsrc = jobs_for(t, profile.get("locations", []))
        jobs, total = jobs[:25], len(jobs)
        log(f"  {len(jobs)} of {total} jobs ({jsrc}), {sum(j['engineering'] and j['in_my_locations'] for j in jobs)} engineering in your locations, "
            f"{sum(j['early_career'] for j in jobs)} early-career")
        log(f"- {t['name']}: people ...")
        people, psrcs = people_for(profile, t)
        log(f"  {len(people)} people ({', '.join(psrcs)})")
        research["companies"].append({"name": t["name"], "jobs": jobs, "people": people})
        research["sources"].append({t["name"]: {"jobs": jsrc, "people": psrcs}})
    log("- GitHub overlap ...")
    research["github"] = github_overlap(profile, profile.get("targets", []))
    research["log"] = log_lines
    with open(os.path.join(ROOT, "research.json"), "w") as f:
        json.dump(research, f, indent=1)
    n_people = sum(len(c["people"]) for c in research["companies"])
    for c in research["companies"]:
        hits = [p for p in c["people"] if p["at_company"] and p["shared"]]
        log(f"  {c['name']}: {sum(p['at_company'] for p in c['people'])} currently there, {len(hits)} with something shared: "
            + ", ".join(f"{p['name']} ({'; '.join(p['shared'])})" for p in hits[:5]))
    n_jobs = sum(len(c["jobs"]) for c in research["companies"])
    print(f"\nWrote research.json: {n_jobs} jobs, {n_people} people, {len(research['github'].get('contributors_of_my_starred', []))} shared-repo contributors.")
    if no_key:
        print(NO_KEY_WARNING)
    print("Next: paste Prompt 2 from PROMPTS.md into your coding agent.")


if __name__ == "__main__":
    main()
