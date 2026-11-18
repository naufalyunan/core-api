"""Seed demo organizations, users and drillholes.

Run: `uv run python -m scripts.seed` (creates missing tables first).

Reads:
  - data/seed/organizations_users.json      organizations and their users
  - data/seed/drillholes_<slug>.csv         drillholes per organization
                                            (slug "red-ridge" -> drillholes_red_ridge.csv)

Idempotent: rows that already exist are skipped (orgs by slug, users by email,
drillholes by organization + hole_id), so it is safe to run again. Everything is
written in one transaction: if any row is invalid, nothing is saved.
"""

import asyncio
import csv
import json
from collections import Counter
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.init_db import create_tables
from app.db.models import Drillhole, Organization, Role, User
from app.db.session import SessionLocal, engine
from app.repositories.drillhole import DrillholeRepository
from app.repositories.user import UserRepository
from app.schemas.drillhole import DrillholeCreate

SEED_DIR = Path(__file__).resolve().parent.parent / "data" / "seed"
stats: Counter[str] = Counter()  # e.g. stats["users created"] += 1


async def get_or_create_org(session: AsyncSession, name: str, slug: str) -> Organization:
    """Get an existing organization by slug, or create it if it doesn't exist."""
    org = await session.scalar(select(Organization).where(Organization.slug == slug))
    if org is not None:
        stats["orgs skipped"] += 1
        return org

    org = Organization(name=name, slug=slug)
    session.add(org)
    await session.flush()  # send the INSERT now so org.id is available for its users
    stats["orgs created"] += 1
    return org


async def create_user_if_missing(
    session: AsyncSession, org: Organization, email: str, password: str, role: Role
) -> None:
    """Create a user unless the email is already taken (an existing user is never changed)."""
    if await UserRepository(session).get_by_email(email):
        stats["users skipped"] += 1
        return

    session.add(
        User(
            organization_id=org.id,
            email=email.lower(),
            hashed_password=hash_password(password),
            role=role,
        )
    )
    stats["users created"] += 1


def read_csv_rows(csv_path: Path) -> list[dict[str, str]] | None:
    """Plain (sync) file reading, kept out of the async functions. None if the file is missing."""
    if not csv_path.exists():
        return None
    with csv_path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


async def seed_drillholes(session: AsyncSession, org: Organization, csv_path: Path) -> None:
    """Read a CSV file and create the missing Drillhole rows for the given organization."""
    rows = read_csv_rows(csv_path)
    if rows is None:
        print(f"CSV file {csv_path} does not exist, skipping drillhole seeding for {org.name}")
        return

    repo = DrillholeRepository(session)
    for row in rows:
        data = DrillholeCreate.model_validate(row)  # same validation as POST /drillholes
        if await repo.get_by_hole_id(org.id, data.hole_id):
            stats["drillholes skipped"] += 1
            continue
        repo.add(Drillhole(organization_id=org.id, **data.model_dump()))
        stats["drillholes created"] += 1


async def main() -> None:
    await create_tables(engine)
    data = json.loads((SEED_DIR / "organizations_users.json").read_text())

    async with SessionLocal() as session:
        for org_data in data["organizations"]:
            org = await get_or_create_org(session, org_data["name"], org_data["slug"])
            for u in org_data["users"]:
                await create_user_if_missing(
                    session, org, u["email"], u["password"], Role(u["role"])
                )
            csv_name = f"drillholes_{org.slug.replace('-', '_')}.csv"
            await seed_drillholes(session, org, SEED_DIR / csv_name)
        await session.commit()

    await engine.dispose()
    for key, count in sorted(stats.items()):
        print(f"{key}: {count}")


if __name__ == "__main__":
    asyncio.run(main())
