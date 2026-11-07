"""Tools the agent can call. Add one: write a function, decorate it with @tool, done.

The schema the model sees is built from the function's signature and docstring, so write the
docstring for the model: say what the tool is for and what comes back.
"""
import inspect
import json
import os
import subprocess
import sys

import engine

TOOLS = {}


def tool(fn):
    """Register fn as a tool. Parameters must be str or int with a default or not."""
    params, required = {}, []
    for name, p in inspect.signature(fn).parameters.items():
        kind = "integer" if p.annotation is int else "string"
        params[name] = {"type": kind}
        if p.default is inspect.Parameter.empty:
            required.append(name)
    TOOLS[fn.__name__] = {"fn": fn, "description": inspect.getdoc(fn),
                          "schema": {"type": "object", "properties": params, "required": required}}
    return fn


@tool
def search_people(query: str, exact: int = 0):
    """Search a public index of professional profiles. Returns up to 8 people with their current and
    past jobs, education, location and profile text. Semantic by default, e.g. "People working at Monzo
    who went to the University of Edinburgh". exact=1 does a keyword search for quoted phrases instead,
    e.g. '"Monzo" "CompSoc"'. Run several different queries; one query rarely finds everyone."""
    slug = engine.re.sub(r"[^a-z0-9]+", "_", query.lower())[:60]
    people, src = engine.exa_people(f"agent_{slug}", query, keyword=bool(exact))
    for p in people:
        p["text"] = p["text"][:1500]
    return {"source": src, "people": people}


@tool
def search_jobs(company: str, ats: str, slug: str):
    """Open jobs on a company's public job board. ats is ashby, greenhouse or lever; slug is the board
    name (usually the company name in lowercase). Returns the 25 most relevant jobs: title, location,
    url, and whether they look engineering / early-career / in the student's locations."""
    jobs, src = engine.jobs_for({"name": company, "ats": ats, "slug": slug}, PROFILE.get("locations", []))
    return {"source": src, "total": len(jobs), "jobs": [{k: v for k, v in j.items() if k != "description"} for j in jobs[:25]]}


@tool
def github_org_members(org: str, n: int = 20):
    """Public members of a GitHub organisation, with name, location, bio and company where set."""
    members, _ = engine.gh(f"gh_members_{org}", f"/orgs/{org}/public_members?per_page={n}")
    out = []
    for m in (members or [])[:n]:
        u, _ = engine.gh(f"gh_user_{m['login']}", f"/users/{m['login']}")
        out.append({"login": m["login"], "url": m["html_url"], **{k: (u or {}).get(k) for k in ("name", "location", "bio", "company")}})
    return out


@tool
def check_message(text: str):
    """Run a draft message through slop_check.py. Returns ok, or the list of reasons it sounds like a
    bot. Fix every reason and check again before saving."""
    r = subprocess.run([sys.executable, os.path.join(engine.ROOT, "slop_check.py")], input=text, capture_output=True, text=True)
    return {"ok": r.returncode == 0, "problems": (r.stdout + r.stderr).strip()}


@tool
def save_routes(markdown: str):
    """Write the finished routes.md and stop. Ranked routes per company, the quoted evidence for each
    shared thing, and one message per route that passed check_message."""
    with open(os.path.join(engine.ROOT, "routes.md"), "w") as f:
        f.write(markdown)
    return {"saved": "routes.md", "chars": len(markdown)}


PROFILE = {}


def load_profile():
    path = os.path.join(engine.ROOT, "profile.json")
    if not os.path.exists(path):
        path = os.path.join(engine.ROOT, "profile.example.json")
        print("No profile.json yet, using profile.example.json (Prompt 1 writes yours).", file=sys.stderr)
    with open(path) as f:
        PROFILE.update(json.load(f))
    return PROFILE
