"""Offer evaluation — plain-English manager brief grounded in offer text + research."""

from __future__ import annotations

import json
import re

from app.models import Company, CreatorProfile, Offer
from app.services.llm import generate_json, last_llm_status
from app.services.web_research import research_brand, research_creator


def evaluate_offer(profile: CreatorProfile | None, offer: Offer, company: Company | None) -> dict:
    niche = (profile.niche if profile else "") or "your niche"
    exclusions = (profile.exclusions if profile else "") or ""
    company_name = company.name if company else _guess_brand_from_offer(offer.raw_text) or "this brand"

    creator_research = research_creator(profile) if profile else ""
    brand_research = research_brand(company) if company else ""

    facts = _extract_offer_facts(offer.raw_text)
    stance = _decide_stance(facts, exclusions)

    fit_summary = _write_fit(company_name, niche, profile, company, facts, creator_research)
    upsides = _write_upsides(company_name, brand_research, niche)
    risks = _write_risks(company_name, brand_research, exclusions, facts)
    pay = _write_pay(facts)
    load = _write_load(facts)
    flags = _write_flags(facts)
    talking = _write_talking_points(company_name, facts, stance)
    reply = _default_reply(stance, company_name, niche)

    fallback = {
        "fit_summary": fit_summary,
        "reputation_upsides": upsides,
        "reputation_risks": risks,
        "pay_value_clarity": pay,
        "deliverable_load": load,
        "red_flags": flags,
        "factors": {
            "brand_fit": fit_summary,
            "audience_alignment": (
                f"Your niche is {niche}. "
                + (
                    "Your profile research suggests this is on-brand for you."
                    if creator_research
                    else "Add platform links and run research for a sharper read."
                )
            ),
            "exclusivity": facts.get("exclusivity") or "Not clearly stated in the offer.",
            "usage_rights": facts.get("usage") or "Not clearly stated — ask before signing.",
            "timeline": facts.get("timeline") or "No clear deadline in the offer.",
            "payment_terms": facts.get("payment") or "No clear cash fee stated.",
            "creative_control": "Ask how many revision rounds and whether scripts are mandatory.",
            "cancellation_risk": "Ask what happens if the campaign is cancelled after you shoot.",
        },
        "recommended_stance": stance,
        "talking_points": talking,
        "reply_draft": reply,
    }

    data = generate_json(
        system=(
            "You are a practical influencer manager in India. "
            "Write a clear brief a creator can act on today. "
            "Short sentences. No jargon like 'cross-check brand reputation against audience expectations'. "
            "No dumping raw research notes. Do not invent a numeric score. "
            "Stance must be accept, negotiate, or pass. "
            "Return JSON keys: fit_summary, reputation_upsides, reputation_risks, "
            "pay_value_clarity, deliverable_load, red_flags, factors (object of short strings), "
            "recommended_stance, talking_points, reply_draft."
        ),
        user=(
            f"Creator niche: {niche}\nExclusions: {exclusions or 'none'}\n"
            f"Creator research (context only):\n{creator_research[:600]}\n\n"
            f"Brand: {company_name}\nBrand research (context only):\n{brand_research[:600]}\n\n"
            f"Extracted facts: {json.dumps(facts)}\n\nOffer text:\n{offer.raw_text}"
        ),
        fallback=fallback,
    )

    # Guard against LLM returning cryptic/generic garbage
    def pick(key: str) -> str:
        val = (data.get(key) or fallback[key] or "").strip()
        if _looks_cryptic(val):
            return str(fallback[key])
        return val

    factors = data.get("factors") if isinstance(data.get("factors"), dict) else fallback["factors"]
    # sanitize factor values
    clean_factors = {}
    for k, v in (factors or {}).items():
        sv = str(v)
        clean_factors[k] = fallback["factors"].get(k, sv) if _looks_cryptic(sv) else sv

    stance_out = (data.get("recommended_stance") or stance).lower().strip()
    if stance_out not in {"accept", "negotiate", "pass"}:
        stance_out = stance

    # Prefer offline writer when Gemini returns cryptic dumps or quota fails
    status = last_llm_status()
    use_offline = status.get("mode") != "gemini"
    if use_offline:
        return {
            "fit_summary": fit_summary,
            "reputation_upsides": upsides,
            "reputation_risks": risks,
            "pay_value_clarity": pay,
            "deliverable_load": load,
            "red_flags": flags,
            "factors_json": json.dumps(fallback["factors"]),
            "recommended_stance": stance,
            "talking_points": talking,
            "reply_draft": reply,
            "generation_note": (
                "Brief based on the offer text and your profile — adjust anything that feels off."
            ),
        }

    return {
        "fit_summary": pick("fit_summary"),
        "reputation_upsides": pick("reputation_upsides"),
        "reputation_risks": pick("reputation_risks"),
        "pay_value_clarity": pick("pay_value_clarity"),
        "deliverable_load": pick("deliverable_load"),
        "red_flags": pick("red_flags"),
        "factors_json": json.dumps(clean_factors),
        "recommended_stance": stance_out,
        "talking_points": pick("talking_points"),
        "reply_draft": pick("reply_draft"),
        "generation_note": "",
    }


