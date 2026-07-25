from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import Base, engine
from app.migrate import ensure_schema
from app.routers import auth, companies, contacts, offers, outreach

settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(companies.router, prefix="/api")
app.include_router(contacts.router, prefix="/api")
app.include_router(outreach.router, prefix="/api")
app.include_router(offers.router, prefix="/api")


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    ensure_schema()


@app.get("/health")
def health():
    return {"ok": True, "app": settings.app_name}
