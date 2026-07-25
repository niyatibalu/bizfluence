"""In-house contact discovery — website emails + strict LinkedIn matching.

This is NOT a Hunter clone (no giant proprietary email DB). It does the parts
that actually work for India D2C brands:
1) Scrape the brand's own site for real @domain emails
2) Find LinkedIn profiles whose title clearly shows they work AT this brand
3) Guess a corporate email only for those verified people (labeled guessed)
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from app.models import Company
from app.services.email_guess import guess_corporate_email
from app.services.web_research import web_search, _real_hits, _clean_domain

_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    re.I,
)

_ROLE_WORDS = (
    "influencer",
    "creator",
    "partnership",
    "partnerships",
    "brand marketing",
    "digital marketing",
    "marketing manager",
    "marketing lead",
    "growth marketing",
    "social media",
    "collab",
    "collaboration",
    "ambassador",
    "pr manager",
    "public relations",
    "communications",
    "community",
)

_GENERIC_LOCALS = {
    "care",
    "hello",
    "hi",
    "info",
    "contact",
    "support",
    "help",
    "sales",
    "marketing",
    "pr",
    "press",
    "media",
    "partnership",
    "partnerships",
    "influencer",
    "influencers",
    "creator",
    "creators",
    "collab",
    "collaborate",
    "collaborations",
    "brand",
    "hr",
    "jobs",
    "career",
    "careers",
    "noreply",
    "no-reply",
    "donotreply",
}

_SITE_PATHS = (
    "",
    "/contact",
    "/contact-us",
    "/pages/contact",
    "/pages/contact-us",
    "/collaborate",
    "/pages/collaborate",
    "/influencer",
    "/partnerships",
)


def find_marketing_contacts(company: Company) -> tuple[list[dict], str, str]:
    domain = _clean_domain(company.domain or "")
    name = (company.name or "").strip()
    if not domain and not name:
        return [], "no_domain", "Add this brand’s website first, then try again."

    aliases = _brand_aliases(name, domain)
    # LinkedIn first (usually the useful signal), then a quick site scrape for inboxes
    people = _linkedin_people(name, domain, aliases)
    site_emails = _scrape_site_emails(domain) if domain else []
    generics = _useful_generics(site_emails, name, domain)

    pattern = _infer_pattern(site_emails, domain)
    out: list[dict] = []
    seen: set[str] = set()

    for p in people:
        key = (p.get("linkedin_url") or p["name"]).lower()
        if key in seen:
            continue
        seen.add(key)
        email, conf = _email_for_person(p["name"], domain, site_emails, pattern)
        out.append(
            {
                "name": p["name"],
                "title": p["title"],
                "linkedin_url": p.get("linkedin_url") or "",
                "email": email,
                "email_confidence": conf,
                "notes": p.get("notes")
                or "Looks like they work here — open their LinkedIn and confirm before you pitch.",
            }
        )
        if len(out) >= 5:
            break

    for e in site_emails:
        if e["kind"] != "personal":
            continue
        if e["email"].lower() in {x.get("email", "").lower() for x in out}:
            continue
        out.append(
            {
                "name": e["display_name"],
                "title": "On their site",
                "linkedin_url": "",
                "email": e["email"],
                "email_confidence": "site",
                "notes": f"Pulled from {domain}.",
            }
        )
        if len(out) >= 5:
            break

    for g in generics:
        if len(out) >= 5:
            break
        if g["email"].lower() in {x.get("email", "").lower() for x in out}:
            continue
        out.append(g)

    if out:
        n = len(out[:5])
        return (
            out[:5],
            "bizfluence",
            f"Found {n} possible contact{'s' if n != 1 else ''}. Check LinkedIn before you reach out.",
        )

    return (
        [],
        "empty",
        f"Couldn’t find a clear contact for {name or domain} yet. Paste a LinkedIn profile below and keep going.",
    )


def _brand_aliases(name: str, domain: str) -> list[str]:
    aliases: list[str] = []
    if name:
        aliases.append(name)
        aliases.append(
            re.sub(
                r"\s+(lifestyle|india|official|pvt|ltd|private|limited)\.?$",
                "",
                name,
                flags=re.I,
            ).strip()
        )
        aliases.append(name.replace(" ", ""))
        # Common stylization: boAt
        if name.lower() == "boat":
            aliases.extend(["boAt", "BoAt", "boAt Lifestyle", "Boat Lifestyle"])
    if domain:
        stem = domain.split(".")[0]
        if stem and stem not in {"www", "mail", "email"}:
            aliases.append(stem)
            aliases.append(stem.replace("-", " "))
            aliases.append(stem.replace("-", ""))
            if "boat" in stem.lower():
                aliases.extend(["boAt", "BoAt", "boAt Lifestyle"])
    cleaned = []
    seen = set()
    for a in aliases:
        a = (a or "").strip()
        if len(a) < 2:
            continue
        k = a.lower()
        if k in seen:
            continue
        seen.add(k)
        cleaned.append(a)
    cleaned.sort(key=len, reverse=True)
    return cleaned


def _scrape_site_emails(domain: str) -> list[dict[str, str]]:
    if not domain:
        return []
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }
    found: dict[str, dict[str, str]] = {}
    # One host only; follow redirects. Cap pages so Find contacts stays snappy.
    base = f"https://www.{domain}"
    try:
        with httpx.Client(timeout=6.0, follow_redirects=True, headers=headers) as client:
            fetches = 0
            for path in _SITE_PATHS:
                if fetches >= 6:
                    break
                url = base if not path else urljoin(base + "/", path.lstrip("/"))
                fetches += 1
                try:
                    r = client.get(url)
                except Exception:  # noqa: BLE001
                    continue
                if r.status_code >= 400:
                    continue
                host = (urlparse(str(r.url)).hostname or "").replace("www.", "")
                if domain not in host:
                    continue
                html = r.text[:150_000]
                for raw in _EMAIL_RE.findall(html):
                    email = raw.lower().strip(".,;:)")
                    email_domain = _clean_domain(email.split("@")[-1])
                    if email_domain != domain:
                        continue
                    if email in found:
                        continue
                    local = email.split("@")[0]
                    kind = "generic" if _is_generic_local(local) else "personal"
                    display = local.replace(".", " ").replace("_", " ").replace("-", " ").title()
                    found[email] = {
                        "email": email,
                        "kind": kind,
                        "display_name": display if kind == "personal" else f"Brand ({local})",
                    }
                if len(found) >= 10:
                    break
    except Exception:  # noqa: BLE001
        pass
    return list(found.values())


def _is_generic_local(local: str) -> bool:
    base = local.split("+")[0].lower()
    if base in _GENERIC_LOCALS:
        return True
    return any(base.startswith(g) for g in ("noreply", "no-reply", "donotreply"))


def _useful_generics(site_emails: list[dict[str, str]], name: str, domain: str) -> list[dict]:
    prefer = (
        "influencer",
        "influencers",
        "creator",
        "partnership",
        "partnerships",
        "collab",
        "marketing",
        "pr",
        "press",
        "hello",
        "care",
        "contact",
    )
    scored: list[tuple[int, dict]] = []
    for e in site_emails:
        if e["kind"] != "generic":
            continue
        local = e["email"].split("@")[0]
        score = 0
        for i, p in enumerate(prefer):
            if p in local:
                score = 20 - i
                break
        if score <= 0:
            continue
        scored.append(
            (
                score,
                {
                    "name": f"{name or domain} ({local})",
                    "title": "Brand inbox",
                    "linkedin_url": "",
                    "email": e["email"],
                    "email_confidence": "generic",
                    "notes": f"Inbox on {domain}. Fine for a first hello if you can’t find a person.",
                },
            )
        )
    scored.sort(key=lambda x: x[0], reverse=True)
    return [row for _, row in scored[:2]]


def _linkedin_people(name: str, domain: str, aliases: list[str]) -> list[dict[str, str]]:
    if not aliases:
        return []
    primary = aliases[0]
    queries = [
        f'site:linkedin.com/in "{primary}" ("Influencer Marketing" OR "Brand Partnerships" OR "Creator Partnerships")',
        f'site:linkedin.com/in "{primary}" ("Digital Marketing" OR "Brand Marketing" OR "Social Media") India',
        f'site:linkedin.com/in "{primary}" marketing manager',
    ]
    if domain:
        stem = domain.split(".")[0].replace("-", " ")
        queries.append(f'site:linkedin.com/in "{stem}" influencer OR partnerships')

    hits: list[dict[str, str]] = []
    for q in queries[:4]:
        hits.extend(web_search(q, max_results=6))
    hits = _real_hits(hits)

    people: list[dict[str, str]] = []
    seen_slugs: set[str] = set()
    for h in hits:
        href = h.get("href") or ""
        m = re.search(r"linkedin\.com/in/([A-Za-z0-9_-]+)", href, re.I)
        if not m:
            continue
        slug = m.group(1).lower()
        if slug in seen_slugs:
            continue
        title = (h.get("title") or "").replace(" | LinkedIn", "").strip()
        body = h.get("body") or ""
        parsed = _parse_linkedin_hit(title, body, aliases)
        if not parsed:
            continue
        seen_slugs.add(slug)
        people.append(
            {
                "name": parsed["name"],
                "title": parsed["title"],
                "linkedin_url": f"https://www.linkedin.com/in/{m.group(1)}",
                "notes": (
                    f"Their LinkedIn lists {primary}. Open the profile and confirm before you pitch."
                ),
                "_score": _contact_score(parsed["title"]),
            }
        )
        if len(people) >= 8:
            break
    people.sort(key=lambda p: p.get("_score", 0), reverse=True)
    for p in people:
        p.pop("_score", None)
    return people[:5]


def _contact_score(title: str) -> int:
    t = (title or "").lower()
    score = 0
    for i, w in enumerate(
        (
            "influencer",
            "creator partnership",
            "brand partnership",
            "partnership",
            "creator",
            "brand marketing",
            "digital marketing",
            "social media",
            "marketing",
        )
    ):
        if w in t:
            score += 20 - i
    return score


def _parse_linkedin_hit(title: str, body: str, aliases: list[str]) -> dict[str, str] | None:
    """Require the brand to appear as employer context — not just a case-study mention."""
    # DuckDuckGo often concatenates several LinkedIn titles into one string
    title = re.split(r"(?<=LinkedIn)\s*", title, maxsplit=1)[0]
    title = title.replace(" | LinkedIn", "").replace(" - LinkedIn", "").strip()

    blob = f"{title} {body}".lower()
    if any(x in blob for x in ("case study", "case studies", "success story")):
        if not _employer_segment_matches(title, aliases):
            return None

    if not any(a.lower() in blob for a in aliases):
        return None

    parts = [p.strip() for p in re.split(r"\s[-–—]\s", title) if p.strip()]
    if not parts:
        return None
    person = parts[0]
    person = re.split(r"(?<=[a-z])(?=[A-Z][a-z]+ [A-Z])", person)[0].strip()
    if len(person.split()) > 4 or len(person) < 3:
        return None
    if person.lower() in {"linkedin", "marketing", "india"}:
        return None

    role = _clean_role(parts[1] if len(parts) > 1 else "", aliases)
    company_seg = parts[2] if len(parts) > 2 else (parts[-1] if len(parts) > 1 else "")

    employer_ok = _text_matches_brand(company_seg, aliases) or _employer_segment_matches(title, aliases)
    if not employer_ok:
        if not (_text_matches_brand(title, aliases) and _has_role_signal(f"{role} {title} {body}")):
            return None
        if company_seg and not _text_matches_brand(company_seg, aliases):
            if len(company_seg) > 3 and not _has_role_signal(company_seg):
                return None

    if not _has_role_signal(f"{role} {title} {body}"):
        if not employer_ok:
            return None

    return {
        "name": person,
        "title": (role or "Marketing / Partnerships")[:100],
    }


def _clean_role(role: str, aliases: list[str]) -> str:
    role = (role or "").strip()
    if not role:
        return ""
    role = role.split("...")[0].strip()
    for a in sorted(aliases, key=len, reverse=True):
        # Allow mashups: "at boAtPulkit" — don't require a word boundary after the brand
        m = re.search(rf"(.{{0,90}}?\bat\s+{re.escape(a)})", role, re.I)
        if m:
            return m.group(1).strip()[:100]
        m = re.search(rf"(.{{0,90}}?@{re.escape(a)})", role, re.I)
        if m:
            return m.group(1).strip()[:100]
        m = re.search(rf"(.{{0,90}}?\b{re.escape(a)}\b)", role, re.I)
        if m:
            end = m.end()
            tail = role[end:]
            stop = re.search(r"[A-Z][a-z]+\s+[A-Z][a-z]+", tail)
            if stop:
                return role[: end + stop.start()].strip()[:100]
            return role[:end].strip()[:100]
    m = re.search(r"^(.*?)(?=[A-Z][a-z]+\s+[A-Z][a-z]+)", role)
    if m and len(m.group(1).strip()) > 8:
        return m.group(1).strip()[:100]
    return role[:100]


def _employer_segment_matches(title: str, aliases: list[str]) -> bool:
    m = re.search(r"\bat\s+(.+)$", title, re.I)
    if m and _text_matches_brand(m.group(1), aliases):
        return True
    m = re.search(r"@\s*([A-Za-z0-9 &._-]{2,40})", title)
    if m and _text_matches_brand(m.group(1), aliases):
        return True
    parts = [p.strip() for p in re.split(r"\s[-–—]\s", title) if p.strip()]
    for seg in parts[1:]:
        if _text_matches_brand(seg, aliases):
            return True
    return _text_matches_brand(title, aliases)


def _text_matches_brand(text: str, aliases: list[str]) -> bool:
    t = (text or "").lower()
    if not t:
        return False
    for a in aliases:
        al = a.lower()
        if len(al) >= 4 and al in t:
            return True
        if len(al) >= 3 and re.search(rf"\b{re.escape(al)}\b", t):
            return True
    return False


def _has_role_signal(text: str) -> bool:
    t = (text or "").lower()
    return any(w in t for w in _ROLE_WORDS)


def _infer_pattern(site_emails: list[dict[str, str]], domain: str) -> str:
    """Infer {first}.{last} vs {first}{last} from personal emails on the site."""
    _ = domain
    for e in site_emails:
        if e["kind"] != "personal":
            continue
        local = e["email"].split("@")[0]
        if "." in local:
            return "{first}.{last}"
        if "_" in local:
            return "{first}_{last}"
    return "{first}.{last}"


def _email_for_person(
    full_name: str,
    domain: str,
    site_emails: list[dict[str, str]],
    pattern: str,
) -> tuple[str, str]:
    if not domain:
        return "", ""
    parts = full_name.split()
    if not parts:
        return "", ""
    first, last = parts[0], parts[-1] if len(parts) > 1 else parts[0]

    # Exact personal email already on site?
    first_l = re.sub(r"[^a-z]", "", first.lower())
    last_l = re.sub(r"[^a-z]", "", last.lower())
    for e in site_emails:
        local = e["email"].split("@")[0].lower()
        if first_l and first_l in local and (not last_l or last_l in local):
            return e["email"], "site"

    guess = guess_corporate_email(first, last, domain)
    # Override pattern preference
    if pattern == "{first}{last}" and first_l and last_l:
        return f"{first_l}{last_l}@{domain}", "guessed"
    if pattern == "{first}_{last}" and first_l and last_l:
        return f"{first_l}_{last_l}@{domain}", "guessed"
    return guess.email, "guessed"