def _looks_cryptic(text: str) -> bool:
    bad = [
        "cross-check brand reputation",
        "public research thin",
        "known fit note",
        "brand notes:",
        "creator signal:",
        "brand signal:",
        "verify influencer program and recent sentiment manually",
        "see brand research",
    ]
    low = text.lower()
    return any(b in low for b in bad)


def _extract_offer_facts(text: str) -> dict[str, str]:
    t = text or ""
    low = t.lower()
    facts: dict[str, str] = {}

    deliverables = []
    if re.search(r"\breel\b", low):
        deliverables.append("Reel(s)")
    if re.search(r"\bstor(y|ies)\b", low):
        deliverables.append("Stories")
    if re.search(r"\bpost\b", low):
        deliverables.append("Feed post(s)")
    if re.search(r"\byoutube\b|\bvideo\b", low):
        deliverables.append("Video")
    if deliverables:
        facts["deliverables"] = ", ".join(deliverables)

    money = re.search(r"(₹\s?[\d,]+|rs\.?\s?[\d,]+|inr\s?[\d,]+|\$\s?[\d,]+)", t, re.I)
    if money:
        facts["payment"] = f"Mentions {money.group(1)}"
    elif "product only" in low or "product gifting" in low or "gifting" in low:
        facts["payment"] = "Looks product/gift-led; cash fee not clearly stated"
    elif "unpaid" in low or "for exposure" in low:
        facts["payment"] = "Unpaid / exposure framing"
    elif "paid" in low or "fee" in low or "remuneration" in low:
        facts["payment"] = "Paid mentioned, but amount unclear — ask for INR number"
    else:
        facts["payment"] = "No clear payment terms in the text"

    excl = re.search(r"(\d+[-\s]?(day|days|month|months|year|years).{0,40}exclusiv\w*)", low)
    if excl:
        facts["exclusivity"] = excl.group(0)
    elif "exclusiv" in low:
        facts["exclusivity"] = "Exclusivity mentioned — get category + duration in writing"

    if "whitelist" in low or "spark ads" in low or "usage rights" in low or "in perpetuity" in low:
        facts["usage"] = "Usage / whitelisting / rights language present — price this separately"
    elif "organic" in low:
        facts["usage"] = "Says organic usage only"

    time = re.search(r"(next \d+ weeks?|within \d+ days?|by\s+\w+\s+\d{1,2}|\d+\s*weeks?)", low)
    if time:
        facts["timeline"] = time.group(0)

    if "cash top-up" in low or "top up" in low or "top-up" in low:
        facts["payment"] = (facts.get("payment") or "") + "; cash top-up mentioned but vague"

    return facts


def _decide_stance(facts: dict[str, str], exclusions: str) -> str:
    pay = (facts.get("payment") or "").lower()
    if "unpaid" in pay or "exposure" in pay:
        return "pass"
    if "product/gift" in pay or "vague" in pay or "unclear" in pay or "not clearly" in pay:
        return "negotiate"
    if "₹" in pay or "inr" in pay or "rs" in pay:
        return "accept" if "exclusivity" not in facts else "negotiate"
    return "negotiate"


def _write_fit(
    company_name: str,
    niche: str,
    profile: CreatorProfile | None,
    company: Company | None,
    facts: dict[str, str],
    creator_research: str,
) -> str:
    bits = [f"This offer is from {company_name} for a creator in {niche}."]
    if facts.get("deliverables"):
        bits.append(f"They are asking for {facts['deliverables']}.")
    # Only use fit_rationale if it reads like a full sentence (has a verb-ish length, no telegraphic ";")
    if company and company.fit_rationale:
        fr = " ".join(company.fit_rationale.strip().split())
        if len(fr) > 40 and ";" not in fr and not fr.lower().startswith("manually"):
            if fr[-1] not in ".!?":
                fr += "."
            bits.append(fr)
        else:
            bits.append(
                f"On paper it can fit {niche} content, but judge whether the brief matches how you actually create."
            )
    else:
        bits.append(f"Check whether {company_name} matches the kind of {niche} content you already post.")
    return " ".join(bits)


