"""Pitch writing — creator POV. Bio is context for Gemini only; never pasted raw."""

from __future__ import annotations

import re

from app.models import Company, Contact, CreatorProfile
from app.schemas import PitchPack
from app.services.llm import generate_json, last_llm_status
from app.services.web_research import research_brand, research_creator, _ig_handle


def generate_pitch_pack(
    profile: CreatorProfile | None,
    company: Company,
    contact: Contact | None,
    contact_name: str = "",
    contact_title: str = "",
) -> PitchPack:
    raw_name = (contact.name if contact else contact_name) or ""
    first = _first_name(raw_name) if raw_name.strip() else "there"
    title = (contact.title if contact else contact_title) or "the partnerships team"

    niche = _clean_phrase((profile.niche if profile else "") or "lifestyle")
    audience_size = _clean_phrase((profile.audience_size if profile else "") or "")
    audience_geo = _clean_phrase((profile.audience_geo if profile else "") or "India") or "India"
    ig = (getattr(profile, "instagram_url", "") if profile else "") or ""
    handle = _ig_handle(ig) if ig else ""
    bio = (profile.bio if profile else "") or ""  # context only — never insert verbatim

    # Research for Gemini context; offline writer uses only structured fields
    creator_research = ""
    brand_research = ""
    try:
        creator_research = research_creator(profile) if profile else ""
        brand_research = research_brand(company)
    except Exception:  # noqa: BLE001
        pass

    angle = _clean_phrase(company.suggested_angle or "")
    if not angle or "tailor to creator" in angle.lower():
        angle = f"a simple integration that shows {company.name} in a real {niche} moment"

    # --- Offline writer (used when Gemini is down/quota) — NEVER pastes bio ---
    who = f"I create {niche} content for audiences in {audience_geo}"
    if audience_size:
        who += f" ({audience_size})"
    who += "."
    if handle:
        who += f" I'm on Instagram @{handle}."

    linkedin_dm = (
        f"Hi {first}, {who} I'd love to explore a collab with {company.name}. "
        f"Happy to share a short media kit if useful — open to a quick chat?"
    )
    if len(linkedin_dm) > 280:
        linkedin_dm = (
            f"Hi {first}, I create {niche} content in {audience_geo}"
            f"{f' (@{handle})' if handle else ''}. "
            f"Interested in collaborating with {company.name} — happy to share my media kit."
        )

    email_body = (
        f"Hi {first},\n\n"
        f"{who}\n\n"
        f"I'm reaching out to explore a PR seeding or paid collab with {company.name}. "
        f"One angle that could work: {angle}.\n\n"
        f"Happy to send a media kit and recent samples"
        f"{f' (Instagram @{handle})' if handle else ''}. "
        f"Would you or {title} be open to a short conversation?\n\n"
        f"Thanks"
    )

    fallback = {
        "linkedin_dm": linkedin_dm.strip(),
        "email_subject": f"Collab inquiry — {niche} creator × {company.name}",
        "email_body": email_body.strip(),
        "subject_alternatives": [
            f"Creator partnership idea for {company.name}",
            f"PR / collab inquiry from a {niche} creator",
        ],
    }

    data = generate_json(
        system=(
            "You write outreach AS THE CREATOR pitching a brand in India.\n"
            "HARD RULES:\n"
            "- Never write as the brand.\n"
            "- Never paste the creator bio verbatim. Paraphrase into 1 polished sentence max if needed.\n"
            "- Use niche, audience size, geo, and Instagram handle as facts — write natural prose.\n"
            "- Full sentences only. LinkedIn DM under 280 characters. Email: 3 short paragraphs.\n"
            "- Return JSON only: {linkedin_dm, email_subject, email_body, subject_alternatives: string[]}"
        ),
        user=(
            f"Recipient first name: {first}\nRole hint: {title}\n"
            f"FACTS (do not dump as a list in the pitch):\n"
            f"- niche: {niche}\n- audience_size: {audience_size or 'unspecified'}\n"
            f"- audience_geo: {audience_geo}\n- instagram_handle: {handle or 'none'}\n"
            f"- bio (paraphrase only, never copy): {bio[:240] or 'none'}\n"
            f"- brand: {company.name}\n- suggested_angle: {angle}\n"
            f"Extra context (do not paste):\n{creator_research[:300]}\n{brand_research[:300]}"
        ),
        fallback=fallback,
    )

    status = last_llm_status()
    # When Gemini is down/quota, always ship the offline writer — never a half-parsed LLM blob
    if status.get("mode") != "gemini":
        return PitchPack(
            linkedin_dm=fallback["linkedin_dm"],
            email_subject=fallback["email_subject"],
            email_body=fallback["email_body"],
            subject_alternatives=list(fallback["subject_alternatives"]),
            generation_note=(
                "Gemini quota/unavailable — used Bizfluence offline writer "
                "(full sentences; profile bio is context only, never pasted)."
            ),
        )

    dm = _sanitize(str(data.get("linkedin_dm") or fallback["linkedin_dm"]), bio, 300)
    email = _sanitize(str(data.get("email_body") or fallback["email_body"]), bio, 2500)
    subject = str(data.get("email_subject") or fallback["email_subject"]).strip()
    alts = list(data.get("subject_alternatives") or fallback["subject_alternatives"])
    forced_offline = False
    if _looks_brand_pov(dm, company.name) or _looks_brand_pov(email, company.name):
        dm, email, subject, alts = (
            fallback["linkedin_dm"],
            fallback["email_body"],
            fallback["email_subject"],
            list(fallback["subject_alternatives"]),
        )
        forced_offline = True
    # If model pasted bio fragments, force offline copy
    if bio.strip() and len(bio.strip()) >= 8 and bio.strip().lower() in (dm + email).lower():
        dm, email, subject, alts = (
            fallback["linkedin_dm"],
            fallback["email_body"],
            fallback["email_subject"],
            list(fallback["subject_alternatives"]),
        )
        forced_offline = True

    return PitchPack(
        linkedin_dm=dm,
        email_subject=subject,
        email_body=email,
        subject_alternatives=alts,
        generation_note=(
            "Gemini output looked off — used offline writer instead." if forced_offline else ""
        ),
    )


def _sanitize(text: str, bio: str, limit: int) -> str:
    t = (text or "").strip()
    for bad in (
        "Public research thin",
        "Known fit note:",
        "Creator signal:",
        "Brand signal:",
        "from public signals",
        "Manually added",
    ):
        if bad.lower() in t.lower():
            t = t.split("\n\n")[0]
            break
    t = re.sub(r"[ \t]+\n", "\n", t)
    if len(t) > limit:
        t = t[: limit - 1].rsplit(" ", 1)[0] + "…"
    return t


def _looks_brand_pov(text: str, brand: str) -> bool:
    low = text.lower()
    brand_l = brand.lower()
    return any(
        b in low
        for b in (
            f"we at {brand_l}",
            "we are looking for creators",
            "apply to our",
            "join our creator",
            "our brand ambassador",
        )
    )


def _first_name(full: str) -> str:
    full = (full or "").strip()
    if not full or full.lower() in {"there", "team"}:
        return "there"
    return full.split()[0]


def _clean_phrase(text: str) -> str:
    return " ".join((text or "").strip().split())
