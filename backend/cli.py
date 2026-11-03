"""
OpenAvisio management CLI.

Usage:
    uv run python cli.py <command> [args]

Commands:
    changepassword <email>          Interactively reset a user's password
    changepassword <email> <pw>     Reset to a given password (non-interactive)
    createuser <email> <role>       Create a new user (prompts for password)
    listusers                       List all users
    license <file>                  Install a License file (.lic); refuses one that does not
                                    verify, then prints what the instance now runs under.
                                    The way in on a hosted Deployment, whose license
                                    routes are operator-only
    reembed                         Queue every chunk not embedded by the configured
                                    embedding model for a new embedding (#238);
                                    run again to pick up what is left
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


async def cmd_reembed():
    import httpx
    from sqlalchemy import or_, select
    from app.core.config import settings
    from app.core.database import AsyncSessionLocal
    from app.models.chat import DocumentChunk
    from app.workers.pipeline import embedding_stage
    from app.workers.scheduler import diary_embedding_job

    async with httpx.AsyncClient(timeout=10, headers=settings.ai_service_headers) as client:
        resp = await client.get(f"{settings.ai_service_url}/models")
        resp.raise_for_status()
        model = resp.json().get("embed_model")
    if not model:
        print("The AI service names no embedding model.", file=sys.stderr)
        sys.exit(1)

    stale = (DocumentChunk.is_deleted == False) & or_(  # noqa: E712
        DocumentChunk.embedding_model.is_(None), DocumentChunk.embedding_model != model,
    )
    async with AsyncSessionLocal() as db:
        docs = (await db.execute(select(DocumentChunk.document_reference_id).where(
            stale, DocumentChunk.document_reference_id.is_not(None)).distinct())).scalars().all()
        entries = (await db.execute(select(DocumentChunk.diary_entry_id).where(
            stale, DocumentChunk.diary_entry_id.is_not(None)).distinct())).scalars().all()

    # the gpu queue runs them one by one and backs off while the AI service is busy
    for doc_id in docs:
        embedding_stage.delay(str(doc_id), quiet=True)
    for entry_id in entries:
        diary_embedding_job.delay(str(entry_id))
    print(f"Queued {len(docs)} documents and {len(entries)} diary entries for {model}.")


async def cmd_license(path: str):
    from app.core.config import settings
    from app.services.license import install_license

    with open(path) as f:
        token = f.read()
    async with (await _session()) as db:
        try:
            info = await install_license(db, token, settings.license_public_key)
        except ValueError as exc:
            print(f"License refused: {exc}", file=sys.stderr)
            sys.exit(1)
    print(f"Tier {info.tier.value}, issued to {info.issued_to}, expires {info.expires_at:%Y-%m-%d}.")


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

    elif cmd == "license":
        if len(args) < 2:
            print("Usage: cli.py license <file>", file=sys.stderr)
            sys.exit(1)
        asyncio.run(cmd_license(args[1]))

    elif cmd == "reembed":
        asyncio.run(cmd_reembed())

    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
