"""Enrich a manually added company with creator-tailored fit copy + light web research."""

from __future__ import annotations

from app.models import Company, CreatorProfile
from app.services.llm import generate_json
from app.services.web_research import research_brand, web_search, _real_hits, _filter_brand_hits


def enrich_company(company: Company, profile: CreatorProfile | None, force: bool = False) -> Company:
    niche = (profile.niche if profile else "") or "creator content"
    audience = ""
    if profile:
        audience = f"{profile.audience_size or ''} {profile.audience_geo or 'India'}".strip()

    # Always gather brand research notes
    if force or not (company.research_notes or "").strip():
        research_brand(company, force=force)

    needs_copy = force or not (company.fit_rationale or "").strip() or company.fit_rationale.startswith("Manually added")

    if needs_copy:
        hits = _filter_brand_hits(
            company.name,
            company.domain or "",
            _real_hits(
                web_search(f'"{company.name}" India brand D2C OR startup', 5)
                + web_search(f'"{company.name}" influencer OR creator India', 4)
            ),
        )
        hit_lines = "\n".join(f"- {h['title']}: {h.get('body','')[:120]}" for h in hits[:5])

        fallback = {
            "fit_rationale": (
                f"{company.name} is an India-market brand that could fit a {niche} creator"
                f"{f' with an audience of {audience}' if audience else ''} — "
                f"worth pitching if their products match your content."
            ),
            "suggested_angle": f"Show {company.name} inside a real {niche} routine your audience already trusts.",
            "priority_narrative": "User-added brand — researched for fit with your niche.",
            "category": company.category or niche.split()[0] if niche else "brand",
        }

        data = generate_json(
            system=(
                "You help micro/mid-tier Indian influencers. Write tailored company card copy. "
                "Return JSON: {fit_rationale, suggested_angle, priority_narrative, category}. "
                "fit_rationale: 1-2 clear sentences about why THIS creator might pitch THIS brand. "
                "Do not invent fake awards."
            ),
            user=(
                f"Creator niche: {niche}\nAudience: {audience}\n"
                f"Brand: {company.name}\nDomain: {company.domain}\n"
                f"Brand research:\n{company.research_notes or '(none)'}\n"
                f"Web hits:\n{hit_lines or '(none)'}"
            ),
            fallback=fallback,
        )
        company.fit_rationale = str(data.get("fit_rationale") or fallback["fit_rationale"])
        company.suggested_angle = str(data.get("suggested_angle") or fallback["suggested_angle"])
        company.priority_narrative = str(data.get("priority_narrative") or fallback["priority_narrative"])
        if data.get("category"):
            company.category = str(data["category"])[:128]

    return company
