"""The signed-in user's own account: profile, password, other sessions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..persistence.models import AuthSession, User
from ..persistence.security import hash_password, token_id, verify_password
from .auth import Principal, clear_failed_sign_ins
from .errors import InvalidInput, NotSignedIn
from .signup import check_password


@dataclass(frozen=True)
class Account:
    user: User
    has_password: bool
    other_sessions: int


def _user(db: Session, principal: Principal) -> User:
    user = db.get(User, principal.user_id)
    if user is None:
        raise NotSignedIn()
    return user


def _other_sessions(db: Session, user_id: str, current_token: str | None) -> int:
    now = datetime.now(UTC)
    query = select(func.count()).select_from(AuthSession).where(AuthSession.user_id == user_id, AuthSession.expires_at > now)
    if current_token:
        query = query.where(AuthSession.id != token_id(current_token))
    return int(db.scalar(query) or 0)


def get_account(db: Session, principal: Principal, current_token: str | None) -> Account:
    user = _user(db, principal)
    return Account(user, bool(user.password_hash), _other_sessions(db, user.id, current_token))


def update_profile(db: Session, principal: Principal, *, name: str, current_token: str | None) -> Account:
    name = " ".join(name.split())
    if not name:
        raise InvalidInput("Your name can't be blank.")
    user = _user(db, principal)
    user.name = name[:200]
    db.flush()
    return get_account(db, principal, current_token)


def change_password(
    db: Session, principal: Principal, *, current_password: str, new_password: str, current_token: str | None
) -> Account:
    """Set a new password (the current one is required when there is one) and
    sign out every other browser; this one stays signed in."""
    user = _user(db, principal)
    if user.password_hash and not verify_password(current_password, user.password_hash):
        raise InvalidInput("Your current password is incorrect.")
    check_password(new_password, user.email)
    user.password_hash = hash_password(new_password)
    sign_out_others(db, principal, current_token)
    clear_failed_sign_ins(user.email)
    return get_account(db, principal, current_token)


def sign_out_others(db: Session, principal: Principal, current_token: str | None) -> int:
    """End every session of this user except the current one; returns how many ended."""
    query = delete(AuthSession).where(AuthSession.user_id == principal.user_id)
    if current_token:
        query = query.where(AuthSession.id != token_id(current_token))
    result = db.execute(query)
    return int(getattr(result, "rowcount", 0) or 0)
