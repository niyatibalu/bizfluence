"""Free web research via DuckDuckGo (India-focused). Builds readable summaries without an LLM."""

from __future__ import annotations

import re
from typing import Any

from app.models import Company, CreatorProfile
from app.services.llm import generate_json, generate_text


def web_search(query: str, max_results: int = 8) -> list[dict[str, str]]:
    try:
        from ddgs import DDGS

        results: list[dict[str, str]] = []
        with DDGS() as ddgs:
            for item in ddgs.text(query, max_results=max_results, region="in-en"):
                title = (item.get("title") or "").strip()
                href = (item.get("href") or "").strip()
                body = (item.get("body") or "").strip()
                if not title and not body:
                    continue
                results.append({"title": title, "href": href, "body": body})
        return results
    except Exception as exc:  # noqa: BLE001
        return [{"title": "search_error", "href": "", "body": str(exc)}]


def _real_hits(hits: list[dict[str, str]]) -> list[dict[str, str]]:
    return [h for h in hits if h.get("title") and h.get("title") != "search_error"]


def format_hits(hits: list[dict[str, str]], limit: int = 6) -> str:
    lines: list[str] = []
    for h in _real_hits(hits)[:limit]:
        lines.append(f"- {h['title']}: {h.get('body', '')} ({h.get('href', '')})")
    return "\n".join(lines) if lines else ""


def research_creator(profile: CreatorProfile | None, force: bool = False) -> str:
    """Research ONLY from the creator's provided social/profile links.

    Never open-web search by display name or niche alone — that confused similar
    names (e.g. Nayna/Nayra vs "Naina AI"). Scope = Instagram / YouTube / LinkedIn /
    other_links the user entered, plus page fetches for those URLs.
    """
    if profile is None:
        return ""
    if profile.research_notes and not force:
        return profile.research_notes

    ig = (getattr(profile, "instagram_url", "") or "").strip()
    yt = (getattr(profile, "youtube_url", "") or "").strip()
    li = (getattr(profile, "linkedin_url", "") or "").strip()
    other = (getattr(profile, "other_links", "") or "").strip()
    handle = _ig_handle(ig) if ig else ""
    other_urls = _split_links(other)
    allowed = _creator_allowed_hosts(handle, ig, yt, li, other_urls)

    if not any([ig, yt, li, other_urls]):
        summary = (
            "No Instagram, YouTube, LinkedIn, or other profile links were provided. "
            "Add the creator's real social URLs and run research again — "
            "Bizfluence only looks at those pages, not random people with similar names."
        )
        profile.research_notes = summary
        return summary

    # Link-scoped search only (site: / exact URL) — never bare name/niche Google
    queries: list[str] = []
    if handle:
        queries.append(f"site:instagram.com/{handle}")
        queries.append(f"site:instagram.com/{handle} reel OR post OR video")
    elif ig:
        queries.append(f'"{_normalize_url(ig)}"')
    if yt:
        yt_path = _yt_channel_hint(yt)
        if yt_path:
            queries.append(f"site:youtube.com {yt_path}")
        queries.append(f'"{_normalize_url(yt)}"')
    if li:
        queries.append(f'"{_normalize_url(li)}"')
        queries.append(f"site:linkedin.com {_linkedin_path(li)}")
    for u in other_urls[:3]:
        queries.append(f'"{_normalize_url(u)}"')

    all_hits: list[dict[str, str]] = []
    for q in queries[:6]:
        if not q.strip():
            continue
        all_hits.extend(web_search(q, max_results=5))

    # Direct page fetch for the links they gave (titles/snippets from THEIR pages)
    page_notes = _fetch_profile_pages(
        [u for u in [ig and _instagram_canonical(handle, ig), yt, li, *other_urls] if u]
    )
    hits = _filter_creator_hits(_real_hits(all_hits), allowed, handle)
    summary = _creator_summary_from_links(profile, handle, hits, page_notes)

    polished = generate_text(
        system=(
            "Rewrite this creator profile research into 3-5 clear sentences for an influencer manager. "
            "ONLY use facts from the linked Instagram/YouTube/LinkedIn/other pages provided. "
            "Do not invent other creators or AI influencers. Plain English. No invented follower counts."
        ),
        user=summary,
        fallback=summary,
    )
    if polished and "search_error" not in polished.lower() and len(polished) > 40:
        # Reject polish that invents unrelated entities (common with name collisions)
        if not _polish_drifts_off_links(polished, handle, ig, yt, li):
            summary = polished.strip()

    profile.research_notes = summary
    return summary

