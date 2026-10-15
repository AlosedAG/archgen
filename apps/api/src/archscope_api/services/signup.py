"""Self sign-up and password reset, both confirmed with a 6-digit code
sent by email.

- Sign-up holds the name and password hash in a pending code record; the
  account is created only when the code is confirmed. Users whose email
  domain is listed on a workspace (``signup_domains``) join it as members;
  everyone else gets their own workspace as its owner.
- Requests never reveal whether an email has an account: signing up with
  an existing email emails that person instead, and a reset for an
  unknown email silently does nothing.
- Codes: 15 minutes, 5 attempts, a new one at most once a minute; only an
  HMAC of the code is stored.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..mail import Mailer, Message
from ..persistence.models import (
    PURPOSE_RESET,
    PURPOSE_SIGNUP,
    ROLE_MEMBER,
    ROLE_OWNER,
    AuthSession,
    EmailCode,
    Membership,
    User,
    Workspace,
)
from ..persistence.security import hash_password
from .auth import Principal, clear_failed_sign_ins, start_session
from .errors import Conflict, InvalidCode, TooManyRequests, WeakPassword

CODE_TTL = timedelta(minutes=15)
RESEND_AFTER = timedelta(seconds=60)
MAX_ATTEMPTS = 5
MIN_PASSWORD = 10
PURPOSE_EXISTS = "exists"  # throttles "you already have an account" emails
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _norm(email: str) -> str:
    return email.strip().lower()


def _aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def _code_hash(pepper: str, purpose: str, email: str, code: str) -> str:
    return hmac.new(pepper.encode(), f"{purpose}:{email}:{code}".encode(), hashlib.sha256).hexdigest()


def check_password(password: str, email: str) -> None:
    """Minimum length, not the email itself, not a single repeated character."""
    if len(password) < MIN_PASSWORD:
        raise WeakPassword(f"Use at least {MIN_PASSWORD} characters.")
    if password.strip().lower() in {email, email.split("@")[0]}:
        raise WeakPassword("Don't use your email address as your password.")
    if len(set(password)) < 4:
        raise WeakPassword("Use a mix of characters.")


def _footer() -> str:
    return "If you didn't ask for this, you can ignore this email.\n\n— ArchitectureScope"


def _issue(
    db: Session, mailer: Mailer, pepper: str, *, email: str, purpose: str, payload: dict[str, str], subject: str, intro: str
) -> None:
    """Create or refresh a code record and email the code."""
    now = datetime.now(UTC)
    record = db.get(EmailCode, (email, purpose))
    if record is not None and now - _aware(record.last_sent_at) < RESEND_AFTER:
        raise TooManyRequests("A code was just sent. Wait a minute before asking for another.")
    code = f"{secrets.randbelow(1_000_000):06d}"
    if record is None:
        record = EmailCode(email=email, purpose=purpose, payload={})
        db.add(record)
    record.code_hash = _code_hash(pepper, purpose, email, code)
    if payload:
        record.payload = payload
    record.attempts = 0
    record.expires_at = now + CODE_TTL
    record.last_sent_at = now
    db.flush()
    minutes = int(CODE_TTL.total_seconds() // 60)
    mailer.send(
        Message(to=email, subject=subject, text=f"{intro}\n\nYour code: {code}\n\nIt expires in {minutes} minutes. {_footer()}")
    )


def _consume(db: Session, pepper: str, *, email: str, purpose: str, code: str) -> EmailCode:
    """The pending record if ``code`` is right; otherwise count the attempt and refuse."""
    record = db.get(EmailCode, (email, purpose))
    if record is None or _aware(record.expires_at) <= datetime.now(UTC):
        raise InvalidCode("That code has expired. Ask for a new one.")
    if record.attempts >= MAX_ATTEMPTS:
        raise InvalidCode("Too many wrong codes. Ask for a new one.")
    if not hmac.compare_digest(_code_hash(pepper, purpose, email, code.strip()), record.code_hash):
        record.attempts += 1
        # Commit now: the error below rolls back the request's transaction,
        # and the attempt must still count (otherwise guessing is unlimited).
        db.commit()
        left = MAX_ATTEMPTS - record.attempts
        raise InvalidCode(
            f"That code isn't right. {left} attempt{'s' if left != 1 else ''} left."
            if left
            else "Too many wrong codes. Ask for a new one."
        )
    return record


# ---- Sign-up ------------------------------------------------------------------


def request_signup(db: Session, mailer: Mailer, pepper: str, *, email: str, name: str, password: str) -> None:
    """Send a sign-up code — or, if the email already has an account, a
    note saying so. The caller can't tell which happened."""
    email = _norm(email)
    if not _EMAIL_RE.match(email):
        raise WeakPassword("Enter a valid email address.")
    check_password(password, email)
    if db.scalar(select(User).where(User.email == email)) is not None:
        now = datetime.now(UTC)
        record = db.get(EmailCode, (email, PURPOSE_EXISTS))
        if record is not None and now - _aware(record.last_sent_at) < RESEND_AFTER:
            return
        if record is None:
            record = EmailCode(email=email, purpose=PURPOSE_EXISTS, code_hash="", payload={}, expires_at=now)
            db.add(record)
        record.last_sent_at = now
        db.flush()
        mailer.send(
            Message(
                to=email,
                subject="You already have an ArchitectureScope account",
                text=(
                    "Someone (hopefully you) tried to create an ArchitectureScope account with this email, but you "
                    "already have one. Sign in instead, or use 'Forgot password' to set a new password.\n\n" + _footer()
                ),
            )
        )
        return
    _issue(
        db,
        mailer,
        pepper,
        email=email,
        purpose=PURPOSE_SIGNUP,
        payload={"name": name.strip()[:200], "password_hash": hash_password(password)},
        subject="Your ArchitectureScope verification code",
        intro=f"Hi {name.strip() or 'there'}, confirm your email to finish creating your ArchitectureScope account.",
    )


