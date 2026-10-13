"""Admin commands for the API.

    python -m archscope_api.cli migrate
    python -m archscope_api.cli create-user --email ana@sonamation.com --name "Ana" --workspace SonaMation --role owner
    python -m archscope_api.cli set-password --email ana@sonamation.com
    python -m archscope_api.cli secret-key          # a value for ARCHSCOPE_SECRET_KEY
    python -m archscope_api.cli signup-domains --workspace SonaMation sonamation.com   # who joins it on sign-up

Passwords are prompted for (never passed on the command line) unless
--password-stdin is given.
"""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

from .persistence.db import session_scope
from .persistence.models import ROLES
from .persistence.security import new_secret_key
from .services import auth, signup
from .services.errors import ServiceError
from .settings import Settings

MIGRATIONS = Path(__file__).resolve().parent / "migrations"


def alembic_config(database_url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def migrate(settings: Settings) -> None:
    """Bring the database schema up to date."""
    if settings.database_url.startswith("sqlite:///"):
        Path(settings.database_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    command.upgrade(alembic_config(settings.database_url), "head")


def _password(args: argparse.Namespace) -> str:
    if args.password_stdin:
        return sys.stdin.readline().rstrip("\n")
    first = getpass.getpass("Password: ")
    if first != getpass.getpass("Repeat password: "):
        raise SystemExit("Passwords don't match.")
    return first


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m archscope_api.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("migrate", help="apply database migrations")
    create = sub.add_parser("create-user", help="create a user (and their workspace if new)")
    create.add_argument("--email", required=True)
    create.add_argument("--name", default="")
    create.add_argument("--workspace", required=True, help="workspace name (created if it doesn't exist)")
    create.add_argument("--role", choices=ROLES, default="member")
    create.add_argument("--no-password", action="store_true", help="Google sign-in only")
    create.add_argument("--password-stdin", action="store_true")
    reset = sub.add_parser("set-password", help="set a user's password (signs them out everywhere)")
    reset.add_argument("--email", required=True)
    reset.add_argument("--password-stdin", action="store_true")
    sub.add_parser("secret-key", help="print a new value for ARCHSCOPE_SECRET_KEY")
    domains = sub.add_parser("signup-domains", help="email domains that join a workspace when they sign up")
    domains.add_argument("--workspace", required=True)
    domains.add_argument("domains", nargs="*", help="e.g. sonamation.com (none = clear)")
    args = parser.parse_args(argv)

    if args.command == "secret-key":
        print(new_secret_key())
        return 0
    settings = Settings()
    if args.command == "migrate":
        migrate(settings)
        print("Database is up to date.")
        return 0
    try:
        if args.command == "create-user":
            password = None if args.no_password else _password(args)
            with session_scope(settings.database_url) as db:
                user = auth.create_user(
                    db, email=args.email, name=args.name, password=password, workspace_name=args.workspace, role=args.role
                )
                print(f"Created {user.email} ({args.role}) in workspace '{args.workspace}'.")
        elif args.command == "signup-domains":
            with session_scope(settings.database_url) as db:
                workspace = signup.set_signup_domains(db, args.workspace, args.domains)
                print(f"'{workspace.name}' sign-up domains: {', '.join(workspace.signup_domains) or '(none)'}")
        elif args.command == "set-password":
            password = _password(args)
            with session_scope(settings.database_url) as db:
                auth.set_password(db, args.email, password)
                print(f"Password updated for {args.email}.")
    except ServiceError as exc:
        print(f"Error: {exc.detail or exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
