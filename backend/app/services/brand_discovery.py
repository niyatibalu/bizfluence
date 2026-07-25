"""India-only brand discovery: large local catalog + live web search."""

from __future__ import annotations

import re

from app.models import CreatorProfile
from app.schemas import SuggestedBrand
from app.services.llm import generate_json
from app.services.web_research import research_creator, search_india_brands


def _b(name: str, domain: str, category: str, fit: str) -> dict[str, str]:
    return {
        "name": name,
        "domain": domain,
        "category": category,
        "fit_rationale": fit,
        "suggested_angle": f"India-market collab angle for {category} — tailor to creator niche.",
        "priority_narrative": "Curated India brand with known or likely creator marketing.",
    }


# Expanded curated India / India-GTM brands by niche (real companies).
NICHE_CATALOG: dict[str, list[dict[str, str]]] = {
    "beauty": [
        _b("Minimalist", "beminimalist.co", "skincare", "Science-led Indian D2C skincare; active creator education."),
        _b("Dot & Key", "dotandkey.com", "skincare", "Lifestyle skincare with frequent mid-tier seeding in India."),
        _b("Plum Goodness", "plumgoodness.com", "skincare", "Clean beauty India brand with strong Instagram marketing."),
        _b("Mamaearth", "mamaearth.in", "personal care", "Mass Indian D2C; heavy influencer + mom-creator spend."),
        _b("The Derma Co", "thedermaco.com", "skincare", "Dermatology-positioned India brand; education creators fit."),
        _b("Foxtale", "foxtale.in", "skincare", "Gen-Z skincare; reel-first marketing."),
        _b("Simple India", "simpleskincare.in", "skincare", "Sensitive-skin positioning; drugstore + creator reach."),
        _b("mCaffeine", "mcaffeine.com", "bath & body", "Coffee-led personal care; campus/lifestyle creators."),
        _b("Sugar Cosmetics", "sugarcosmetics.com", "makeup", "Color cosmetics with large India creator roster."),
        _b("MyGlamm", "myglamm.com", "beauty", "Beauty marketplace + own brands; influencer-heavy."),
        _b("Nykaa", "nykaa.com", "beauty retail", "India's largest beauty retailer; established creator programs."),
        _b("Wow Skin Science", "buywow.in", "personal care", "Mass D2C personal care; volume influencer campaigns."),
        _b("Pilgrim", "pilgrim.in", "skincare", "Korean-inspired India skincare; beauty creators."),
        _b("Earth Rhythm", "earthrhythm.com", "clean beauty", "Clean/conscious beauty; values-aligned creators."),
        _b("Bare Anatomy", "bareanatomy.com", "haircare", "Hair science brand; routine & problem-solution content."),
    ],
    "fitness": [
        _b("Cult.fit", "cult.fit", "fitness", "India fitness platform; coaches & lifestyle creators."),
        _b("HealthifyMe", "healthifyme.com", "health-tech", "Nutrition coaching app; wellness creators."),
        _b("Decathlon", "decathlon.in", "sports retail", "Sports gear India; beginner sport content."),
        _b("MuscleBlaze", "muscleblaze.com", "supplements", "India sports nutrition; gym creators."),
        _b("HKVitals", "hkvitals.com", "supplements", "Wellness supplements; fitness lifestyle."),
        _b("Wellbeing Nutrition", "wellbeingnutrition.com", "supplements", "Clean supplements; premium wellness creators."),
        _b("The Whole Truth", "thewholetruthfoods.com", "nutrition", "Clean protein/snacks; honest-review creators."),
        _b("FitBit India partners", "fitbit.com", "wearables", "Wearables with India fitness audience."),
        _b("Puma India", "in.puma.com", "athleisure", "Sportswear; fashion-fitness crossover."),
        _b("Adidas India", "adidas.co.in", "athleisure", "Sportswear campaigns with athletes & creators."),
        _b("HRX", "hrxbrand.com", "athleisure", "Myntra-led fitness fashion; mass creators."),
        _b("Bold Care", "boldcare.in", "men's wellness", "Men's health D2C; careful niche fit."),
    ],
    "tech": [
        _b("boAt", "boat-lifestyle.com", "audio", "Mass audio India; very high influencer spend."),
        _b("Noise", "gonoise.com", "wearables", "Smartwatches for young India."),
        _b("Nothing", "nothing.tech", "electronics", "Design-forward phones; aesthetic tech creators (India sales)."),
        _b("OnePlus India", "oneplus.in", "smartphones", "Smartphone launches; tech reviewers."),
        _b("realme", "realme.com/in", "smartphones", "Value smartphones; YouTube tech India."),
        _b("Fire-Boltt", "fireboltt.com", "wearables", "Budget wearables; volume creator seeding."),
        _b("CrossBeats", "crossbeats.com", "audio", "Audio D2C; lifestyle tech."),
        _b("Portronics", "portronics.com", "accessories", "Gadgets accessories; unboxing creators."),
        _b("Hammer", "hammeronline.in", "audio", "Audio/wearables; mid-tier India creators."),
        _b("Lenskart", "lenskart.com", "eyewear", "Eyewear retail; try-on / style creators."),
    ],
    "food": [
        _b("Sleepy Owl", "sleepyowl.co", "coffee", "D2C coffee; morning-routine creators."),
        _b("Blue Tokai", "bluetokaicoffee.com", "coffee", "Specialty coffee India; lifestyle + café content."),
        _b("Epigamia", "epigamia.com", "dairy", "Greek yogurt; snack-swap & fitness-adjacent."),
        _b("Slurrp Farm", "slurrpfarm.com", "family food", "Kids nutrition; parenting creators."),
        _b("Yoga Bar", "yogabars.in", "snacks", "Healthy snacks; fitness & workday content."),
        _b("True Elements", "true-elements.com", "healthy foods", "Breakfast/healthy foods; wellness creators."),
        _b("Wingreens Farms", "wingreensfarms.com", "gourmet", "Dips/spreads; foodie reels."),
        _b("Veeba", "veeba.in", "sauces", "Sauces; quick-recipe creators."),
        _b("Country Delight", "countrydelight.in", "dairy delivery", "Fresh dairy subscription; family lifestyle."),
        _b("Farmley", "farmley.com", "dry fruits", "Nuts/snacks; festive + healthy snacking."),
        _b("Chaayos", "chaayos.com", "F&B", "Chai café chain; urban lifestyle."),
        _b("Behrouz Biryani", "behrouzbiryani.com", "food delivery", "Premium biryani brand; food influencers."),
    ],
    "fashion": [
        _b("Snitch", "snitch.co.in", "menswear", "Fast menswear; heavy creator marketing."),
        _b("Bewakoof", "bewakoof.com", "apparel", "Meme/casual apparel; Gen-Z creators."),
        _b("The Souled Store", "thesouledstore.com", "apparel", "Pop-culture merch; fandom creators."),
        _b("Myntra", "myntra.com", "fashion retail", "Fashion marketplace; styling creators."),
        _b("Ajio", "ajio.com", "fashion retail", "Reliance fashion; lookbook creators."),
        _b("Rare Rabbit", "rareism.com", "menswear", "Premium casual menswear."),
        _b("Savana", "savana.com", "womenswear", "Fast fashion women; reel try-ons."),
        _b("Libas", "libas.in", "ethnic wear", "Ethnic wear; festive content."),
        _b("W for Woman", "wforwoman.com", "ethnic wear", "Contemporary ethnic; women lifestyle."),
        _b("Fabindia", "fabindia.com", "lifestyle retail", "Craft/lifestyle; culture & values creators."),
        _b("Biba", "biba.in", "ethnic wear", "Ethnic wear; festive campaigns."),
        _b("Urbanic", "urbanic.com", "womenswear", "Trendy womenswear; Instagram-first."),
    ],
    "home": [
        _b("Pepperfry", "pepperfry.com", "furniture", "Furniture marketplace; home makeover creators."),
        _b("Wakefit", "wakefit.co", "mattress", "Mattress D2C; sleep & wellness content."),
        _b("Sleepyhead", "sleepyhead.in", "mattress", "Sleep products; lifestyle creators."),
        _b("Home Centre", "homecentre.in", "home", "Home décor retail; interiors creators."),
        _b("IKEA India", "ikea.com/in", "home", "Home furnishing; DIY & apartment content."),
    ],
    "fintech": [
        _b("CRED", "cred.club", "fintech", "Premium fintech; lifestyle money creators (stretch)."),
        _b("Groww", "groww.in", "investing", "Investing app; finance educators."),
        _b("Zerodha", "zerodha.com", "investing", "Brokerage; serious finance creators."),
        _b("PhonePe", "phonepe.com", "payments", "Payments; mass India lifestyle."),
        _b("Fi Money", "fi.money", "neobank", "Neobank; young urban money creators."),
    ],
    "default": [
        _b("Nykaa", "nykaa.com", "beauty retail", "Broad India beauty retail creator programs."),
        _b("Myntra", "myntra.com", "fashion retail", "Fashion marketplace campaigns."),
        _b("Flipkart", "flipkart.com", "e-commerce", "Big-fest campaigns; category-dependent fit."),
        _b("Amazon India", "amazon.in", "e-commerce", "Influencer storefronts & seasonal campaigns."),
        _b("Meesho", "meesho.com", "social commerce", "Value commerce; regional/language creators."),
    ],
}


