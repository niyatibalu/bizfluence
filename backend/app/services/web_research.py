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
    other_links the user entered, plus deep fetches (YouTube RSS, page meta, link-in-bio).
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

    # --- Deep fetches on their own channels (primary signal) ---
    yt_dossier = _youtube_dossier(yt) if yt else {}
    ig_dossier = _instagram_dossier(handle, ig) if (handle or ig) else {}
    li_dossier = _linkedin_dossier(li) if li else {}
    other_dossier = _other_links_dossier(other_urls) if other_urls else {}

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
            queries.append(f"site:youtube.com {yt_path} review OR haul OR routine OR collab")
        queries.append(f'"{_normalize_url(yt)}"')
    if li:
        queries.append(f'"{_normalize_url(li)}"')
        path = _linkedin_path(li)
        if path:
            queries.append(f"site:linkedin.com/{path}")
    for u in other_urls[:3]:
        queries.append(f'"{_normalize_url(u)}"')

    all_hits: list[dict[str, str]] = []
    for q in queries[:8]:
        if not q.strip():
            continue
        all_hits.extend(web_search(q, max_results=5))

    # Direct page fetch for the links they gave (titles/snippets from THEIR pages)
    page_notes = _fetch_profile_pages(
        [u for u in [ig and _instagram_canonical(handle, ig), yt, li, *other_urls] if u]
    )
    hits = _filter_creator_hits(_real_hits(all_hits), allowed, handle)
    summary = _creator_summary_from_links(
        profile,
        handle,
        hits,
        page_notes,
        yt_dossier=yt_dossier,
        ig_dossier=ig_dossier,
        li_dossier=li_dossier,
        other_dossier=other_dossier,
    )

    polished = generate_text(
        system=(
            "Rewrite this creator profile research into 4-7 clear sentences for an influencer manager. "
            "ONLY use facts from the linked Instagram/YouTube/LinkedIn/other pages and listed videos. "
            "Call out content themes if video titles suggest them. "
            "Do not invent other creators or AI influencers. Plain English. No invented follower counts."
        ),
        user=summary,
        fallback=summary,
    )
    if polished and "search_error" not in polished.lower() and len(polished) > 40:
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
        f'"{name}" collab OR "brand ambassador" OR seeding India',
    ]
    hits: list[dict[str, str]] = []
    for q in queries[:5]:
        hits.extend(web_search(q, max_results=6))
    hits = _filter_brand_hits(name, domain, _real_hits(hits))

    site_notes = _fetch_brand_site(domain) if domain else []
    summary = _brand_summary_from_hits(company, hits, site_notes=site_notes)
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
    yt_dossier: dict | None = None,
    ig_dossier: dict | None = None,
    li_dossier: dict | None = None,
    other_dossier: dict | None = None,
) -> str:
    yt_dossier = yt_dossier or {}
    ig_dossier = ig_dossier or {}
    li_dossier = li_dossier or {}
    other_dossier = other_dossier or {}

    niche = profile.niche or "content"
    audience_bits = [
        p
        for p in [
            (profile.audience_size or "").strip(),
            (profile.audience_geo or "").strip(),
            (getattr(profile, "audience_description", "") or "").strip(),
        ]
        if p
    ]
    audience = " · ".join(audience_bits) if audience_bits else "India"

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
    parts.append(f"This creator works in {niche} for an audience of {audience}.")
    if platforms:
        parts.append("Research scoped to these linked channels only: " + ", ".join(platforms) + ".")

    bio = _polish_fragment(profile.bio or "")
    if bio:
        parts.append(f"Bio (from profile form): {bio}")
    goals = _polish_fragment(getattr(profile, "collab_goals", "") or "")
    if goals:
        parts.append(f"Collab goals: {goals}")
    exclusions = (getattr(profile, "exclusions", "") or "").strip()
    if exclusions:
        parts.append(f"Hard no-gos: {exclusions}.")

    # YouTube depth
    if yt_dossier.get("channel_title") or yt_dossier.get("videos"):
        parts.append("YouTube channel signals:")
        if yt_dossier.get("channel_title"):
            parts.append(f"• Channel: {yt_dossier['channel_title']}")
        if yt_dossier.get("description"):
            parts.append(f"• About: {yt_dossier['description'][:220]}")
        videos = yt_dossier.get("videos") or []
        if videos:
            parts.append("• Recent videos:")
            for title in videos[:8]:
                parts.append(f"  – {title}")
        themes = yt_dossier.get("themes") or []
        if themes:
            parts.append("• Content themes from titles: " + ", ".join(themes[:6]) + ".")

    # Instagram
    if ig_dossier.get("title") or ig_dossier.get("description") or ig_dossier.get("posts"):
        parts.append("Instagram signals:")
        if ig_dossier.get("title"):
            parts.append(f"• Profile title: {ig_dossier['title']}")
        if ig_dossier.get("description"):
            parts.append(f"• Public blurb: {ig_dossier['description'][:200]}")
        for p in (ig_dossier.get("posts") or [])[:5]:
            parts.append(f"• Indexed post/reel: {p}")
        if ig_dossier.get("note"):
            parts.append(f"• {ig_dossier['note']}")

    # LinkedIn
    if li_dossier.get("title") or li_dossier.get("description"):
        parts.append("LinkedIn signals:")
        if li_dossier.get("title"):
            parts.append(f"• {li_dossier['title']}")
        if li_dossier.get("description"):
            parts.append(f"• {li_dossier['description'][:200]}")

    # Link-in-bio / other
    if other_dossier.get("links") or other_dossier.get("blurb"):
        parts.append("From other linked pages (Linktree / site):")
        if other_dossier.get("blurb"):
            parts.append(f"• {other_dossier['blurb'][:200]}")
        for link in (other_dossier.get("links") or [])[:6]:
            parts.append(f"• Outbound: {link}")

    if page_notes:
        parts.append("Linked page titles / meta:")
        for p in page_notes[:4]:
            title = (p.get("title") or "").strip()
            snippet = (p.get("body") or "").strip()[:140]
            line = f"• {title or p.get('href', '')}"
            if snippet:
                line += f" — {snippet}"
            parts.append(line)

    if hits:
        # Prefer channel dossiers; keep indexed hits short (DDG often mashes titles)
        parts.append("Indexed pages matching their handles:")
        for h in hits[:3 if (yt_dossier.get("videos") or ig_dossier.get("posts")) else 5]:
            title = re.split(r"(?<=- YouTube)", (h.get("title") or ""), maxsplit=1)[0].strip()
            title = re.sub(r"\s+", " ", title)[:120]
            if not title:
                continue
            snippet = (h.get("body") or "")[:100]
            parts.append(f"• {title}" + (f" — {snippet}" if snippet else ""))
    elif not (yt_dossier or ig_dossier or li_dossier or page_notes):
        parts.append(
            "Could not pull rich public snippets from these links yet (pages may be private or blocked). "
            "Suggestions still use the niche, audience, and links you entered."
        )

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


