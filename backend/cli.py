"""
OpenAvisio management CLI.

Usage:
    uv run python cli.py <command> [args]

Commands:
    changepassword <email>          Interactively reset a user's password
    changepassword <email> <pw>     Reset to a given password (non-interactive)
    createuser <email> <role>       Create a new user (prompts for password)
    listusers                       List all users
"""

import asyncio
import sys


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

async def _get_user(db, email: str):
    from sqlalchemy import select
    from app.models.user import User
    result = await db.execute(select(User).where(User.email == email, User.is_deleted == False))  # noqa: E712
    return result.scalar_one_or_none()


async def _session():
    from app.core.database import AsyncSessionLocal
    return AsyncSessionLocal()


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

async def cmd_changepassword(email: str, password: str | None = None):
    from app.core.security import hash_password

    if password is None:
        import getpass
        password = getpass.getpass(f"New password for {email}: ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Passwords do not match.", file=sys.stderr)
            sys.exit(1)

    if len(password) < 8:
        print("Password must be at least 8 characters.", file=sys.stderr)
        sys.exit(1)

    async with (await _session()) as db:
        user = await _get_user(db, email)
        if not user:
            print(f"No user found with email: {email}", file=sys.stderr)
            sys.exit(1)
        user.hashed_password = hash_password(password)
        user.failed_login_attempts = 0
        user.locked_until = None
        await db.commit()
        print(f"Password updated for {user.email} (role={user.role})")


async def cmd_createuser(email: str, role: str):
    import getpass
    from app.core.security import hash_password
    from app.models.user import User

    valid_roles = ("user", "manager", "admin")
    if role not in valid_roles:
        print(f"Invalid role '{role}'. Choose from: {', '.join(valid_roles)}", file=sys.stderr)
        sys.exit(1)

    password = getpass.getpass(f"Password for {email}: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords do not match.", file=sys.stderr)
        sys.exit(1)

    async with (await _session()) as db:
        existing = await _get_user(db, email)
        if existing:
            print(f"User already exists: {email}", file=sys.stderr)
            sys.exit(1)
        user = User(
            email=email,
            hashed_password=hash_password(password),
            role=role,
            is_active=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        print(f"Created user {user.email} (role={user.role}, id={user.id})")


async def cmd_listusers():
    from sqlalchemy import select
    from app.models.user import User
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.is_deleted == False).order_by(User.email))  # noqa: E712
        users = result.scalars().all()
        if not users:
            print("No users found.")
            return
        fmt = "{:<40} {:<10} {:<8} {}"
        print(fmt.format("EMAIL", "ROLE", "ACTIVE", "LAST LOGIN"))
        print("-" * 80)
        for u in users:
            last = u.last_login_at.strftime("%Y-%m-%d %H:%M") if u.last_login_at else "never"
            print(fmt.format(u.email, u.role, "yes" if u.is_active else "no", last))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(0)

    cmd = args[0]

    if cmd == "changepassword":
        if len(args) < 2:
            print("Usage: cli.py changepassword <email> [password]", file=sys.stderr)
            sys.exit(1)
        asyncio.run(cmd_changepassword(args[1], args[2] if len(args) > 2 else None))

    elif cmd == "createuser":
        if len(args) < 3:
            print("Usage: cli.py createuser <email> <role>", file=sys.stderr)
            sys.exit(1)
        asyncio.run(cmd_createuser(args[1], args[2]))

    elif cmd == "listusers":
        asyncio.run(cmd_listusers())

    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