def _catalog_for_niche(niche: str, field: str | None) -> list[SuggestedBrand]:
    key = (field or niche or "default").lower()
    matched: list[dict[str, str]] = []
    for niche_key, brands in NICHE_CATALOG.items():
        if niche_key == "default":
            continue
        if niche_key in key or any(w in key for w in niche_key.split() if len(w) > 3):
            matched.extend(brands)
        # also match category words inside brand niches
        for b in brands:
            if b["category"].lower() in key or any(
                w in b["fit_rationale"].lower() for w in key.split() if len(w) > 4
            ):
                if b not in matched:
                    matched.append(b)
    if not matched:
        # keyword map
        aliases = {
            "skincare": "beauty",
            "makeup": "beauty",
            "cosmetic": "beauty",
            "gym": "fitness",
            "health": "fitness",
            "wellness": "fitness",
            "gadget": "tech",
            "phone": "tech",
            "audio": "tech",
            "coffee": "food",
            "foodie": "food",
            "recipe": "food",
            "outfit": "fashion",
            "style": "fashion",
            "ethnic": "fashion",
            "interior": "home",
            "decor": "home",
            "finance": "fintech",
            "money": "fintech",
        }
        for word, mapped in aliases.items():
            if word in key:
                matched.extend(NICHE_CATALOG.get(mapped, []))
    if not matched:
        matched = NICHE_CATALOG["default"] + NICHE_CATALOG["beauty"][:5] + NICHE_CATALOG["fashion"][:5]
    seen: set[str] = set()
    out: list[SuggestedBrand] = []
    for b in matched:
        dom = b["domain"].lower()
        if dom in seen:
            continue
        seen.add(dom)
        out.append(SuggestedBrand(**b))
    return out[:20]