def _extract_youtube_channel_id(html: str) -> str:
    """Channel-owned UC id only — never recommended-video channelIds."""
    for pattern in (
        # Official channel package (rssUrl / externalId live deep in the page JSON)
        r'"rssUrl"\s*:\s*"https://www\.youtube\.com/feeds/videos\.xml\?channel_id=(UC[\w-]{22})"',
        r'"externalId"\s*:\s*"(UC[\w-]{22})"',
        r'<link[^>]+href="https://www\.youtube\.com/feeds/videos\.xml\?channel_id=(UC[\w-]{22})"',
        r'itemprop="channelId"\s+content="(UC[\w-]{22})"',
        r'"browseId"\s*:\s*"(UC[\w-]{22})"',
    ):
        m = re.search(pattern, html, re.I)
        if m:
            return m.group(1)
    return ""


def _youtube_dossier(yt_url: str) -> dict[str, Any]:
    """Pull channel meta + recent video titles via public YouTube RSS (no API key)."""
    out: dict[str, Any] = {"videos": [], "themes": []}
    try:
        import httpx
    except ImportError:
        return out

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }
    url = _normalize_url(yt_url)
    handle = ""
    hm = re.search(r"youtube\.com/@([A-Za-z0-9._-]+)", url)
    if hm:
        handle = hm.group(1)
    channel_id = ""
    m = re.search(r"youtube\.com/channel/(UC[\w-]{22})", url)
    if m:
        channel_id = m.group(1)

    try:
        with httpx.Client(timeout=18.0, follow_redirects=True, headers=headers) as client:
            html = ""
            if not channel_id or handle:
                r = client.get(url if "youtube.com" in url else f"https://www.youtube.com/@{handle}")
                if r.status_code < 400:
                    # channelMetadataRenderer / rssUrl sit ~2MB down the page — do not truncate
                    html = r.text
            if html:
                head = html[:80_000]
                tm = re.search(r"<title[^>]*>(.*?)</title>", head, re.I | re.S)
                if tm:
                    out["channel_title"] = (
                        re.sub(r"\s+", " ", tm.group(1)).replace("- YouTube", "").strip()
                    )
                if not out.get("channel_title"):
                    ctm = re.search(
                        r'"channelMetadataRenderer"\s*:\s*\{\s*"title"\s*:\s*"((?:\\.|[^"\\])+)"',
                        html,
                    )
                    if ctm:
                        out["channel_title"] = (
                            bytes(ctm.group(1), "utf-8")
                            .decode("unicode_escape", errors="ignore")
                            .strip()
                        )
                dm = re.search(
                    r'<meta[^>]+(?:name|property)=["\'](?:description|og:description)["\'][^>]+content=["\']([^"\']+)',
                    head,
                    re.I,
                )
                if dm:
                    out["description"] = re.sub(r"\s+", " ", dm.group(1)).strip()[:400]
                else:
                    # channelMetadataRenderer description (JSON-escaped)
                    jm = re.search(
                        r'"channelMetadataRenderer"\s*:\s*\{[^{}]{0,200}?"description"\s*:\s*"((?:\\.|[^"\\]){20,800})"',
                        html,
                    )
                    if jm:
                        desc = bytes(jm.group(1), "utf-8").decode("unicode_escape", errors="ignore")
                        out["description"] = re.sub(r"\s+", " ", desc).strip()[:400]

                if not channel_id:
                    channel_id = _extract_youtube_channel_id(html)

            if channel_id:
                out["channel_id"] = channel_id
                fr = client.get(
                    f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
                )
                if fr.status_code < 400:
                    xml = fr.text
                    titles = re.findall(r"<media:title[^>]*>(.*?)</media:title>", xml)
                    if not titles:
                        titles = re.findall(r"<title>(.*?)</title>", xml)[1:]
                    cleaned = []
                    channel_title_l = (out.get("channel_title") or "").lower()
                    for t in titles:
                        t = re.sub(r"<[^>]+>", "", t)
                        t = (
                            t.replace("&amp;", "&")
                            .replace("&quot;", '"')
                            .replace("&#39;", "'")
                            .strip()
                        )
                        if not t or t.lower() == channel_title_l:
                            continue
                        if t.lower() in {"youtube", "home", "videos"}:
                            continue
                        cleaned.append(t)
                    if cleaned:
                        out["videos"] = cleaned[:10]
                        out["themes"] = _themes_from_titles(cleaned)

            # Fallback: indexed uploads for this @handle only (still link-scoped)
            if handle and len(out.get("videos") or []) < 3:
                hits = _real_hits(
                    web_search(f"site:youtube.com/@{handle}", max_results=8)
                )
                extra = []
                for h in hits:
                    href = (h.get("href") or "").lower()
                    title = (h.get("title") or "").replace(" - YouTube", "").strip()
                    if "youtube.com" not in href or not title:
                        continue
                    if title.lower() in {"youtube", handle.lower(), f"@{handle.lower()}"}:
                        continue
                    if f"/@{handle.lower()}" in href or "/watch" in href or "/shorts/" in href:
                        extra.append(title)
                if extra:
                    seen = set(out.get("videos") or [])
                    for t in extra:
                        if t not in seen:
                            (out.setdefault("videos", [])).append(t)
                            seen.add(t)
                    out["videos"] = (out.get("videos") or [])[:10]
                    out["themes"] = _themes_from_titles(out["videos"])
    except Exception:  # noqa: BLE001
        pass
    return out