def research_brand(company: Company | None, force: bool = False) -> str:
    if company is None:
        return ""
    cached = getattr(company, "research_notes", "") or ""
    if cached and not force:
        return cached

    name = company.name
    domain = company.domain or ""
    queries = [
        f'"{name}" India brand',
        f'"{name}" influencer marketing OR creator OR UGC OR brand ambassador India',
        f'"{name}" review OR controversy OR backlash India',
        f"{domain} official" if domain else f"{name} official website India",
    ]
    hits: list[dict[str, str]] = []
    for q in queries[:4]:
        hits.extend(web_search(q, max_results=6))
    hits = _filter_brand_hits(name, domain, _real_hits(hits))

    summary = _brand_summary_from_hits(company, hits)
    polished = generate_text(
        system=(
            "Rewrite this brand research into 3-5 clear sentences for an influencer manager in India. "
            "Cover: what they sell, whether they work with creators, any risks. Plain English. No jargon."
        ),
        user=summary,
        fallback=summary,
    )
    if polished and len(polished) > 40 and "public research thin" not in polished.lower():
        summary = polished.strip()

    company.research_notes = summary
    return summary


def _filter_brand_hits(name: str, domain: str, hits: list[dict[str, str]]) -> list[dict[str, str]]:
    """Keep only hits that actually seem about this brand."""
    name_l = name.lower().strip()
    tokens = [t for t in re.split(r"\s+", name_l) if len(t) > 1]
    kept: list[dict[str, str]] = []
    for h in hits:
        blob = f"{h.get('title', '')} {h.get('body', '')} {h.get('href', '')}".lower()
        if domain and domain.lower().split("/")[0] in blob:
            kept.append(h)
            continue
        if name_l and name_l in blob:
            kept.append(h)
            continue
        if tokens and all(t in blob for t in tokens):
            kept.append(h)
            continue
    return kept


def search_india_brands(niche: str, field: str | None, extra_hints: str, creator_context: str) -> list[dict[str, Any]]:
    focus = field or niche or "consumer brand"
    queries = [
        f"best {focus} brands India D2C 2025 2026",
        f"top {focus} D2C brands India influencer",
        f"{focus} brands India brand ambassador campaign",
        f"{extra_hints} {focus} India brands" if extra_hints else f"popular {focus} Indian brands Instagram",
    ]
    hits: list[dict[str, str]] = []
    for q in queries[:4]:
        hits.extend(web_search(q, max_results=8))
    raw = format_hits(hits, limit=20)

    # Also extract brand-like names from titles heuristically when LLM unavailable
    heuristic = _extract_brands_from_titles(hits, focus, niche)

    data = generate_json(
        system=(
            "Extract REAL India-market brands from the search snippets. "
            "Return JSON: {\"brands\":[{name,domain,category,fit_rationale,suggested_angle,priority_narrative}]} "
            "India only. 8-12 brands. fit_rationale must be one clear sentence."
        ),
        user=(
            f"Creator niche: {niche}\nField: {focus}\nHints: {extra_hints}\n"
            f"Creator research:\n{creator_context}\n\nSearch snippets:\n{raw or '(none)'}"
        ),
        fallback={"brands": heuristic},
    )
    brands = data.get("brands") or heuristic
    cleaned: list[dict[str, Any]] = []
    for b in brands:
        if not isinstance(b, dict) or not b.get("name"):
            continue
        cleaned.append(
            {
                "name": str(b.get("name", "")).strip(),
                "domain": _clean_domain(str(b.get("domain", ""))),
                "category": str(b.get("category", focus))[:128],
                "fit_rationale": str(b.get("fit_rationale") or f"India {focus} brand relevant to {niche or 'this creator'}."),
                "suggested_angle": str(b.get("suggested_angle") or f"Show the product in a real {niche or focus} routine."),
                "priority_narrative": str(b.get("priority_narrative") or "Found via India web search for creator-ready brands."),
            }
        )
    return cleaned


