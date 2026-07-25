"""Hunter.io Domain Search — people emails tied to a company domain."""

from __future__ import annotations

from typing import Any

import httpx

from app.config import get_settings
from app.services.web_research import _clean_domain

# Generic inboxes that are useful for creator outreach when no named people exist
_USEFUL_GENERICS = (
    "influencer",
    "influencers",
    "creator",
    "creators",
    "partnership",
    "partnerships",
    "collab",
    "collaborations",
    "marketing",
    "brand",
    "pr",
    "press",
    "hello",
    "hi",
    "care",
    "support",
    "contact",
    "info",
)


def hunter_configured() -> bool:
    get_settings.cache_clear()
    return bool((get_settings().hunter_api_key or "").strip())


def domain_email_count(domain: str) -> dict[str, Any]:
    """Free Hunter call — how many emails they index for this domain."""
    key = (get_settings().hunter_api_key or "").strip()
    host = _clean_domain(domain)
    if not key or not host:
        return {}
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(
                "https://api.hunter.io/v2/email-count",
                params={"domain": host, "api_key": key},
            )
            if r.status_code >= 400:
                return {}
            return (r.json().get("data") or {}) if r.content else {}
    except Exception:  # noqa: BLE001
        return {}


def domain_search_contacts(
    domain: str,
    *,
    company_name: str = "",
    limit: int = 10,
) -> tuple[list[dict[str, Any]], str]:
    """Search Hunter for contacts on this domain only (never by name alone).

    Returns (contacts, status) where status is one of:
      hunter_people | hunter_generic | hunter_empty | hunter_error | hunter_skipped
    """
    get_settings.cache_clear()
    key = (get_settings().hunter_api_key or "").strip()
    host = _clean_domain(domain)
    # Never search by company name alone — "boAt" matches boat.sk (wrong country)
    if not key:
        return [], "hunter_skipped"
    if not host:
        return [], "hunter_skipped"

    # Free plan: limit + offset must be <= 10
    limit = max(1, min(int(limit), 10))

    # 1) Named people in marketing/comms
    emails = _call_domain_search(
        api_key=key,
        domain=host,
        limit=limit,
        extra={
            "department": "marketing,communication",
            "type": "personal",
            "required_field": "full_name",
        },
    )
    people = _personal_to_contacts(emails, host)
    if people:
        return people[:limit], "hunter_people"

    # 2) Any named personal emails on the domain
    emails = _call_domain_search(
        api_key=key,
        domain=host,
        limit=limit,
        extra={"type": "personal", "required_field": "full_name"},
    )
    people = _personal_to_contacts(emails, host)
    if people:
        return people[:limit], "hunter_people"

    # 3) Unfiltered — may include generics only
    emails = _call_domain_search(api_key=key, domain=host, limit=limit, extra={})
    people = _personal_to_contacts(emails, host)
    if people:
        return people[:limit], "hunter_people"

    generics = _generic_to_contacts(emails, host, company_name)
    if generics:
        return generics[:limit], "hunter_generic"

    return [], "hunter_empty"


def _call_domain_search(
    *,
    api_key: str,
    domain: str,
    limit: int,
    extra: dict[str, str],
) -> list[dict[str, Any]]:
    params: dict[str, str | int] = {
        "api_key": api_key,
        "domain": domain,
        "limit": limit,
        "offset": 0,
    }
    params.update(extra)

    try:
        with httpx.Client(timeout=20.0) as client:
            r = client.get("https://api.hunter.io/v2/domain-search", params=params)
            if r.status_code >= 400:
                return []
            payload = r.json()
    except Exception:  # noqa: BLE001
        return []

    data = payload.get("data") or {}
    # Guard: Hunter must resolve to the same domain we asked for
    got = _clean_domain(str(data.get("domain") or ""))
    if got and got != domain:
        return []
    emails = data.get("emails") or []
    return [e for e in emails if isinstance(e, dict)]


def _personal_to_contacts(emails: list[dict[str, Any]], brand: str) -> list[dict[str, Any]]:
    marketing_words = (
        "influencer",
        "creator",
        "partnership",
        "brand",
        "marketing",
        "pr",
        "communications",
        "collab",
        "ambassador",
        "social",
        "growth",
        "content",
    )
    scored: list[tuple[int, dict[str, Any]]] = []
    for e in emails:
        if (e.get("type") or "") == "generic":
            continue
        value = (e.get("value") or "").strip()
        first = (e.get("first_name") or "").strip()
        last = (e.get("last_name") or "").strip()
        name = f"{first} {last}".strip()
        if not name or not value:
            continue
        position = (e.get("position") or e.get("position_raw") or "").strip()
        dept = (e.get("department") or "").strip()
        confidence = e.get("confidence")
        verification = e.get("verification") if isinstance(e.get("verification"), dict) else {}
        vstatus = (verification.get("status") or "").strip()
        linkedin = _normalize_linkedin(e.get("linkedin"))
        phone = (e.get("phone_number") or "").strip()

        blob = f"{position} {dept}".lower()
        score = 0
        if dept in ("marketing", "communication"):
            score += 5
        score += sum(2 for w in marketing_words if w in blob)
        if e.get("decision_maker"):
            score += 1
        if isinstance(confidence, int):
            score += confidence // 25
        if linkedin:
            score += 1

        bits = [f"Hunter · {brand}"]
        if confidence is not None:
            bits.append(f"score {confidence}")
        if vstatus:
            bits.append(f"verify {vstatus}")
        if phone:
            bits.append(f"phone {phone}")
        notes = " · ".join(bits) + "."

        scored.append(
            (
                score,
                {
                    "name": name,
                    "title": position or (dept.title() if dept else "Team"),
                    "linkedin_url": linkedin,
                    "email": value,
                    "email_confidence": _confidence_label(confidence, vstatus),
                    "notes": notes,
                },
            )
        )

    scored.sort(key=lambda x: x[0], reverse=True)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for _, row in scored:
        email_l = row["email"].lower()
        if email_l in seen:
            continue
        seen.add(email_l)
        out.append(row)
    return out


def _generic_to_contacts(
    emails: list[dict[str, Any]], brand: str, company_name: str
) -> list[dict[str, Any]]:
    """Brand inboxes only — clearly labeled, not fake people."""
    out: list[dict[str, Any]] = []
    for e in emails:
        if (e.get("type") or "") != "generic":
            continue
        value = (e.get("value") or "").strip().lower()
        if not value or "@" not in value:
            continue
        local = value.split("@", 1)[0]
        if local not in _USEFUL_GENERICS and not any(g in local for g in _USEFUL_GENERICS):
            continue
        label = company_name or brand
        out.append(
            {
                "name": f"{label} ({local})",
                "title": "Brand inbox (not a named person)",
                "linkedin_url": "",
                "email": value,
                "email_confidence": "generic",
                "notes": (
                    f"Hunter only found a generic inbox for {brand} — "
                    "no named marketing contacts in their database. "
                    "Prefer LinkedIn outreach if you can find the right person."
                ),
            }
        )
    return out[:3]


def _normalize_linkedin(raw: Any) -> str:
    linkedin = (str(raw) if raw else "").strip()
    if not linkedin:
        return ""
    if linkedin.startswith("http"):
        return linkedin
    return f"https://www.linkedin.com/in/{linkedin.lstrip('/')}"


def _confidence_label(confidence: Any, verification_status: str) -> str:
    if verification_status == "valid":
        return "high"
    if isinstance(confidence, int):
        if confidence >= 80:
            return "high"
        if confidence >= 50:
            return "medium"
        return "low"
    return "hunter"