def _instagram_dossier(handle: str, ig_url: str) -> dict[str, Any]:
    """Best-effort IG public signals (login walls are common)."""
    out: dict[str, Any] = {"posts": []}
    canonical = _instagram_canonical(handle, ig_url)
    pages = _fetch_profile_pages([canonical])
    if pages:
        out["title"] = pages[0].get("title") or ""
        out["description"] = pages[0].get("body") or ""
        if "login" in (out["title"] + out["description"]).lower() or not out["description"]:
            out["note"] = (
                "Instagram often hides the full profile behind a login wall; "
                "using indexed public posts when available."
            )
    if handle:
        hits = _real_hits(web_search(f"site:instagram.com/{handle} reel OR post", max_results=8))
        for h in hits[:6]:
            href = (h.get("href") or "").lower()
            if f"instagram.com/{handle.lower()}" in href:
                title = (h.get("title") or "").strip()
                if title:
                    out["posts"].append(title[:120])
    return out


def _linkedin_dossier(li_url: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    pages = _fetch_profile_pages([li_url])
    if pages:
        out["title"] = pages[0].get("title") or ""
        out["description"] = pages[0].get("body") or ""
    path = _linkedin_path(li_url)
    if path:
        hits = _real_hits(web_search(f"site:linkedin.com/{path}", max_results=4))
        if hits and not out.get("description"):
            out["description"] = (hits[0].get("body") or "")[:200]
            if not out.get("title"):
                out["title"] = hits[0].get("title") or ""
    return out


def _other_links_dossier(urls: list[str]) -> dict[str, Any]:
    """Parse Linktree / Beacons / personal sites for bio text and outbound links."""
    out: dict[str, Any] = {"links": [], "blurb": ""}
    try:
        import httpx
    except ImportError:
        return out

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }
    found: list[str] = []
    blurbs: list[str] = []
    with httpx.Client(timeout=8.0, follow_redirects=True, headers=headers) as client:
        for url in urls[:4]:
            try:
                r = client.get(_normalize_url(url))
                if r.status_code >= 400:
                    continue
                html = r.text[:120_000]
                dm = re.search(
                    r'<meta[^>]+(?:name|property)=["\'](?:description|og:description)["\'][^>]+content=["\']([^"\']+)',
                    html,
                    re.I,
                )
                if dm:
                    blurbs.append(re.sub(r"\s+", " ", dm.group(1)).strip())
                # Collect obvious outbound http links (skip trackers)
                for href in re.findall(r'href=["\'](https?://[^"\']+)["\']', html, re.I):
                    low = href.lower()
                    if any(
                        skip in low
                        for skip in (
                            "facebook.com",
                            "twitter.com",
                            "x.com",
                            "tiktok.com",
                            "googleapis",
                            "gstatic",
                            "schema.org",
                            "w3.org",
                            "linktr.ee/s/",
                        )
                    ):
                        # still keep socials that are useful
                        if any(s in low for s in ("instagram.com", "youtube.com", "youtu.be", "linkedin.com")):
                            found.append(href.split("?")[0])
                        continue
                    if "linktr.ee" in low or "beacons.ai" in low or "bio.site" in low:
                        continue
                    found.append(href.split("?")[0])
            except Exception:  # noqa: BLE001
                continue
    # dedupe
    seen: set[str] = set()
    for link in found:
        if link not in seen:
            seen.add(link)
            out["links"].append(link)
        if len(out["links"]) >= 8:
            break
    if blurbs:
        out["blurb"] = blurbs[0]
    return out


