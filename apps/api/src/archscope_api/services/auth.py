"""Accounts and sign-in sessions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..persistence.models import ROLE_ADMIN, ROLE_MEMBER, ROLE_OWNER, ROLES, AuthSession, Membership, User, Workspace
from ..persistence.security import hash_password, new_session_token, token_id, verify_password
from .errors import Conflict, Forbidden, NotSignedIn, SignInFailed

# How often a session's last-seen time is refreshed (avoids a write per request).
_TOUCH_EVERY = timedelta(minutes=5)


@dataclass(frozen=True)
class Principal:
    """The signed-in user, in the workspace their session is for."""

    user_id: str
    email: str
    name: str
    workspace_id: str
    workspace_name: str
    role: str

    @property
    def is_admin(self) -> bool:
        return self.role in (ROLE_OWNER, ROLE_ADMIN)


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _aware(moment: datetime) -> datetime:
    """SQLite returns naive datetimes; treat them as UTC."""
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def _principal(db: Session, user: User, workspace_id: str) -> Principal:
    membership = db.get(Membership, (user.id, workspace_id))
    if membership is None:
        raise Forbidden("You're not a member of this workspace.")
    return Principal(
        user_id=user.id,
        email=user.email,
        name=user.name,
        workspace_id=workspace_id,
        workspace_name=membership.workspace.name,
        role=membership.role,
    )


def start_session(db: Session, user: User, *, session_days: int, user_agent: str = "") -> tuple[str, Principal]:
    """Open a session in the user's first workspace; returns (cookie token, principal)."""
    if not user.is_active:
        raise SignInFailed("This account is disabled.")
    membership = next(iter(sorted(user.memberships, key=lambda m: m.workspace_id)), None)
    if membership is None:
        raise Forbidden("This account isn't in a workspace yet. Ask an admin to add you.")
    token = new_session_token()
    now = datetime.now(UTC)
    db.add(
        AuthSession(
            id=token_id(token),
            user_id=user.id,
            workspace_id=membership.workspace_id,
            created_at=now,
            expires_at=now + timedelta(days=session_days),
            last_seen_at=now,
            user_agent=user_agent[:300],
        )
    )
    user.last_login_at = now
    return token, _principal(db, user, membership.workspace_id)


def sign_in(db: Session, email: str, password: str, *, session_days: int, user_agent: str = "") -> tuple[str, Principal]:
    user = db.scalar(select(User).where(User.email == _normalize_email(email)))
    # Verify even when the user doesn't exist, so timing doesn't reveal which emails have accounts.
    valid = verify_password(password, user.password_hash if user else hash_password("timing-equalizer", iterations=1000))
    if user is None or not valid:
        raise SignInFailed()
    return start_session(db, user, session_days=session_days, user_agent=user_agent)


def principal_for_token(db: Session, token: str | None) -> Principal:
    """The principal for a session cookie, or :class:`NotSignedIn`."""
    if not token:
        raise NotSignedIn()
    session = db.get(AuthSession, token_id(token))
    now = datetime.now(UTC)
    if session is None or _aware(session.expires_at) <= now:
        raise NotSignedIn("Your session has expired. Sign in again.")
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise NotSignedIn()
    if now - _aware(session.last_seen_at) > _TOUCH_EVERY:
        session.last_seen_at = now
    return _principal(db, user, session.workspace_id)


def sign_out(db: Session, token: str | None) -> None:
    if token:
        db.execute(delete(AuthSession).where(AuthSession.id == token_id(token)))


def create_user(
    db: Session,
    *,
    email: str,
    name: str = "",
    password: str | None = None,
    workspace_name: str = "",
    workspace_id: str | None = None,
    role: str = ROLE_MEMBER,
) -> User:
    """Create a user and add them to a workspace (by id, or by name —
    created if it doesn't exist). Used by the admin CLI and Google sign-in."""
    if role not in ROLES:
        raise Conflict(f"Role must be one of {', '.join(ROLES)}.")
    email = _normalize_email(email)
    if db.scalar(select(User).where(User.email == email)) is not None:
        raise Conflict(f"A user with email {email} already exists.")
    workspace = db.get(Workspace, workspace_id) if workspace_id else None
    if workspace is None and workspace_name:
        workspace = db.scalar(select(Workspace).where(Workspace.name == workspace_name))
        if workspace is None:
            workspace = Workspace(name=workspace_name)
            db.add(workspace)
            db.flush()
    if workspace is None:
        raise Conflict("Give a workspace for the new user.")
    user = User(email=email, name=name.strip(), password_hash=hash_password(password) if password else None)
    db.add(user)
    db.flush()
    db.add(Membership(user_id=user.id, workspace_id=workspace.id, role=role))
    db.flush()
    db.refresh(user)
    return user


def set_password(db: Session, email: str, password: str) -> None:
    user = db.scalar(select(User).where(User.email == _normalize_email(email)))
    if user is None:
        raise Conflict(f"No user with email {email}.")
    user.password_hash = hash_password(password)
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
