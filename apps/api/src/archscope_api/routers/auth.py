"""Sign-in, self sign-up, and password reset. Mounted outside the
authenticated ``/api/v1`` router (at the same prefix) so these endpoints
work without a session.

The session lives in an HttpOnly, SameSite=Lax cookie (Secure outside
local development), so scripts can't read it and other sites can't use
it; only a hash of its token is stored. Sign-up and reset are confirmed
with a 6-digit code sent by email.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from ..mail import Mailer
from ..schemas.workspace import (
    Accepted,
    Account,
    AuthConfig,
    CodeConfirm,
    EmailOnly,
    Me,
    PasswordChange,
    PasswordResetConfirm,
    ProfileUpdate,
    SignedOutOthers,
    SignInRequest,
    SignUpRequest,
)
from ..services import account, auth, signup
from ..services.auth import Principal
from ..services.errors import Forbidden, Unavailable
from ..settings import Settings
from .deps import CodePepperDep, DbDep, MailerDep, PrincipalDep, SettingsDep

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

CHECK_EMAIL = "If that address can receive email, a 6-digit code is on its way. It expires in 15 minutes."


def _me(principal: Principal) -> Me:
    return Me(
        user_id=principal.user_id,
        email=principal.email,
        name=principal.name,
        workspace_id=principal.workspace_id,
        workspace_name=principal.workspace_name,
        role=principal.role,
        is_admin=principal.is_admin,
    )


def _set_session(response: Response, settings: Settings, token: str) -> None:
    response.set_cookie(
        settings.session_cookie,
        token,
        max_age=settings.session_days * 24 * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def _require_mail(mailer: Mailer | None) -> Mailer:
    if mailer is None:
        raise Unavailable("Email isn't configured on this server, so accounts are created by an admin.")
    return mailer


@router.get("/config", response_model=AuthConfig, summary="Sign-in methods offered")
def config(settings: SettingsDep) -> AuthConfig:
    can_email = settings.email_delivery != "none"
    return AuthConfig(
        password=True,
        google=settings.google_enabled,
        signup=settings.signup_enabled and can_email,
        password_reset=can_email,
        email_delivery=settings.email_delivery,
        min_password_length=signup.MIN_PASSWORD,
    )


@router.post("/sign-in", response_model=Me, summary="Sign in with email and password")
def sign_in(body: SignInRequest, request: Request, response: Response, db: DbDep, settings: SettingsDep) -> Me:
    token, principal = auth.sign_in(
        db, body.email, body.password, session_days=settings.session_days, user_agent=request.headers.get("user-agent", "")
    )
    _set_session(response, settings, token)
    return _me(principal)


@router.post("/sign-out", status_code=204, summary="Sign out of this browser")
def sign_out(request: Request, db: DbDep, settings: SettingsDep) -> Response:
    auth.sign_out(db, request.cookies.get(settings.session_cookie))
    response = Response(status_code=204)
    response.delete_cookie(settings.session_cookie, path="/")
    return response


@router.get("/me", response_model=Me, summary="The signed-in user")
def me(principal: PrincipalDep) -> Me:
    return _me(principal)


# ---- Your account (profile page) -------------------------------------------------


def _account(result: account.Account, principal: Principal) -> Account:
    return Account(
        user_id=result.user.id,
        email=result.user.email,
        name=result.user.name,
        workspace_name=principal.workspace_name,
        role=principal.role,
        has_password=result.has_password,
        created_at=result.user.created_at,
        last_login_at=result.user.last_login_at,
        other_sessions=result.other_sessions,
    )


@router.get("/account", response_model=Account, summary="Your account")
def get_account(request: Request, principal: PrincipalDep, db: DbDep, settings: SettingsDep) -> Account:
    return _account(account.get_account(db, principal, request.cookies.get(settings.session_cookie)), principal)


@router.patch("/account", response_model=Account, summary="Change your display name")
def update_account(body: ProfileUpdate, request: Request, principal: PrincipalDep, db: DbDep, settings: SettingsDep) -> Account:
    token = request.cookies.get(settings.session_cookie)
    return _account(account.update_profile(db, principal, name=body.name, current_token=token), principal)


@router.post("/account/password", response_model=Account, summary="Change your password (signs out your other browsers)")
def change_password(body: PasswordChange, request: Request, principal: PrincipalDep, db: DbDep, settings: SettingsDep) -> Account:
    result = account.change_password(
        db,
        principal,
        current_password=body.current_password,
        new_password=body.new_password,
        current_token=request.cookies.get(settings.session_cookie),
    )
    return _account(result, principal)


@router.post("/account/sign-out-others", response_model=SignedOutOthers, summary="Sign out every other browser")
def sign_out_others(request: Request, principal: PrincipalDep, db: DbDep, settings: SettingsDep) -> SignedOutOthers:
    return SignedOutOthers(signed_out=account.sign_out_others(db, principal, request.cookies.get(settings.session_cookie)))


# ---- Self sign-up -----------------------------------------------------------------


@router.post("/sign-up", response_model=Accepted, status_code=202, summary="Start creating an account (emails a code)")
def sign_up(body: SignUpRequest, db: DbDep, mailer: MailerDep, pepper: CodePepperDep, settings: SettingsDep) -> Accepted:
    if not settings.signup_enabled:
        raise Unavailable("Self sign-up is turned off. Ask an admin for an account.")
    allowed = settings.signup_domains_allowed
    if allowed and body.email.rsplit("@", 1)[-1].strip().lower() not in allowed:
        raise Forbidden(f"Accounts can only be created with a {' or '.join('@' + d for d in allowed)} email.")
    signup.request_signup(db, _require_mail(mailer), pepper, email=body.email, name=body.name, password=body.password)
    return Accepted(message=CHECK_EMAIL)


@router.post("/sign-up/resend", response_model=Accepted, status_code=202, summary="Send a new sign-up code")
def resend(body: EmailOnly, db: DbDep, mailer: MailerDep, pepper: CodePepperDep) -> Accepted:
    signup.resend_signup(db, _require_mail(mailer), pepper, email=body.email)
    return Accepted(message=CHECK_EMAIL)


@router.post("/sign-up/verify", response_model=Me, summary="Confirm the emailed code; creates the account and signs in")
def verify(
    body: CodeConfirm, request: Request, response: Response, db: DbDep, pepper: CodePepperDep, settings: SettingsDep
) -> Me:
    token, principal = signup.verify_signup(
        db,
        pepper,
        email=body.email,
        code=body.code,
        session_days=settings.session_days,
        user_agent=request.headers.get("user-agent", ""),
    )
    _set_session(response, settings, token)
    return _me(principal)


# ---- Password reset -------------------------------------------------------------------


@router.post("/password-reset", response_model=Accepted, status_code=202, summary="Email a password-reset code")
def password_reset(body: EmailOnly, db: DbDep, mailer: MailerDep, pepper: CodePepperDep) -> Accepted:
    signup.request_reset(db, _require_mail(mailer), pepper, email=body.email)
    return Accepted(message=CHECK_EMAIL)


@router.post("/password-reset/confirm", response_model=Me, summary="Set a new password with the emailed code; signs in")
def password_reset_confirm(
    body: PasswordResetConfirm, request: Request, response: Response, db: DbDep, pepper: CodePepperDep, settings: SettingsDep
) -> Me:
    token, principal = signup.confirm_reset(
        db,
        pepper,
        email=body.email,
        code=body.code,
        password=body.password,
        session_days=settings.session_days,
        user_agent=request.headers.get("user-agent", ""),
    )
    _set_session(response, settings, token)
    return _me(principal)