def _themes_from_titles(titles: list[str]) -> list[str]:
    """Offline theme guess from repeated words in video titles."""
    stop = {
        "the", "a", "an", "and", "or", "to", "for", "of", "in", "on", "with", "my", "your",
        "how", "i", "me", "we", "you", "is", "at", "this", "that", "from", "vs", "ep", "part",
        "full", "video", "official", "new", "best", "top", "india", "hindi", "day", "vlog",
    }
    counts: dict[str, int] = {}
    for title in titles:
        words = re.findall(r"[A-Za-z]{4,}", title.lower())
        for w in words:
            if w in stop:
                continue
            counts[w] = counts.get(w, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [w for w, n in ranked if n >= 2][:6] or [w for w, _ in ranked[:4]]


def _fetch_brand_site(domain: str) -> list[dict[str, str]]:
    if not domain:
        return []
    host = _clean_domain(domain)
    return _fetch_profile_pages([f"https://{host}", f"https://www.{host}"])


def _unescape_html(text: str) -> str:
    return (
        (text or "")
        .replace("&amp;", "&")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&nbsp;", " ")
    )


def _fetch_profile_pages(urls: list[str]) -> list[dict[str, str]]:
    """Best-effort GET of creator's own URLs for title/meta text (no name Google)."""
    notes: list[dict[str, str]] = []
    try:
        import httpx
    except ImportError:
        return notes

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }
    seen_hosts: set[str] = set()
    with httpx.Client(timeout=10.0, follow_redirects=True, headers=headers) as client:
        for url in urls[:6]:
            nu = _normalize_url(url)
            host = re.sub(r"^https?://(?:www\.)?", "", nu).split("/")[0]
            if host in seen_hosts and "youtube" not in host:
                continue
            seen_hosts.add(host)
            try:
                r = client.get(nu)
                if r.status_code >= 400:
                    notes.append(
                        {
                            "title": f"Linked page ({r.status_code})",
                            "href": str(r.url),
                            "body": "Page did not return public HTML (common for Instagram/LinkedIn login walls).",
                        }
                    )
                    continue
                html = r.text[:100_000]
                title = ""
                m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
                if m:
                    title = _unescape_html(re.sub(r"\s+", " ", m.group(1)).strip())
                desc = ""
                for pattern in (
                    r'<meta[^>]+(?:name|property)=["\'](?:description|og:description|og:title)["\'][^>]+content=["\']([^"\']+)',
                    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:name|property)=["\'](?:description|og:description)["\']',
                ):
                    m = re.search(pattern, html, re.I)
                    if m:
                        desc = _unescape_html(re.sub(r"\s+", " ", m.group(1)).strip())
                        break
                # Lightweight about/h1 sniff for brand sites
                if not desc:
                    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
                    if h1:
                        desc = re.sub(r"<[^>]+>", "", h1.group(1))
                        desc = _unescape_html(re.sub(r"\s+", " ", desc).strip())[:180]
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


