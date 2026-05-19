"""SQLAlchemy models, session factory, init + seed."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime
from typing import Iterator, Optional

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Integer, String, Text, create_engine, func,
)
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker,
)

from config.settings import SETTINGS, resolved_database_url
from core.logging import get_logger
from core.security import hash_password

log = get_logger("core.db")


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    profile: Mapped[Optional["Profile"]] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    cases: Mapped[list["Case"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Profile(Base):
    __tablename__ = "profiles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    firm_name: Mapped[str] = mapped_column(String(160), nullable=False)
    role: Mapped[str] = mapped_column(String(40), nullable=False, default="lawyer")
    practice_area: Mapped[str] = mapped_column(String(80), nullable=False)
    years_of_experience: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    jurisdiction_focus: Mapped[str] = mapped_column(String(120), nullable=False)
    city: Mapped[str] = mapped_column(String(80), nullable=False)
    preferred_languages: Mapped[str] = mapped_column(String(255), nullable=False, default="English")
    bar_registration_id: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    default_workspace_theme: Mapped[str] = mapped_column(String(40), nullable=False, default="Parchment (light)")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    user: Mapped[User] = relationship(back_populates="profile")


class Case(Base):
    __tablename__ = "cases"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    case_name: Mapped[str] = mapped_column(String(200), nullable=False)
    case_type: Mapped[str] = mapped_column(String(80), nullable=False)
    court_or_forum: Mapped[str] = mapped_column(String(120), nullable=False)
    jurisdiction: Mapped[str] = mapped_column(String(120), nullable=False)
    client_name: Mapped[str] = mapped_column(String(160), nullable=False)
    party_names: Mapped[str] = mapped_column(Text, nullable=False)
    your_role_in_case: Mapped[str] = mapped_column(String(80), nullable=False)
    opposing_party_name: Mapped[str] = mapped_column(String(255), nullable=False)
    filing_date: Mapped[date] = mapped_column(Date, nullable=False)
    next_hearing_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    urgency_level: Mapped[str] = mapped_column(String(20), nullable=False, default="Routine")
    confidentiality_level: Mapped[str] = mapped_column(String(20), nullable=False, default="Standard")
    case_status: Mapped[str] = mapped_column(String(40), nullable=False, default="Drafting")
    short_case_summary: Mapped[str] = mapped_column(Text, nullable=False)
    internal_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    user: Mapped[User] = relationship(back_populates="cases")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    target_type: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    target_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


_engine = None
_SessionLocal: Optional[sessionmaker[Session]] = None


def _ensure_dirs() -> None:
    """Create every directory the backend writes into. Idempotent and
    safe to call on every boot. On Render with a persistent disk mounted
    at /var/data, DATA_ROOT + CASES_ROOT both land on the disk and these
    mkdirs are no-ops after the first deploy."""
    for d in (
        SETTINGS.data_root,
        SETTINGS.cases_root,
        SETTINGS.uploads_dir,
        SETTINGS.outputs_dir,
        SETTINGS.seeds_dir,
        SETTINGS.logs_dir,
    ):
        d.mkdir(parents=True, exist_ok=True)


def get_engine():
    global _engine
    if _engine is None:
        _ensure_dirs()
        _engine = create_engine(
            resolved_database_url(),
            echo=False,
            future=True,
            connect_args={"check_same_thread": False} if resolved_database_url().startswith("sqlite") else {},
        )
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, expire_on_commit=False)
    return _SessionLocal


@contextmanager
def session_scope() -> Iterator[Session]:
    sess = get_session_factory()()
    try:
        yield sess
        sess.commit()
    except Exception:
        sess.rollback()
        raise
    finally:
        sess.close()


def init_db() -> None:
    Base.metadata.create_all(bind=get_engine())
    log.info("Database tables ensured at {}", resolved_database_url())


def write_audit(sess: Session, *, user_id: Optional[int], action: str, target_type: Optional[str] = None,
                target_id: Optional[int] = None, message: Optional[str] = None) -> None:
    sess.add(AuditLog(user_id=user_id, action=action, target_type=target_type, target_id=target_id, message=message))
    log.info("audit | user={} action={} target={}:{} | {}", user_id, action, target_type, target_id, message or "")


def seed_demo_users() -> None:
    """Create the two demo lawyers with pre-loaded profile + case if not present."""
    if not SETTINGS.seed_demo_users:
        return

    demo_payloads = [
        {
            "email": SETTINGS.demo_user_1_email,
            "password": SETTINGS.demo_user_1_password,
            "profile": dict(
                full_name="Anika Rao",
                display_name="Anika",
                firm_name="Rao & Mehta Associates",
                role="lawyer",
                practice_area="Commercial litigation",
                years_of_experience=11,
                jurisdiction_focus="Bombay High Court",
                city="Mumbai",
                preferred_languages="English, Hindi, Marathi",
                bar_registration_id="MAH/2014/04821",
                phone="+91 98200 11223",
                default_workspace_theme="Parchment (light)",
            ),
            "case": dict(
                case_name="Aurelia Ventures Pvt Ltd v. Stellar Holdings LLP",
                case_type="Commercial dispute",
                court_or_forum="Bombay High Court",
                jurisdiction="Bombay High Court",
                client_name="Aurelia Ventures Pvt Ltd",
                party_names="Aurelia Ventures Pvt Ltd; Stellar Holdings LLP; Mr. R. Kothari (guarantor)",
                your_role_in_case="Counsel for plaintiff",
                opposing_party_name="Stellar Holdings LLP",
                filing_date=date(2026, 1, 18),
                next_hearing_date=date(2026, 6, 4),
                urgency_level="Elevated",
                confidentiality_level="Privileged",
                case_status="Pending hearing",
                short_case_summary=(
                    "Claim for INR 12.4 crore arising from breach of an exclusive distribution "
                    "agreement dated 2023-08-14. Plaintiff seeks specific performance and damages; "
                    "interim injunction granted in part."
                ),
                internal_notes="Lead witness Mr. Patel rehearsal still pending; clarify guarantor liability.",
            ),
        },
        {
            "email": SETTINGS.demo_user_2_email,
            "password": SETTINGS.demo_user_2_password,
            "profile": dict(
                full_name="Vikram Shastri",
                display_name="Vikram",
                firm_name="Shastri Chambers",
                role="lawyer",
                practice_area="Constitutional & writ",
                years_of_experience=18,
                jurisdiction_focus="Delhi High Court",
                city="New Delhi",
                preferred_languages="English, Hindi",
                bar_registration_id="DEL/2007/01147",
                phone="+91 98110 44556",
                default_workspace_theme="Parchment (light)",
            ),
            "case": dict(
                case_name="Ravi Menon v. State of Maharashtra & Ors.",
                case_type="Writ petition",
                court_or_forum="Bombay High Court",
                jurisdiction="Bombay High Court",
                client_name="Ravi Menon",
                party_names="Ravi Menon (petitioner); State of Maharashtra; Municipal Commissioner, Pune",
                your_role_in_case="Counsel for petitioner",
                opposing_party_name="State of Maharashtra; Municipal Commissioner, Pune",
                filing_date=date(2026, 3, 2),
                next_hearing_date=date(2026, 5, 27),
                urgency_level="Urgent",
                confidentiality_level="Restricted",
                case_status="Under arguments",
                short_case_summary=(
                    "Article 226 petition challenging a municipal demolition notice on grounds of "
                    "violation of natural justice and Article 21. Stay granted pending final hearing."
                ),
                internal_notes="Prepare cross-references to Olga Tellis and Maneka Gandhi.",
            ),
        },
    ]

    with session_scope() as sess:
        for payload in demo_payloads:
            existing = sess.query(User).filter(User.email == payload["email"]).one_or_none()
            if existing:
                continue
            user = User(email=payload["email"], password_hash=hash_password(payload["password"]), is_demo=True)
            sess.add(user)
            sess.flush()
            sess.add(Profile(user_id=user.id, **payload["profile"]))
            sess.add(Case(user_id=user.id, **payload["case"]))
            write_audit(sess, user_id=user.id, action="seed.user", target_type="user", target_id=user.id,
                        message=f"Seeded demo user {payload['email']}")
            log.info("Seeded demo user {}", payload["email"])


if __name__ == "__main__":
    init_db()
    seed_demo_users()
    print("Database initialised and demo accounts seeded.")
