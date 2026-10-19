"""Operator: a fresh recovery code for a member who lost password, passkey and code (ADR 044).

Only after the identity is proven. Hand the code over by phone or letter, never into the mailbox
the request came from. The member sets a new password with it under "Passwort und Passkey
verloren?"; the operator never learns the password.

    docker compose exec -T backend uv run python -m app.scripts.new_recovery_code <email>
"""

import asyncio
import sys
from datetime import UTC, datetime

from sqlalchemy import func, select

from app.core.database import AsyncSessionLocal
from app.core.security import generate_recovery_code, hash_password, normalize_recovery_code
from app.models.audit import AuditLog
from app.models.user import User


async def main(email: str) -> str:
    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(
            func.lower(User.email) == email.lower(), User.is_deleted == False))).scalar_one_or_none()  # noqa: E712
        if not user or not user.is_active:
            sys.exit(f"No active member with {email}.")
        code = generate_recovery_code()
        user.recovery_code_hash = hash_password(normalize_recovery_code(code))
        user.failed_login_attempts = 0
        user.locked_until = None
        db.add(AuditLog(timestamp=datetime.now(UTC), user_name="operator", entity_type="User",
                        entity_id=str(user.id), action="recovery_reissued"))
        await db.commit()
        return code


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    print(asyncio.run(main(sys.argv[1])))