def _brand_summary_from_hits(
    company: Company, hits: list[dict[str, str]], site_notes: list[dict[str, str]] | None = None
) -> str:
    name = company.name
    domain = company.domain or "unknown site"
    category = getattr(company, "category", None) or "consumer"
    parts: list[str] = [
        f"{name} ({domain}) is listed as an India-market {category} brand."
    ]
    if getattr(company, "fit_rationale", None):
        parts.append(_polish_fragment(company.fit_rationale))

    if site_notes:
        parts.append("From their website:")
        for p in site_notes[:2]:
            title = (p.get("title") or "").strip()
            body = (p.get("body") or "").strip()[:180]
            if title:
                parts.append(f"• {title}")
            if body:
                parts.append(f"• {body}")

    influencer_hits = [
        h
        for h in hits
        if (h.get("title") or "").strip()
        and re.search(
            r"influencer|creator|ugc|ambassador|collab|campaign|seeding",
            f"{h.get('title','')} {h.get('body','')}",
            re.I,
        )
    ]
    risk_hits = [
        h
        for h in hits
        if (h.get("title") or "").strip()
        and re.search(
            r"controvers|backlash|scam|complaint|boycott|lawsuit",
            f"{h.get('title','')} {h.get('body','')}",
            re.I,
        )
    ]

    if influencer_hits:
        parts.append("Creator-marketing signals found online:")
        for h in influencer_hits[:4]:
            parts.append(f"• {h['title']}")
    else:
        parts.append(
            "This search did not clearly show recent influencer campaigns. "
            "Ask them about their current creator program."
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