def _creator_summary_from_links(
    profile: CreatorProfile,
    handle: str,
    hits: list[dict[str, str]],
    page_notes: list[dict[str, str]],
) -> str:
    niche = profile.niche or "content"
    audience = " ".join(
        p for p in [(profile.audience_size or "").strip(), (profile.audience_geo or "India").strip()] if p
    )
    platforms = []
    if profile.instagram_url:
        platforms.append(f"Instagram (@{handle})" if handle else f"Instagram ({profile.instagram_url})")
    if profile.youtube_url:
        platforms.append(f"YouTube ({profile.youtube_url})")
    if profile.linkedin_url:
        platforms.append(f"LinkedIn ({profile.linkedin_url})")
    for u in _split_links(getattr(profile, "other_links", "") or ""):
        platforms.append(u)

    parts: list[str] = []
    parts.append(
        f"This creator works in {niche}"
        + (f" for an audience of {audience}" if audience else " for an India audience")
        + "."
    )
    if platforms:
        parts.append("Research is limited to these linked channels only: " + ", ".join(platforms) + ".")
    bio = _polish_fragment(profile.bio or "")
    if bio:
        parts.append(f"Profile form note (context only, not searched as a name): {bio}")

    if page_notes:
        parts.append("From their linked pages:")
        for p in page_notes[:5]:
            title = (p.get("title") or "").strip()
            snippet = (p.get("body") or "").strip()[:160]
            href = p.get("href") or ""
            line = f"• {title or href}"
            if snippet:
                line += f" — {snippet}"
            parts.append(line)

    if hits:
        parts.append("Indexed posts/pages that match their handles:")
        for h in hits[:5]:
            snippet = (h.get("body") or "")[:140]
            parts.append(f"• {h['title']}" + (f" — {snippet}" if snippet else ""))
    elif not page_notes:
        parts.append(
            "Could not pull public snippets from these links yet (pages may be private or blocked). "
            "Brand suggestions will still use the niche, audience, and links you entered — "
            "not other people with similar names."
        )
    else:
        parts.append("No extra indexed posts beyond the linked page titles above.")

    parts.append(
        "Note: Bizfluence does not Google the creator's display name, to avoid mixing them up "
        "with similarly named accounts (including AI influencers)."
    )
    return "\n".join(parts)


def _split_links(text: str) -> list[str]:
    parts = re.split(r"[\s,;]+", (text or "").strip())
    out: list[str] = []
    for p in parts:
        p = p.strip()
        if p.startswith("http://") or p.startswith("https://") or "." in p:
            if not p.startswith("http"):
                p = "https://" + p
            out.append(p)
    return out[:8]


def _normalize_url(url: str) -> str:
    u = (url or "").strip()
    if u.startswith("@"):
        return f"https://instagram.com/{u[1:]}"
    if not u.startswith("http"):
        if "instagram.com" in u or "youtube.com" in u or "youtu.be" in u or "linkedin.com" in u:
            return "https://" + u.lstrip("/")
        if "/" not in u and " " not in u:
            return f"https://instagram.com/{u.lstrip('@')}"
        return "https://" + u.lstrip("/")
    return u


def _instagram_canonical(handle: str, ig: str) -> str:
    if handle:
        return f"https://www.instagram.com/{handle}/"
    return _normalize_url(ig)


def _yt_channel_hint(url: str) -> str:
    u = url or ""
    m = re.search(r"youtube\.com/@([A-Za-z0-9._-]+)", u)
    if m:
        return f"@{m.group(1)}"
    m = re.search(r"youtube\.com/(?:channel|c|user)/([A-Za-z0-9._-]+)", u)
    if m:
        return m.group(1)
    m = re.search(r"youtu\.be/([A-Za-z0-9_-]+)", u)
    if m:
        return m.group(1)
    return ""


def _linkedin_path(url: str) -> str:
    m = re.search(r"linkedin\.com/(in|company)/([A-Za-z0-9_-]+)", url or "")
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    return ""


