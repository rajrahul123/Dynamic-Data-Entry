"""Create the initial administrator account.

Usage (from the ``backend`` directory, with the virtual environment active):

    python scripts/create_admin.py
    python scripts/create_admin.py --username alice --email alice@example.com
    python scripts/create_admin.py --username alice --password 's3cret!'

Credentials can be supplied interactively (prompts, password masked) or via
CLI arguments. The script fails without writing anything if the username or
email already exists, so running it twice never creates a duplicate admin.

Role defaults to ``admin``; pass ``--role operator|viewer`` to instead create a
non-admin account (useful for seeding additional accounts later).
"""

import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models import Role, User  # noqa: E402
from sqlalchemy import select  # noqa: E402

VALID_ROLES = [role.value for role in Role]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create an initial admin account.")
    parser.add_argument("--username", help="Username (skips interactive prompt).")
    parser.add_argument("--email", help="Email address (skips interactive prompt).")
    parser.add_argument("--full-name", help="Full name (skips interactive prompt).")
    parser.add_argument("--password", help="Password (skips masked prompts).")
    parser.add_argument(
        "--role",
        choices=VALID_ROLES,
        default=Role.admin.value,
        help="Role for the new account (default: admin).",
    )
    return parser.parse_args()


def _prompt(question: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{question}{suffix}: ").strip()
    return value or default or ""


def main() -> int:
    settings = get_settings()
    args = _parse_args()

    username = args.username or _prompt("Username")
    email = args.email or _prompt("Email")
    full_name = args.full_name or _prompt("Full name (optional)", default="") or None

    password = args.password
    if not password:
        password = getpass.getpass("Password: ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Error: passwords do not match", file=sys.stderr)
            return 1

    if not (username and email and password):
        print("Error: username, email, and password are required", file=sys.stderr)
        return 1

    with SessionLocal() as db:
        existing = db.scalar(
            select(User).where(
                (User.username == username) | (User.email == email)
            )
        )
        if existing is not None:
            print(
                f"Error: a user already exists with this username/email "
                f"(username={existing.username!r}). No changes were made.",
                file=sys.stderr,
            )
            return 1

        role = Role(args.role)
        user = User(
            username=username,
            email=email,
            full_name=full_name,
            password_hash=hash_password(password),
            role=role,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    print(f"Created user {user.username!r} (id={user.id}) with role {role.value!r}.")
    print(f"Environment: {settings.environment}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())