def _write_upsides(company_name: str, brand_research: str, niche: str) -> str:
    if brand_research and "Creator-marketing signals found" in brand_research:
        return (
            f"{company_name} shows up online in creator/influencer contexts, "
            f"so a collab can look normal to a {niche} audience rather than random."
        )
    if brand_research and "No obvious controversy" in brand_research:
        return (
            f"{company_name} did not throw obvious controversy headlines in a quick search, "
            f"which is a basic plus for audience trust."
        )
    return (
        f"If your audience already knows or likes {company_name}, this can strengthen niche credibility. "
        f"Ask them for 2–3 recent creator examples so you can judge brand-safety yourself."
    )


def _write_risks(company_name: str, brand_research: str, exclusions: str, facts: dict[str, str]) -> str:
    risks = []
    if brand_research and "Possible reputation flags" in brand_research:
        risks.append(f"Search surfaced possible reputation flags for {company_name} — read those headlines before saying yes.")
    else:
        risks.append(f"We did not find loud controversy for {company_name} in a quick search, but that is not a deep audit.")
    if exclusions:
        risks.append(f"Stay away if this conflicts with your no-gos: {exclusions}.")
    if "gift" in (facts.get("payment") or "").lower() or "product" in (facts.get("payment") or "").lower():
        risks.append("Gift-only or vague cash deals often underpay relative to the work.")
    return " ".join(risks)


def _write_pay(facts: dict[str, str]) -> str:
    return facts.get("payment") or "The offer does not clearly state cash, product value, or payment timing."


def _write_load(facts: dict[str, str]) -> str:
    d = facts.get("deliverables")
    t = facts.get("timeline")
    if d and t:
        return f"{d}, with timing around: {t}."
    if d:
        return f"{d}. Timeline is unclear — ask for posting dates before you accept."
    return "Deliverables are vague. Get an exact list (how many Reels/Stories/posts and due dates)."


def _write_flags(facts: dict[str, str]) -> str:
    flags = []
    if facts.get("exclusivity"):
        flags.append(f"Exclusivity: {facts['exclusivity']}")
    if facts.get("usage"):
        flags.append(facts["usage"])
    pay = facts.get("payment") or ""
    if "gift" in pay.lower() or "vague" in pay.lower() or "unpaid" in pay.lower():
        flags.append(pay)
    return " | ".join(flags) if flags else "No major red flags jumped out of the text, but payment and exclusivity still need written clarity."


def _write_talking_points(company_name: str, facts: dict[str, str], stance: str) -> str:
    points = [
        f"Confirm the exact deliverables for {company_name} in writing.",
        "Ask for the cash fee in INR (and whether product is extra or instead).",
    ]
    if facts.get("exclusivity"):
        points.append("Narrow exclusivity: which category, how many days, and what happens if you already have a competing draft.")
    if facts.get("usage"):
        points.append("If they want whitelisting/ads usage, price it as a separate line item.")
    if stance == "pass":
        points.append("If terms stay unpaid/exposure-only, politely decline and invite a paid brief later.")
    return "\n".join(f"- {p}" for p in points)


def _guess_brand_from_offer(text: str) -> str:
    m = re.search(r"\b([A-Z][A-Za-z0-9&'.]+(?:\s+[A-Z][A-Za-z0-9&'.]+){0,2})\b would like", text or "")
    if m:
        return m.group(1)
    return ""


def _default_reply(stance: str, company: str, niche: str) -> str:
    if stance == "accept":
        return (
            f"Hi — thanks for the {company} note. This fits my {niche} content well. "
            f"Please send the agreement with deliverables, fee (INR), and timeline so we can lock it in."
        )
    if stance == "pass":
        return (
            f"Hi — thank you for thinking of me for {company}. "
            f"I'll pass on these terms, but I'd be happy to revisit a paid brief later."
        )
    return (
        f"Hi — thanks for the {company} brief. I'm interested. Before I confirm, could you share: "
        f"(1) exact deliverables, (2) cash fee in INR, (3) exclusivity window/category, and "
        f"(4) whether you need paid usage/whitelisting? Happy to jump on a short call."
    )