def _creator_allowed_hosts(
    handle: str, ig: str, yt: str, li: str, other_urls: list[str]
) -> set[str]:
    hosts: set[str] = set()
    if handle:
        hosts.add(f"instagram.com/{handle.lower()}")
    for u in [ig, yt, li, *other_urls]:
        if not u:
            continue
        nu = _normalize_url(u).lower()
        m = re.search(r"https?://(?:www\.)?([^/?#]+)", nu)
        if m:
            hosts.add(m.group(1).removeprefix("www."))
        # keep path tokens for IG/LI
        if "instagram.com/" in nu and handle:
            hosts.add(f"instagram.com/{handle.lower()}")
        if "linkedin.com/" in nu:
            path = _linkedin_path(nu)
            if path:
                hosts.add(f"linkedin.com/{path.lower()}")
        yt_h = _yt_channel_hint(nu)
        if yt_h:
            hosts.add(yt_h.lower())
    return hosts


def _filter_creator_hits(
    hits: list[dict[str, str]], allowed: set[str], handle: str
) -> list[dict[str, str]]:
    """Drop results about other people (e.g. Naina AI when researching @nayna)."""
    kept: list[dict[str, str]] = []
    handle_l = (handle or "").lower()
    for h in hits:
        href = (h.get("href") or "").lower()
        blob = f"{h.get('title', '')} {h.get('body', '')} {href}".lower()
        # hard reject known AI-influencer collision when handle is different
        if "naina ai" in blob or "ai human influencer" in blob or "ai influencer" in blob:
            if handle_l and handle_l not in ("naina", "nainaai"):
                continue
        ok = False
        for a in allowed:
            if a and a in href:
                ok = True
                break
            if a and a in blob and ("instagram.com" in href or "youtube.com" in href or "linkedin.com" in href or a in href):
                ok = True
                break
        if handle_l and f"instagram.com/{handle_l}" in href:
            ok = True
        if ok:
            kept.append(h)
    return kept


def _fetch_profile_pages(urls: list[str]) -> list[dict[str, str]]:
    """Best-effort GET of creator's own URLs for title/meta text (no name Google)."""
    notes: list[dict[str, str]] = []
    try:
        import httpx
    except ImportError:
        return notes

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; BizfluenceResearch/1.0; +https://bizfluence.local) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }
    with httpx.Client(timeout=8.0, follow_redirects=True, headers=headers) as client:
        for url in urls[:5]:
            try:
                r = client.get(_normalize_url(url))
                if r.status_code >= 400:
                    notes.append(
                        {
                            "title": f"Linked page ({r.status_code})",
                            "href": str(r.url),
                            "body": "Page did not return public HTML (common for Instagram login walls).",
                        }
                    )
                    continue
                html = r.text[:80_000]
                title = ""
                m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
                if m:
                    title = re.sub(r"\s+", " ", m.group(1)).strip()
                desc = ""
                m = re.search(
                    r'<meta[^>]+(?:name|property)=["\'](?:description|og:description)["\'][^>]+content=["\']([^"\']+)',
                    html,
                    re.I,
                )
                if not m:
                    m = re.search(
                        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:name|property)=["\'](?:description|og:description)["\']',
                        html,
                        re.I,
                    )
                if m:
                    desc = re.sub(r"\s+", " ", m.group(1)).strip()
                notes.append({"title": title or str(r.url), "href": str(r.url), "body": desc})
            except Exception as exc:  # noqa: BLE001
                notes.append(
                    {
                        "title": "Linked page (unreachable)",
                        "href": url,
                        "body": str(exc)[:120],
                    }
                )
    return notes


def _polish_drifts_off_links(text: str, handle: str, ig: str, yt: str, li: str) -> bool:
    """True if Gemini polish likely invented an unrelated similarly-named creator."""
    low = text.lower()
    if "naina ai" in low or "ai human influencer" in low:
        h = (handle or "").lower()
        if h and h not in ("naina", "nainaai"):
            return True
    # If polish mentions a different @handle than ours
    mentioned = re.findall(r"@([A-Za-z0-9._]+)", text)
    if handle and mentioned:
        ours = handle.lower()
        foreign = [m for m in mentioned if m.lower() != ours and m.lower() not in {"instagram", "youtube"}]
        if foreign and ours not in {m.lower() for m in mentioned}:
            return True
    return False


