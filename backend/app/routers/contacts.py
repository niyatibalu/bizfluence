from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Company, Contact, User
from app.schemas import ContactCreate, ContactOut, EmailGuessOut, EmailGuessRequest
from app.services.contact_find import find_marketing_contacts
from app.services.email_guess import guess_corporate_email

router = APIRouter(tags=["contacts"])


def _company_for_user(db: Session, user: User, company_id: int) -> Company:
    company = db.get(Company, company_id)
    if not company or company.user_id != user.id:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.get("/companies/{company_id}/contacts", response_model=list[ContactOut])
def list_contacts(
    company_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _company_for_user(db, user, company_id)
    return db.query(Contact).filter(Contact.company_id == company_id).all()


@router.post("/companies/{company_id}/contacts", response_model=ContactOut)
def create_contact(
    company_id: int,
    payload: ContactCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _company_for_user(db, user, company_id)
    contact = Contact(company_id=company_id, **payload.model_dump())
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


@router.post("/companies/{company_id}/contacts/find", response_model=list[ContactOut])
def find_and_save_contacts(
    company_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Best-effort public web search for marketing contacts + email guess. Verify before sending."""
    company = _company_for_user(db, user, company_id)
    found = find_marketing_contacts(company)
    saved: list[Contact] = []
    existing_names = {
        c.name.lower() for c in db.query(Contact).filter(Contact.company_id == company_id).all()
    }
    for row in found:
        if row["name"].lower() in existing_names:
            continue
        contact = Contact(company_id=company_id, **row)
        db.add(contact)
        saved.append(contact)
        existing_names.add(row["name"].lower())
    db.commit()
    for c in saved:
        db.refresh(c)
    return saved


@router.delete("/contacts/{contact_id}")
def delete_contact(
    contact_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    contact = db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    company = db.get(Company, contact.company_id)
    if not company or company.user_id != user.id:
        raise HTTPException(status_code=404, detail="Contact not found")
    db.delete(contact)
    db.commit()
    return {"ok": True}


@router.post("/email/guess", response_model=EmailGuessOut)
def email_guess(payload: EmailGuessRequest, user: User = Depends(get_current_user)):
    _ = user
    return guess_corporate_email(payload.first_name, payload.last_name, payload.domain)
