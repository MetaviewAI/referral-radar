#!/usr/bin/env python3
"""Referral radar, the fixed plan. The same sources the agent's tools use, called in an order a person wrote.

Reads profile.json, runs one people search per thing you have in common, fetches jobs and GitHub
overlap, flags what is shared, and writes research.json for Prompt 2 in PROMPTS.md to rank.
No LLM key needed. agent.py is the version where the model decides the order.

Python 3.9+ and `requests`. Set OFFLINE=1 to use fixtures/ instead of the network.
"""
import json
import os
import time

import sources
from sources import found, log


def hooks_for(profile):
    """What to search on, best-scoring overlaps first, since only the first five are searched."""
    hooks = [(s, "who were in") for s in profile.get("societies", [])[:1]] \
        + [(h, "who went to") for h in profile.get("hackathons", [])[:1]] \
        + [(profile.get("school"), "who went to school at")] \
        + [(profile.get("hometown"), "who grew up in")] \
        + [(e, "who previously worked at") for e in profile.get("past_employers", [])[:1]] \
        + [(u, "who studied at") for u in profile.get("unis", [])]
    return [(h, verb) for h, verb in hooks if h][:5]


def people_for(profile, company):
    """One semantic and one exact search per hook, then deterministic flags from the structured history.

    The flags are hints for Prompt 2: `at_company` from workHistory with no end date, `shared`
    from educationHistory / past employers / the profile text."""
    out, srcs = [], set()
    for hook, verb in hooks_for(profile):
        for query, exact in ((f"People working at {company} {verb} {hook}", False), (f'"{company}" "{hook}"', True)):
            people, src = sources.exa_people(query, keyword=exact)
            out += people
            srcs.add(src)
    seen, dedup = set(), []
    for p in out:
        key = sources.norm(p["name"]) or p["url"]
        if not p["url"] or key in seen:
            continue
        seen.add(key)
        p["at_company"] = bool(found([company], [w["company"] for w in p["current"]]))
        institutions = [e["institution"] for e in p["education"]]
        employers = [w["company"] for w in p["past"] + p["current"]]
        p["shared"] = [f"uni: {u}" for u in found(profile.get("unis", []), institutions)] \
            + [f"school: {s}" for s in found([profile.get("school")], institutions)] \
            + [f"past employer: {e}" for e in found(profile.get("past_employers", []), employers)] \
            + [f"in text: {h}" for h in found(profile.get("societies", []) + profile.get("hackathons", []), [p["text"]])]
        dedup.append(p)
    dedup.sort(key=lambda p: (not p["at_company"], -len(p["shared"])))
    return dedup, sorted(srcs)


def github_overlap(profile, targets):
    me = profile.get("github")
    result = {"my_starred_repos": [], "contributors_of_my_starred": [], "org_members": {}}
    if not me:
        return result
    starred, _ = sources.gh(f"/users/{me}/starred?per_page=5")
    for repo in (starred or [])[:3]:
        full = repo["full_name"]
        result["my_starred_repos"].append(full)
        contribs, _ = sources.gh(f"/repos/{full}/contributors?per_page=15")
        result["contributors_of_my_starred"] += [{"login": c["login"], "repo": full, "url": c["html_url"]} for c in contribs or []]
    for t in targets:
        if t.get("github_org"):
            result["org_members"][t["name"]] = sources.gh_org_members(t["github_org"], 8)
    return result


def main():
    profile = sources.load_profile()
    log(f"Referral radar for {profile.get('name', 'you')} ({'OFFLINE' if sources.OFFLINE else 'live'})")
    no_key = not sources.EXA_KEY and not sources.OFFLINE
    if no_key:
        log(sources.NO_KEY_WARNING)
    research = {"profile": profile, "generated_at": time.strftime("%Y-%m-%d %H:%M"),
                "mode": "offline" if sources.OFFLINE else "live", "companies": [], "github": {}, "sources": {}}
    for t in profile.get("targets", []):
        log(f"- {t['name']}: jobs ...")
        jobs, jsrc = sources.jobs_for(t.get("ats", ""), t.get("slug", ""), profile.get("locations", []))
        total, jobs = len(jobs), jobs[:sources.TOP_JOBS]
        log(f"  {len(jobs)} of {total} jobs ({jsrc}), {sum(j['engineering'] and j['in_my_locations'] for j in jobs)} engineering in your locations, "
            f"{sum(j['early_career'] for j in jobs)} early-career")
        log(f"- {t['name']}: people ...")
        people, psrcs = people_for(profile, t["name"])
        log(f"  {len(people)} people ({', '.join(psrcs)})")
        research["companies"].append({"name": t["name"], "jobs": jobs, "people": people})
        research["sources"][t["name"]] = {"jobs": jsrc, "people": psrcs}
    log("- GitHub overlap ...")
    research["github"] = github_overlap(profile, profile.get("targets", []))
    with open(os.path.join(sources.ROOT, "research.json"), "w") as f:
        json.dump(research, f, indent=1)
    for c in research["companies"]:
        hits = [p for p in c["people"] if p["at_company"] and p["shared"]]
        log(f"  {c['name']}: {sum(p['at_company'] for p in c['people'])} currently there, {len(hits)} with something shared: "
            + ", ".join(f"{p['name']} ({'; '.join(p['shared'])})" for p in hits[:5]))
    n_jobs = sum(len(c["jobs"]) for c in research["companies"])
    n_people = sum(len(c["people"]) for c in research["companies"])
    print(f"\nWrote research.json: {n_jobs} jobs, {n_people} people, {len(research['github']['contributors_of_my_starred'])} shared-repo contributors.")
    if no_key:
        print(sources.NO_KEY_WARNING)
    print("Next: paste Prompt 2 from PROMPTS.md into your coding agent.")


if __name__ == "__main__":
    main()