def resend_signup(db: Session, mailer: Mailer, pepper: str, *, email: str) -> None:
    email = _norm(email)
    if db.get(EmailCode, (email, PURPOSE_SIGNUP)) is None:
        return  # nothing pending (or already confirmed) — don't reveal which
    _issue(
        db,
        mailer,
        pepper,
        email=email,
        purpose=PURPOSE_SIGNUP,
        payload={},
        subject="Your ArchitectureScope verification code",
        intro="Here's a new code to finish creating your ArchitectureScope account.",
    )


def _workspace_for(db: Session, email: str, name: str) -> tuple[Workspace, str]:
    domain = email.split("@", 1)[1]
    for workspace in db.scalars(select(Workspace).order_by(Workspace.created_at)):
        if domain in {d.lower() for d in workspace.signup_domains or []}:
            return workspace, ROLE_MEMBER
    workspace = Workspace(name=f"{name or email.split('@')[0]}'s workspace", signup_domains=[])
    db.add(workspace)
    db.flush()
    return workspace, ROLE_OWNER


def verify_signup(
    db: Session, pepper: str, *, email: str, code: str, session_days: int, user_agent: str = ""
) -> tuple[str, Principal]:
    """Confirm the code, create the account, and sign the new user in."""
    email = _norm(email)
    record = _consume(db, pepper, email=email, purpose=PURPOSE_SIGNUP, code=code)
    if db.scalar(select(User).where(User.email == email)) is not None:
        db.delete(record)
        raise Conflict("This email already has an account. Sign in instead.")
    name = str(record.payload.get("name") or "")
    workspace, role = _workspace_for(db, email, name)
    user = User(email=email, name=name, password_hash=str(record.payload["password_hash"]))
    db.add(user)
    db.flush()
    db.add(Membership(user_id=user.id, workspace_id=workspace.id, role=role))
    db.delete(record)
    db.flush()
    db.refresh(user)
    return start_session(db, user, session_days=session_days, user_agent=user_agent)


# ---- Password reset ---------------------------------------------------------------


def request_reset(db: Session, mailer: Mailer, pepper: str, *, email: str) -> None:
    email = _norm(email)
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not user.is_active:
        return
    _issue(
        db,
        mailer,
        pepper,
        email=email,
        purpose=PURPOSE_RESET,
        payload={},
        subject="Reset your ArchitectureScope password",
        intro="Use this code to set a new ArchitectureScope password.",
    )


def confirm_reset(
    db: Session, pepper: str, *, email: str, code: str, password: str, session_days: int, user_agent: str = ""
) -> tuple[str, Principal]:
    """Set the new password, sign out every other session, and sign in here."""
    email = _norm(email)
    check_password(password, email)
    record = _consume(db, pepper, email=email, purpose=PURPOSE_RESET, code=code)
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        raise InvalidCode("That code has expired. Ask for a new one.")
    user.password_hash = hash_password(password)
    clear_failed_sign_ins(user.email)
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    db.delete(record)
    db.flush()
    return start_session(db, user, session_days=session_days, user_agent=user_agent)


def set_signup_domains(db: Session, workspace_name: str, domains: list[str]) -> Workspace:
    """Which email domains join ``workspace_name`` when they sign up (admin CLI)."""
    workspace = db.scalar(select(Workspace).where(Workspace.name == workspace_name))
    if workspace is None:
        raise Conflict(f"No workspace named '{workspace_name}'.")
    workspace.signup_domains = sorted({d.strip().lower().lstrip("@") for d in domains if d.strip()})
    db.flush()
    return workspace
