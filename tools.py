"""Tools the agent can call. Add one: write a function, annotate every parameter, give it a
docstring, decorate it with @tool. Done.

The schema the model sees is built from the signature and the docstring, so write the docstring
for the model: what the tool is for and what comes back. Parameters are str, int, float or bool.
Return anything JSON can hold. Never raise for an empty result; return it.
"""
import inspect
import os

import slop_check
import sources

# Supported parameter types: JSON schema name, and how to coerce what the model sends back.
KINDS = {str: "string", int: "integer", float: "number", bool: "boolean"}
COERCE = {str: str, int: int, float: float, bool: lambda v: str(v).lower() in ("true", "1")}
TOOLS = {}


def tool(fn):
    doc = inspect.getdoc(fn)
    assert doc, f"{fn.__name__} needs a docstring: it is what the model reads"
    props, required, coerce = {}, [], {}
    for name, p in inspect.signature(fn).parameters.items():
        assert p.annotation in KINDS, f"{fn.__name__}.{name}: annotate as one of str, int, float, bool"
        props[name] = {"type": KINDS[p.annotation]}
        coerce[name] = COERCE[p.annotation]
        if p.default is inspect.Parameter.empty:
            required.append(name)
    TOOLS[fn.__name__] = {"fn": fn, "description": doc, "coerce": coerce,
                          "schema": {"type": "object", "properties": props, "required": required}}
    return fn


def call(name, args):
    """Run a tool with arguments as the model sent them, coerced to the annotated types."""
    t = TOOLS[name]
    return t["fn"](**{k: t["coerce"][k](v) for k, v in args.items() if k in t["coerce"]})


@tool
def search_people(query: str, exact: bool = False, n: int = 8):
    """Search a public index of professional profiles. Returns up to n (max 10) people with their
    current and past jobs, education, location and profile text (societies, hackathons and repos only
    show up in the text, so read it). Semantic by default, e.g. "People working at Monzo who went to the
    University of Edinburgh". exact=true does a keyword search for quoted phrases instead, e.g.
    '"Monzo" "CompSoc"'. Run several different queries; one query rarely finds everyone."""
    people, src = sources.exa_people(query, n=min(n, 10), keyword=exact)
    for p in people:
        p["text"] = p["text"][:2500]  # keeps the model's context small; jobs and education are structured
    return {"source": src, "people": people}


@tool
def search_jobs(ats: str, board: str, locations: str = ""):
    """Open jobs on a company's public job board. ats is ashby, greenhouse or lever; board is the
    board name (usually the company name in lowercase). locations is a comma-separated list of the
    student's cities. Returns the most relevant jobs: title, location, url, and whether each looks
    engineering / early-career / in those locations."""
    jobs, src = sources.jobs_for(ats, board, [x.strip() for x in locations.split(",") if x.strip()])
    return {"source": src, "total": len(jobs), "jobs": [{k: v for k, v in j.items() if k != "description"} for j in jobs[:sources.TOP_JOBS]]}


@tool
def github_org_members(org: str, n: int = 20):
    """Public members of a GitHub organisation, with name, location, bio and company where set."""
    return sources.gh_org_members(org, n)


@tool
def check_message(text: str):
    """Run a draft message through the slop detector. Returns ok, or the list of reasons it sounds
    like a bot. Fix every reason and check again before saving."""
    found = slop_check.problems(text)
    return {"ok": not found, "problems": found}


@tool
def save_routes(markdown: str):
    """Write the finished routes.md. Ranked routes per company, the quoted evidence for each shared
    thing, and one message per route that passed check_message."""
    with open(os.path.join(sources.ROOT, "routes.md"), "w") as f:
        f.write(markdown)
    return {"saved": "routes.md", "chars": len(markdown)}
