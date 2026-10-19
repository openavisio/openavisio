"""Operator: hand a household's Household Manager role to another member (#351, ADR 052).

Only when the manager is gone for good and the contract holder is proven. Touches roles only.

    docker compose exec -T backend uv run python -m app.scripts.transfer_manager <email of the new manager>
"""

import asyncio
import sys

from sqlalchemy import func, select

from app.core.database import AsyncSessionLocal
from app.models.user import User
from app.services.household import transfer_manager


async def main(email: str) -> None:
    async with AsyncSessionLocal() as db:
        to = (await db.execute(select(User).where(func.lower(User.email) == email.lower()))).scalar_one_or_none()
        if not to:
            sys.exit(f"No member with {email}.")
        try:
            old = await transfer_manager(db, to, by_name="operator")
        except ValueError as e:
            sys.exit(str(e))
        print(f"Household Manager: {old.email} -> {to.email}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    asyncio.run(main(sys.argv[1]))