def suggest_brands(
    profile: CreatorProfile | None,
    field: str | None = None,
    extra_hints: str = "",
    refresh_research: bool = False,
    tier: str = "micro_mid",
) -> list[SuggestedBrand]:
    niche = (profile.niche if profile else "") or ""
    exclusions = (profile.exclusions if profile else "") or ""
    goals = (profile.collab_goals if profile else "") or ""
    audience_size = (profile.audience_size if profile else "") or ""

    creator_ctx = ""
    if profile is not None:
        creator_ctx = research_creator(profile, force=refresh_research)

    catalog = _catalog_for_niche(niche, field)
    if tier == "micro_mid":
        catalog = [b for b in catalog if not _is_mega_brand(b.name, b.domain)]

    tier_hints = (
        "Prefer emerging India D2C, startups, and mid-size brands that work with micro/mid creators "
        "(about 1K–500K followers). Avoid only mega marketplaces (Amazon, Flipkart, Myntra, Nykaa as primary) "
        "unless no smaller alternatives exist."
        if tier == "micro_mid"
        else ""
    )
    web_brands = search_india_brands(
        niche,
        field,
        f"{extra_hints} {tier_hints} micro influencer friendly D2C startup".strip(),
        creator_ctx,
    )

    merged: dict[str, SuggestedBrand] = {}
    for b in catalog:
        key = (b.domain or b.name).lower()
        merged[key] = b
    for raw in web_brands:
        try:
            sb = SuggestedBrand(**raw)
        except Exception:  # noqa: BLE001
            continue
        if tier == "micro_mid" and _is_mega_brand(sb.name, sb.domain):
            continue
        key = (sb.domain or sb.name).lower()
        if key not in merged:
            merged[key] = sb

    # Personalize ranking / angles with creator research (Gemini when live)
    candidates = list(merged.values())[:20]
    # Offline personalization so free-tier quota does not dump raw catalog blurbs
    personalized_offline = [
        _personalize_brand_offline(b, profile, niche, audience_size, creator_ctx) for b in candidates
    ]
    fallback = {"brands": [b.model_dump() for b in personalized_offline]}
    data = generate_json(
        system=(
            "You are an India-focused influencer manager for MICRO and MID-TIER creators (1K–500K followers). "
            "Keep ONLY brands relevant to this creator's niche. Geography: India only. Respect exclusions. "
            "Prefer smaller D2C / emerging brands that actually reply to cold outreach — not only Fortune-scale giants. "
            "Rewrite fit_rationale and suggested_angle to reference THIS creator (niche, audience, platforms). "
            "Return JSON {brands:[...]} max 12 items. "
            "Note: candidates come from a curated India directory PLUS live web search — not Gemini alone."
        ),
        user=(
            f"Creator niche: {niche}\nField: {field or 'none'}\nExclusions: {exclusions}\nGoals: {goals}\n"
            f"Audience size hint: {audience_size or 'micro/mid'}\nAudience geo: "
            f"{(profile.audience_geo if profile else 'India')}\n"
            f"Tier preference: {tier}\n"
            f"Creator research (from their linked socials only):\n{creator_ctx}\n\nCandidates:\n{fallback}"
        ),
        fallback=fallback,
    )

    results: list[SuggestedBrand] = []
    for item in (data.get("brands") or fallback["brands"])[:12]:
        try:
            sb = SuggestedBrand(**item)
        except Exception:  # noqa: BLE001
            continue
        if tier == "micro_mid" and _is_mega_brand(sb.name, sb.domain):
            continue
        results.append(sb)
    return results or personalized_offline[:8]


