"""
Seed South African higher education institutions.

Data sourced from the Department of Higher Education and Training (DHET)
official list of registered public higher education institutions.

Run once against a staging or local database:
    python scripts/seed_sa_institutions.py

This script is idempotent — it skips institutions that already exist
(matched by slug).
"""
from __future__ import annotations

import asyncio
import os
import sys
from uuid import uuid4

# Allow running from repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ---------------------------------------------------------------------------
# Authoritative list of South African public higher education institutions
# Source: DHET — www.dhet.gov.za — registered public HEIs
# ---------------------------------------------------------------------------
SA_INSTITUTIONS = [
    # Universities (comprehensive, research, university of technology)
    {"display_name": "Cape Peninsula University of Technology", "slug": "cput", "institution_type": "university_of_technology", "country": "ZA", "domains": ["cput.ac.za"]},
    {"display_name": "Central University of Technology, Free State", "slug": "cut-freestate", "institution_type": "university_of_technology", "country": "ZA", "domains": ["cut.ac.za"]},
    {"display_name": "Durban University of Technology", "slug": "dut", "institution_type": "university_of_technology", "country": "ZA", "domains": ["dut.ac.za"]},
    {"display_name": "Mangosuthu University of Technology", "slug": "mut", "institution_type": "university_of_technology", "country": "ZA", "domains": ["mut.ac.za"]},
    {"display_name": "Nelson Mandela University", "slug": "nmu", "institution_type": "comprehensive_university", "country": "ZA", "domains": ["mandela.ac.za"]},
    {"display_name": "North-West University", "slug": "nwu", "institution_type": "comprehensive_university", "country": "ZA", "domains": ["nwu.ac.za"]},
    {"display_name": "Rhodes University", "slug": "ru", "institution_type": "traditional_university", "country": "ZA", "domains": ["ru.ac.za"]},
    {"display_name": "Sefako Makgatho Health Sciences University", "slug": "smu", "institution_type": "specialist_university", "country": "ZA", "domains": ["smu.ac.za"]},
    {"display_name": "Sol Plaatje University", "slug": "spu", "institution_type": "traditional_university", "country": "ZA", "domains": ["spu.ac.za"]},
    {"display_name": "Stellenbosch University", "slug": "sun", "institution_type": "traditional_university", "country": "ZA", "domains": ["sun.ac.za", "stellenbosch.ac.za"]},
    {"display_name": "Tshwane University of Technology", "slug": "tut", "institution_type": "university_of_technology", "country": "ZA", "domains": ["tut.ac.za"]},
    {"display_name": "University of Cape Town", "slug": "uct", "institution_type": "traditional_university", "country": "ZA", "domains": ["uct.ac.za"]},
    {"display_name": "University of Fort Hare", "slug": "ufh", "institution_type": "traditional_university", "country": "ZA", "domains": ["ufh.ac.za"]},
    {"display_name": "University of Johannesburg", "slug": "uj", "institution_type": "comprehensive_university", "country": "ZA", "domains": ["uj.ac.za"]},
    {"display_name": "University of KwaZulu-Natal", "slug": "ukzn", "institution_type": "traditional_university", "country": "ZA", "domains": ["ukzn.ac.za"]},
    {"display_name": "University of Limpopo", "slug": "ul", "institution_type": "comprehensive_university", "country": "ZA", "domains": ["ul.ac.za"]},
    {"display_name": "University of Mpumalanga", "slug": "ump", "institution_type": "comprehensive_university", "country": "ZA", "domains": ["ump.ac.za"]},
    {"display_name": "University of Pretoria", "slug": "up", "institution_type": "traditional_university", "country": "ZA", "domains": ["up.ac.za"]},
    {"display_name": "University of South Africa", "slug": "unisa", "institution_type": "distance_education_university", "country": "ZA", "domains": ["unisa.ac.za"]},
    {"display_name": "University of the Free State", "slug": "ufs", "institution_type": "traditional_university", "country": "ZA", "domains": ["ufs.ac.za"]},
    {"display_name": "University of the Western Cape", "slug": "uwc", "institution_type": "comprehensive_university", "country": "ZA", "domains": ["uwc.ac.za"]},
    {"display_name": "University of the Witwatersrand", "slug": "wits", "institution_type": "traditional_university", "country": "ZA", "domains": ["wits.ac.za"]},
    {"display_name": "University of Venda", "slug": "univen", "institution_type": "comprehensive_university", "country": "ZA", "domains": ["univen.ac.za"]},
    {"display_name": "University of Zululand", "slug": "unizulu", "institution_type": "comprehensive_university", "country": "ZA", "domains": ["unizulu.ac.za"]},
    {"display_name": "Vaal University of Technology", "slug": "vut", "institution_type": "university_of_technology", "country": "ZA", "domains": ["vut.ac.za"]},
    {"display_name": "Walter Sisulu University", "slug": "wsu", "institution_type": "comprehensive_university", "country": "ZA", "domains": ["wsu.ac.za"]},
]


async def seed(database_url: str) -> None:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with factory() as session:
        async with session.begin():
            # Bypass RLS for seed operation
            await session.execute(text("SET LOCAL app.tenant_id = '00000000-0000-0000-0000-000000000000'"))
            await session.execute(text("SET LOCAL app.user_id = '00000000-0000-0000-0000-000000000000'"))
            await session.execute(text("SET LOCAL app.role_code = 'system'"))

            from services.database.models.tenancy import Institution  # noqa: PLC0415

            inserted = 0
            skipped = 0
            for data in SA_INSTITUTIONS:
                existing = await session.scalar(
                    select(Institution).where(Institution.slug == data["slug"])
                )
                if existing:
                    skipped += 1
                    continue
                inst = Institution(
                    id=uuid4(),
                    display_name=data["display_name"],
                    slug=data["slug"],
                    institution_type=data.get("institution_type", "traditional_university"),
                    country=data.get("country", "ZA"),
                    status="active",
                    configuration={
                        "email_domains": data.get("domains", []),
                        "jurisdiction": "ZA",
                        "regulatory_body": "CHE",
                        "qualification_framework": "NQF",
                    },
                )
                session.add(inst)
                inserted += 1

    print(f"SA institutions seed complete: {inserted} inserted, {skipped} already present.")
    await engine.dispose()


if __name__ == "__main__":
    url = os.environ.get("DATABASE_URL") or os.environ.get("STAGING_DATABASE_URL")
    if not url:
        print("ERROR: Set DATABASE_URL or STAGING_DATABASE_URL environment variable.")
        sys.exit(1)
    asyncio.run(seed(url))
