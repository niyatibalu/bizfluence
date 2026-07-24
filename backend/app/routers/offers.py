from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Company, CreatorProfile, Offer, OfferBrief, User
from app.schemas import OfferCreate, OfferOut, OfferUpdate
from app.services.offer_eval import _default_reply, evaluate_offer

router = APIRouter(prefix="/offers", tags=["offers"])


@router.get("", response_model=list[OfferOut])
def list_offers(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(Offer)
        .filter(Offer.user_id == user.id)
        .order_by(Offer.created_at.desc())
        .all()
    )


@router.post("", response_model=OfferOut)
def create_offer(
    payload: OfferCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.company_id:
        company = db.get(Company, payload.company_id)
        if not company or company.user_id != user.id:
            raise HTTPException(status_code=400, detail="Invalid company_id")
    else:
        company = None

    offer = Offer(
        user_id=user.id,
        company_id=payload.company_id,
        source=payload.source,
        raw_text=payload.raw_text,
        status="new",
    )
    db.add(offer)
    db.flush()

    profile = db.query(CreatorProfile).filter(CreatorProfile.user_id == user.id).first()
    brief_data = evaluate_offer(profile, offer, company)
    brief = OfferBrief(offer_id=offer.id, **brief_data)
    db.add(brief)
    if profile is not None:
        db.add(profile)
    if company is not None:
        db.add(company)
    db.commit()
    db.refresh(offer)
    return offer


@router.get("/{offer_id}", response_model=OfferOut)
def get_offer(
    offer_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    offer = db.get(Offer, offer_id)
    if not offer or offer.user_id != user.id:
        raise HTTPException(status_code=404, detail="Offer not found")
    return offer


@router.patch("/{offer_id}", response_model=OfferOut)
def update_offer(
    offer_id: int,
    payload: OfferUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    offer = db.get(Offer, offer_id)
    if not offer or offer.user_id != user.id:
        raise HTTPException(status_code=404, detail="Offer not found")
    prev_status = offer.status
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(offer, key, value)
    # When user picks accept / negotiate / pass, refresh reply draft to match
    if payload.status and payload.status != prev_status and offer.brief:
        company = db.get(Company, offer.company_id) if offer.company_id else None
        profile = db.query(CreatorProfile).filter(CreatorProfile.user_id == user.id).first()
        niche = (profile.niche if profile else "") or "creator"
        company_name = company.name if company else "the brand"
        map_stance = {"accepted": "accept", "negotiating": "negotiate", "passed": "pass"}.get(
            payload.status or "", ""
        )
        if map_stance:
            offer.brief.recommended_stance = map_stance
            offer.brief.reply_draft = _default_reply(map_stance, company_name, niche)
    db.commit()
    db.refresh(offer)
    return offer


@router.post("/{offer_id}/reevaluate", response_model=OfferOut)
def reevaluate(
    offer_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    offer = db.get(Offer, offer_id)
    if not offer or offer.user_id != user.id:
        raise HTTPException(status_code=404, detail="Offer not found")
    company = db.get(Company, offer.company_id) if offer.company_id else None
    profile = db.query(CreatorProfile).filter(CreatorProfile.user_id == user.id).first()
    brief_data = evaluate_offer(profile, offer, company)
    if offer.brief:
        for key, value in brief_data.items():
            setattr(offer.brief, key, value)
    else:
        db.add(OfferBrief(offer_id=offer.id, **brief_data))
    if profile is not None:
        db.add(profile)
    if company is not None:
        db.add(company)
    db.commit()
    db.refresh(offer)
    return offer