def _brand_summary_from_hits(company: Company, hits: list[dict[str, str]]) -> str:
    name = company.name
    domain = company.domain or "unknown site"
    category = company.category or "consumer"
    parts: list[str] = [
        f"{name} ({domain}) is listed as an India-market {category} brand."
    ]
    if company.fit_rationale:
        parts.append(_polish_fragment(company.fit_rationale))

    influencer_hits = [
        h
        for h in hits
        if re.search(r"influencer|creator|ugc|ambassador|collab|campaign", f"{h.get('title','')} {h.get('body','')}", re.I)
    ]
    risk_hits = [
        h
        for h in hits
        if re.search(r"controvers|backlash|scam|complaint|boycott|lawsuit", f"{h.get('title','')} {h.get('body','')}", re.I)
    ]

    if influencer_hits:
        parts.append("Creator-marketing signals found online:")
        for h in influencer_hits[:3]:
            parts.append(f"• {h['title']}")
    else:
        parts.append(
            "This search did not clearly show recent influencer campaigns. "
            "That does not mean they never work with creators — it means you should ask them about their current program."
        )

    if risk_hits:
        parts.append("Possible reputation flags to double-check:")
        for h in risk_hits[:3]:
            parts.append(f"• {h['title']}")
    else:
        parts.append("No obvious controversy headlines showed up in this quick search.")

    if hits:
        parts.append("Sources glanced:")
        for h in hits[:4]:
            parts.append(f"• {h['title']} — {h.get('href','')}")
    return "\n".join(parts)


def _extract_brands_from_titles(hits: list[dict[str, str]], focus: str, niche: str) -> list[dict[str, Any]]:
    """Pull candidate brand names from listicle titles when Gemini is unavailable."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for h in _real_hits(hits):
        title = h.get("title") or ""
        # "Top 25 D2C Skincare Brands in India" — not a brand itself
        if re.search(r"\b(top|best|list|brands in india)\b", title, re.I) and " vs " not in title.lower():
            # try to pull from body: "Mamaearth, Minimalist, ..."
            body = h.get("body") or ""
            for name in re.findall(r"\b([A-Z][A-Za-z0-9&'.-]{2,}(?:\s+[A-Z][A-Za-z0-9&'.-]{2,}){0,2})\b", body):
                if name.lower() in seen:
                    continue
                if name.lower() in {"india", "indian", "discover", "explore", "brands", "d2c"}:
                    continue
                seen.add(name.lower())
                out.append(
                    {
                        "name": name,
                        "domain": "",
                        "category": focus,
        "fit_rationale": f"Mentioned in India {focus} coverage; relevant for a {niche or 'this'} creator.",
                        "suggested_angle": f"Feature the product inside a real {niche or focus} story this creator already makes.",
                        "priority_narrative": f"Surfaced from: {title[:80]}",
                    }
                )
                if len(out) >= 10:
                    return out
    return out


def _polish_fragment(text: str) -> str:
    """Turn a partial bio/note into one clean sentence, or empty if unusable."""
    t = " ".join((text or "").strip().split())
    if len(t) < 12:
        return ""
    # Drop obvious placeholder junk
    if t.lower() in {"n/a", "na", "none", "test", "asdf"}:
        return ""
    if t[0].islower():
        t = t[0].upper() + t[1:]
    if t[-1] not in ".!?":
        t += "."
    return t


def _ig_handle(url: str) -> str:
    m = re.search(r"instagram\.com/([A-Za-z0-9._]+)", url)
    if m:
        h = m.group(1).strip("/")
        if h.lower() in {"p", "reel", "reels", "stories", "explore"}:
            return ""
        return h
    if url.startswith("@"):
        return url[1:].strip()
    if "/" not in url and " " not in url:
        return url.lstrip("@").strip()
    return ""


def _clean_domain(domain: str) -> str:
    d = domain.lower().strip()
    d = re.sub(r"^https?://", "", d)
    d = re.sub(r"^www\.", "", d)
    return d.split("/")[0][:255]
