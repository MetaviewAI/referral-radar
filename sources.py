"""The data layer: every network call the kit makes, normalised into plain dicts and ranked for relevance.

Python 3.9+ and `requests`. Set OFFLINE=1 to use fixtures/ instead of the network.
"""
import hashlib
import html
import json
import os
import re
import sys
import time

import requests

ROOT = os.path.dirname(os.path.abspath(__file__))


def load_dotenv():
    """KEY=value lines from .env next to the scripts, without overriding what is already exported."""
    path = os.path.join(ROOT, ".env")
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip("'\""))


load_dotenv()
OFFLINE = os.environ.get("OFFLINE") == "1"
EXA_KEY = os.environ.get("EXA_API_KEY", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
TIMEOUT = 8
JOBS_TIMEOUT = 45  # big Lever boards (e.g. palantir, ~6 MB) take 15-25s
TOP_JOBS = 25
EARLY_CAREER = re.compile(r"\b(grad|graduate|intern(s|ships?)?|junior|early[- ]career|entry[- ]level|placement|apprentice(ship)?)\b", re.I)
ENGINEERING = re.compile(r"\b(engineers?|developer|software|ml|machine learning|scientist|devops|sre)\b", re.I)
# Exa appends a generated description after each job and school ("Monzo is a Banking company. ... workforce in Germany ...").
ORG_BLURB = re.compile(r"^.{1,150}? is an? [\w ,&()-]{0,60}?\b(company|institution|organi[sz]ation|agency)\b")

NO_KEY_WARNING = """
!! EXA_API_KEY is not set, so no people search: every company will show 0 people
!! and there is nothing to find routes with.
!! Get a free key at dashboard.exa.ai (sign in and finish onboarding; skipping it loses
!! the $10 free credit), then: export EXA_API_KEY=<key> and run this again.
"""


def log(msg):
    print(msg, file=sys.stderr)


def http(url, body=None, headers=None, timeout=TIMEOUT):
    """One HTTP call. POST when body is given, else GET. Raises on a non-2xx."""
    r = requests.request("POST" if body is not None else "GET", url, json=body, timeout=timeout,
                         headers={"User-Agent": "referral-radar/1.0", **(headers or {})})
    r.raise_for_status()
    return r.json()


def fixture(name):
    path = os.path.join(ROOT, "fixtures", name + ".json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def fetch(url, body=None, headers=None, timeout=TIMEOUT, fixture_name=None):
    """http() with a disk cache, retries on 429, and a fixture to fall back on when offline or the
    call fails. Returns (data, source) where source is live / cache / fixture / missing."""
    key = hashlib.sha1(json.dumps([url, body], sort_keys=True).encode()).hexdigest()[:16]
    cached = os.path.join(ROOT, "cache", f"{fixture_name or 'r'}_{key}.json")
    if not OFFLINE:
        if os.path.exists(cached):
            with open(cached) as f:
                return json.load(f), "cache"
        for attempt in range(4):
            try:
                data = http(url, body, headers, timeout)
                os.makedirs(os.path.dirname(cached), exist_ok=True)
                with open(cached, "w") as f:
                    json.dump(data, f)
                return data, "live"
            except requests.HTTPError as e:
                if e.response.status_code == 429 and attempt < 3:
                    time.sleep(2 ** attempt)
                    continue
                log(f"  ! {url[:60]}: HTTP {e.response.status_code}")
                break
            except Exception as e:  # noqa: BLE001
                log(f"  ! {url[:60]}: {type(e).__name__}: {str(e)[:80]}")
                break
    data = fixture(fixture_name) if fixture_name else None
    if data is None:
        return None, "missing"
    return data, "fixture"


def norm(x):
    return re.sub(r"[^a-z0-9]+", " ", (x or "").lower()).replace("the university of", "university of").strip()


def found(wants, haystack):
    """The wants that appear as whole words in any of the haystack strings."""
    return [w for w in wants if w and any(f" {norm(w)} " in f" {norm(h)} " for h in haystack)]


def load_profile():
    path = os.path.join(ROOT, "profile.json")
    if not os.path.exists(path):
        path = os.path.join(ROOT, "profile.example.json")
        log("No profile.json yet, using the demo profile.example.json (Prompt 1 writes yours).")
    with open(path) as f:
        return json.load(f)


# ---------- jobs ----------

def strip_html(s):
    return re.sub(r"<[^>]+>", " ", html.unescape(s or "")).strip()


def jobs_for(ats, board, locations=()):
    """Open jobs on a public Ashby / Greenhouse / Lever board, most relevant first:
    engineering, then in the given locations, then early-career."""
    name = f"jobs_{board}"
    if ats == "greenhouse":
        data, src = fetch(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true", timeout=JOBS_TIMEOUT, fixture_name=name)
        jobs = [{"title": j["title"], "location": (j.get("location") or {}).get("name"), "url": j["absolute_url"],
                 "posted": j.get("updated_at"), "description": strip_html(j.get("content"))[:1500]} for j in (data or {}).get("jobs", [])]
    elif ats == "lever":
        data, src = fetch(f"https://api.lever.co/v0/postings/{board}?mode=json", timeout=JOBS_TIMEOUT, fixture_name=name)
        jobs = [{"title": j["text"], "location": (j.get("categories") or {}).get("location"), "url": j["hostedUrl"],
                 "team": (j.get("categories") or {}).get("team"), "description": (j.get("descriptionPlain") or "")[:1500]}
                for j in (data or [])]
    elif ats == "ashby":
        data, src = fetch(f"https://api.ashbyhq.com/posting-api/job-board/{board}", timeout=JOBS_TIMEOUT, fixture_name=name)
        jobs = [{"title": j["title"], "location": j.get("location"), "url": j.get("jobUrl"), "team": j.get("team"),
                 "department": j.get("department"), "posted": j.get("publishedAt"),
                 "description": (j.get("descriptionPlain") or "")[:1500]}
                for j in (data or {}).get("jobs", []) if j.get("isListed", True)]
    else:
        log(f"  ! unknown ats {ats!r}")
        return [], "skipped"
    for j in jobs:
        j["early_career"] = bool(EARLY_CAREER.search(j["title"]))
        j["engineering"] = bool(ENGINEERING.search(j["title"]))
        j["in_my_locations"] = bool(found(list(locations), [j["location"]]))
    jobs.sort(key=lambda j: (not j["engineering"], not j["in_my_locations"], not j["early_career"]))
    return jobs, src


# ---------- people ----------

def strip_org_blurbs(text):
    return "\n\n".join(p for p in re.split(r"\n\s*\n", text) if not ORG_BLURB.match(p.strip()))


def exa_people(query, n=8, keyword=False):
    """Exa's profile index, two ways: semantic (category=people) or exact phrases (keyword search
    restricted to linkedin.com/in). Both return the same structured entities. People are never
    bundled as fixtures (they are real people), so offline or keyless means none."""
    if not EXA_KEY or OFFLINE:
        return [], "offline" if OFFLINE else "no key"
    body = {"query": query, "numResults": n, "contents": {"text": {"maxCharacters": 8000}}}
    if keyword:
        body.update({"type": "keyword", "includeDomains": ["linkedin.com/in", "uk.linkedin.com/in"]})
    else:
        body["category"] = "people"
    data, src = fetch("https://api.exa.ai/search", body=body, headers={"x-api-key": EXA_KEY})
    people = []
    for r in (data or {}).get("results", []):
        props = ((r.get("entities") or [{}])[0].get("properties") or {})
        work = [{"title": w.get("title"), "company": (w.get("company") or {}).get("name"),
                 "from": (w.get("dates") or {}).get("from"), "to": (w.get("dates") or {}).get("to")}
                for w in props.get("workHistory") or []]
        edu = [{"institution": (e.get("institution") or {}).get("name"), "degree": e.get("degree"),
                "from": (e.get("dates") or {}).get("from"), "to": (e.get("dates") or {}).get("to")}
               for e in props.get("educationHistory") or []]
        people.append({"name": props.get("name") or (r.get("title") or "").split(" - ")[0].split(" | ")[0].strip(),
                       "url": r.get("url"), "location": props.get("location"),
                       "current": [w for w in work if w["company"] and not w["to"]],
                       "past": [w for w in work if w["company"] and w["to"]],
                       "education": edu, "text": strip_org_blurbs(r.get("text") or ""), "query": query})
    return people, src


# ---------- github ----------

def gh(path):
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return fetch(f"https://api.github.com{path}", headers=headers)


def gh_user(login):
    """name, location, bio, company of a GitHub user, where set."""
    u, _ = gh(f"/users/{login}")
    return {k: (u or {}).get(k) for k in ("name", "location", "bio", "company")}


def gh_org_members(org, n=20):
    """Public members of a GitHub org with name, location, bio and company where set."""
    members, _ = gh(f"/orgs/{org}/public_members?per_page={n}")
    return [{"login": m["login"], "url": m["html_url"], **gh_user(m["login"])} for m in (members or [])]
