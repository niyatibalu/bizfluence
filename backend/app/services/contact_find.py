"""Best-effort contact discovery for India brands (free web search + email guess)."""

from __future__ import annotations

import re

from app.models import Company
from app.services.email_guess import guess_corporate_email
from app.services.llm import generate_json
from app.services.web_research import web_search, _real_hits, _filter_brand_hits


def find_marketing_contacts(company: Company) -> list[dict]:
    """
    Search the public web for likely influencer/marketing contacts.
    Returns dicts: name, title, linkedin_url, email, email_confidence, notes
    Accuracy is best-effort without LinkedIn login — user should verify before sending.
    """
    name = company.name
    domain = company.domain or ""
    queries = [
        f'"{name}" "Influencer Marketing Manager" LinkedIn India',
        f'"{name}" "Brand Partnerships" OR "Creator Partnerships" LinkedIn',
        f'"{name}" "Digital Marketing Manager" LinkedIn site:linkedin.com/in',
        f'"{name}" influencer marketing email OR contact',
    ]
    hits: list[dict[str, str]] = []
    for q in queries:
        hits.extend(web_search(q, max_results=5))
    hits = _filter_brand_hits(name, domain, _real_hits(hits))

    # Also keep linkedin profile URLs even if brand filter is strict
    for h in _real_hits(web_search(f'site:linkedin.com/in "{name}" "marketing"', 6)):
        if "linkedin.com/in" in (h.get("href") or ""):
            hits.append(h)

    raw = "\n".join(f"- {h['title']} | {h.get('href','')} | {h.get('body','')[:160]}" for h in hits[:12])

    fallback_contacts = _heuristic_contacts(hits, domain)
    data = generate_json(
        system=(
            "Extract possible marketing/influencer contacts for this India brand from search snippets. "
            "Return JSON {contacts:[{name,title,linkedin_url,notes}]}. "
            "Only include people who look real. Prefer titles: Influencer Marketing, Brand Partnerships, "
            "Creator, Digital Marketing, PR. Max 5. If unsure, return fewer. Never invent LinkedIn URLs."
        ),
        user=f"Brand: {name} ({domain})\nSnippets:\n{raw or '(none)'}",
        fallback={"contacts": fallback_contacts},
    )

    out: list[dict] = []
    for c in data.get("contacts") or fallback_contacts:
        if not isinstance(c, dict):
            continue
        person = str(c.get("name") or "").strip()
        if not person or len(person) < 3:
            continue
        title = str(c.get("title") or "Marketing / Partnerships").strip()
        li = str(c.get("linkedin_url") or "").strip()
        if li and "linkedin.com" not in li:
            li = ""
        email = ""
        confidence = ""
        parts = person.split()
        if domain and len(parts) >= 1:
            guess = guess_corporate_email(parts[0], parts[-1] if len(parts) > 1 else parts[0], domain)
            email = guess.email
            confidence = guess.confidence
        out.append(
            {
                "name": person,
                "title": title,
                "linkedin_url": li,
                "email": email,
                "email_confidence": confidence or ("guessed" if email else ""),
                "notes": str(c.get("notes") or "Found via public web search — verify before outreach."),
            }
        )
    return out[:5]


def _heuristic_contacts(hits: list[dict[str, str]], domain: str) -> list[dict]:
    contacts: list[dict] = []
    for h in hits:
        href = h.get("href") or ""
        title = h.get("title") or ""
        m = re.search(r"linkedin\.com/in/([A-Za-z0-9_-]+)", href)
        if not m:
            continue
        # Title often "Name - Role - Company | LinkedIn"
        name_part = title.split("-")[0].split("|")[0].strip()
        if len(name_part.split()) > 4 or len(name_part) < 3:
            continue
        role = ""
        if "-" in title:
            role = title.split("-")[1].strip()[:80]
        contacts.append(
            {
                "name": name_part,
                "title": role or "Marketing",
                "linkedin_url": f"https://www.linkedin.com/in/{m.group(1)}",
                "notes": "Parsed from LinkedIn search result — verify profile.",
            }
        )
    return contacts[:3]
