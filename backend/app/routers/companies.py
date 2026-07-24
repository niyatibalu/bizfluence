from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Company, CreatorProfile, User
from app.schemas import (
    CompanyCreate,
    CompanyOut,
    CompanyUpdate,
    SuggestBrandsRequest,
    SuggestedBrand,
)
from app.services.brand_discovery import suggest_brands
from app.services.company_enrich import enrich_company

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("", response_model=list[CompanyOut])
def list_companies(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(Company)
        .filter(Company.user_id == user.id)
        .order_by(Company.created_at.desc())
        .all()
    )


@router.post("", response_model=CompanyOut)
def create_company(
    payload: CompanyCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(CreatorProfile).filter(CreatorProfile.user_id == user.id).first()
    data = payload.model_dump()
    company = Company(user_id=user.id, **data)
    # Auto-enrich so manually added brands get the same tailored cards
    enrich_company(company, profile)
    db.add(company)
    if profile is not None:
        db.add(profile)
    db.commit()
    db.refresh(company)
    return company


@router.post("/{company_id}/enrich", response_model=CompanyOut)
def enrich_company_route(
    company_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    company = db.get(Company, company_id)
    if not company or company.user_id != user.id:
        raise HTTPException(status_code=404, detail="Company not found")
    profile = db.query(CreatorProfile).filter(CreatorProfile.user_id == user.id).first()
    enrich_company(company, profile, force=True)
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


@router.post("/suggest", response_model=list[SuggestedBrand])
def suggest(
    payload: SuggestBrandsRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(CreatorProfile).filter(CreatorProfile.user_id == user.id).first()
    brands = suggest_brands(
        profile,
        field=payload.field,
        extra_hints=payload.extra_hints,
        refresh_research=payload.refresh_research,
        tier=payload.tier,
    )
    if profile is not None:
        db.add(profile)
        db.commit()
    return brands


@router.post("/suggest/save", response_model=list[CompanyOut])
def suggest_and_save(
    payload: SuggestBrandsRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(CreatorProfile).filter(CreatorProfile.user_id == user.id).first()
    suggestions = suggest_brands(
        profile,
        field=payload.field,
        extra_hints=payload.extra_hints,
        refresh_research=payload.refresh_research,
        tier=payload.tier,
    )
    if profile is not None:
        db.add(profile)

    # Replace prior auto-discovered targets so old searches (other niches/users bleed) don't linger
    if payload.replace_existing:
        stale = (
            db.query(Company)
            .filter(Company.user_id == user.id, Company.status.in_(["discovered", "researching"]))
            .all()
        )
        for c in stale:
            # Keep companies that already have outreach/contacts activity
            if c.contacts or c.messages:
                continue
            db.delete(c)
        db.flush()

    created: list[Company] = []
    existing = db.query(Company).filter(Company.user_id == user.id).all()
    existing_domains = {c.domain.lower() for c in existing if c.domain}
    existing_names = {c.name.lower() for c in existing}
    for s in suggestions:
        key_d = (s.domain or "").lower()
        key_n = s.name.lower()
        if (key_d and key_d in existing_domains) or key_n in existing_names:
            continue
        company = Company(
            user_id=user.id,
            name=s.name,
            domain=s.domain,
            category=s.category,
            fit_rationale=s.fit_rationale,
            suggested_angle=s.suggested_angle,
            priority_narrative=s.priority_narrative,
            status="discovered",
        )
        db.add(company)
        created.append(company)
        if key_d:
            existing_domains.add(key_d)
        existing_names.add(key_n)
    db.commit()
    for c in created:
        db.refresh(c)
    return created


@router.delete("/board/clear-discovered")
def clear_discovered(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Company)
        .filter(Company.user_id == user.id, Company.status == "discovered")
        .all()
    )
    for c in rows:
        if not c.contacts and not c.messages:
            db.delete(c)
    db.commit()
    return {"ok": True, "removed": len(rows)}


@router.get("/{company_id}", response_model=CompanyOut)
def get_company(
    company_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    company = db.get(Company, company_id)
    if not company or company.user_id != user.id:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.patch("/{company_id}", response_model=CompanyOut)
def update_company(
    company_id: int,
    payload: CompanyUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    company = db.get(Company, company_id)
    if not company or company.user_id != user.id:
        raise HTTPException(status_code=404, detail="Company not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(company, key, value)
    db.commit()
    db.refresh(company)
    return company


@router.delete("/{company_id}")
def delete_company(
    company_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    company = db.get(Company, company_id)
    if not company or company.user_id != user.id:
        raise HTTPException(status_code=404, detail="Company not found")
    db.delete(company)
    db.commit()
    return {"ok": True}