def _personalize_brand_offline(
    brand: SuggestedBrand,
    profile: CreatorProfile | None,
    niche: str,
    audience_size: str,
    creator_ctx: str,
) -> SuggestedBrand:
    """When Gemini is quota'd out, still write fit copy that names THIS creator's niche."""
    niche_l = (niche or "their niche").strip() or "their niche"
    audience = audience_size.strip() if audience_size else ""
    geo = ((profile.audience_geo if profile else "") or "India").strip()
    handle = ""
    if profile and getattr(profile, "instagram_url", ""):
        from app.services.web_research import _ig_handle

        handle = _ig_handle(profile.instagram_url or "")

    who = f"a {niche_l} creator"
    if audience:
        who += f" with ~{audience} reach"
    who += f" in {geo}"
    if handle:
        who += f" (@{handle})"

    # Prefer content themes from research when present
    themes = []
    if creator_ctx:
        m = re.search(r"Content themes from titles:\s*([^\n.]+)", creator_ctx, re.I)
        if m:
            themes = [t.strip() for t in m.group(1).split(",") if t.strip()][:3]
    theme_bit = f" (especially {' / '.join(themes)})" if themes else ""

    base = (brand.fit_rationale or "").strip()
    # Keep the brand's category fact, then attach creator-specific why
    fit = (
        f"{brand.name} fits {who}{theme_bit}: {base}"
        if base and "creator" not in base.lower()[:40]
        else f"{brand.name} is a relevant India {brand.category or 'consumer'} brand for {who}{theme_bit}."
    )
    # Avoid runaway length
    if len(fit) > 280:
        fit = fit[:277].rsplit(" ", 1)[0] + "…"

    angle = (brand.suggested_angle or "").strip()
    if not angle or "tailor to creator" in angle.lower() or "india-market collab angle" in angle.lower():
        angle = f"Show {brand.name} inside a real {niche_l} moment that matches how this creator already posts."

    return SuggestedBrand(
        name=brand.name,
        domain=brand.domain,
        category=brand.category,
        fit_rationale=fit,
        suggested_angle=angle,
        priority_narrative=brand.priority_narrative
        or "Matched to this creator’s niche and audience.",
    )


def _is_mega_brand(name: str, domain: str) -> bool:
    blob = f"{name} {domain}".lower()
    megas = [
        "amazon",
        "flipkart",
        "myntra",
        "ajio",
        "nykaa",
        "meesho",
        "reliance",
        "tata cliq",
        "cred.club",
        "phonepe",
        "google",
        "meta ",
        "facebook",
        "apple.com",
        "samsung",
        "unilever",
        "hindustan unilever",
        "procter",
        "coca-cola",
        "pepsi",
    ]
    return any(m in blob for m in megas)
