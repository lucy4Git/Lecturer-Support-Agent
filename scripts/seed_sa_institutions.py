"""
Seed South African public higher education institutions into tenant.institutions.

Data sourced from the Department of Higher Education and Training (DHET)
official list of registered public higher education institutions.

Run against staging via Railway:
    railway run --service lsa-staging-api python scripts/seed_sa_institutions.py

Reads MIGRATION_DATABASE_URL (preferred) or DATABASE_URL.
Idempotent — ON CONFLICT (slug) DO UPDATE preserves the row if it already exists.
"""
from __future__ import annotations

import json
import os
import sys
import uuid

# ---------------------------------------------------------------------------
# Authoritative list of South African public higher education institutions
# Source: DHET — www.dhet.gov.za — registered public HEIs
# ---------------------------------------------------------------------------
SA_INSTITUTIONS = [
    # Universities of Technology
    {"display_name": "Cape Peninsula University of Technology",          "slug": "cput",       "institution_type": "university_of_technology",       "domains": ["cput.ac.za"]},
    {"display_name": "Central University of Technology, Free State",     "slug": "cut",        "institution_type": "university_of_technology",       "domains": ["cut.ac.za"]},
    {"display_name": "Durban University of Technology",                  "slug": "dut",        "institution_type": "university_of_technology",       "domains": ["dut.ac.za"]},
    {"display_name": "Mangosuthu University of Technology",              "slug": "mut",        "institution_type": "university_of_technology",       "domains": ["mut.ac.za"]},
    {"display_name": "Tshwane University of Technology",                 "slug": "tut",        "institution_type": "university_of_technology",       "domains": ["tut.ac.za"]},
    {"display_name": "Vaal University of Technology",                    "slug": "vut",        "institution_type": "university_of_technology",       "domains": ["vut.ac.za"]},
    # Comprehensive universities
    {"display_name": "Nelson Mandela University",                        "slug": "nmu",        "institution_type": "comprehensive_university",       "domains": ["mandela.ac.za"]},
    {"display_name": "North-West University",                            "slug": "nwu",        "institution_type": "comprehensive_university",       "domains": ["nwu.ac.za"]},
    {"display_name": "University of Johannesburg",                       "slug": "uj",         "institution_type": "comprehensive_university",       "domains": ["uj.ac.za"]},
    {"display_name": "University of Limpopo",                            "slug": "ul",         "institution_type": "comprehensive_university",       "domains": ["ul.ac.za"]},
    {"display_name": "University of Mpumalanga",                         "slug": "ump",        "institution_type": "comprehensive_university",       "domains": ["ump.ac.za"]},
    {"display_name": "University of the Western Cape",                   "slug": "uwc",        "institution_type": "comprehensive_university",       "domains": ["uwc.ac.za"]},
    {"display_name": "University of Venda",                              "slug": "univen",     "institution_type": "comprehensive_university",       "domains": ["univen.ac.za"]},
    {"display_name": "University of Zululand",                           "slug": "unizulu",    "institution_type": "comprehensive_university",       "domains": ["unizulu.ac.za"]},
    {"display_name": "Walter Sisulu University",                         "slug": "wsu",        "institution_type": "comprehensive_university",       "domains": ["wsu.ac.za"]},
    # Traditional universities
    {"display_name": "Rhodes University",                                "slug": "ru",         "institution_type": "traditional_university",         "domains": ["ru.ac.za"]},
    {"display_name": "Sol Plaatje University",                           "slug": "spu",        "institution_type": "traditional_university",         "domains": ["spu.ac.za"]},
    {"display_name": "Stellenbosch University",                          "slug": "sun",        "institution_type": "traditional_university",         "domains": ["sun.ac.za", "stellenbosch.ac.za"]},
    {"display_name": "University of Cape Town",                          "slug": "uct",        "institution_type": "traditional_university",         "domains": ["uct.ac.za"]},
    {"display_name": "University of Fort Hare",                          "slug": "ufh",        "institution_type": "traditional_university",         "domains": ["ufh.ac.za"]},
    {"display_name": "University of KwaZulu-Natal",                      "slug": "ukzn",       "institution_type": "traditional_university",         "domains": ["ukzn.ac.za"]},
    {"display_name": "University of Pretoria",                           "slug": "up",         "institution_type": "traditional_university",         "domains": ["up.ac.za"]},
    {"display_name": "University of the Free State",                     "slug": "ufs",        "institution_type": "traditional_university",         "domains": ["ufs.ac.za"]},
    {"display_name": "University of the Witwatersrand",                  "slug": "wits",       "institution_type": "traditional_university",         "domains": ["wits.ac.za"]},
    # Specialist / distance
    {"display_name": "Sefako Makgatho Health Sciences University",       "slug": "smu",        "institution_type": "specialist_university",          "domains": ["smu.ac.za"]},
    {"display_name": "University of South Africa",                       "slug": "unisa",      "institution_type": "distance_education_university",  "domains": ["unisa.ac.za"]},
]


def seed(database_url: str) -> None:
    try:
        import psycopg
    except ImportError:
        import psycopg2 as psycopg  # type: ignore[no-redef]

    # psycopg3 async not needed — use sync here for simplicity
    clean_url = database_url.replace("postgresql+psycopg://", "postgresql://").replace("postgresql+asyncpg://", "postgresql://")

    with psycopg.connect(clean_url) as conn:
        with conn.transaction():
            inserted = 0
            updated = 0
            for data in SA_INSTITUTIONS:
                inst_id = str(uuid.uuid4())
                config = {
                    "email_domains": data.get("domains", []),
                    "jurisdiction": "ZA",
                    "regulatory_body": "CHE",
                    "qualification_framework": "NQF",
                }
                conn.execute(
                    """
                    INSERT INTO tenant.institutions
                        (id, slug, legal_name, display_name, institution_type,
                         country_code, default_timezone, default_locale,
                         is_active, configuration)
                    VALUES
                        (%s, %s, %s, %s, %s, 'ZA', 'Africa/Johannesburg', 'en',
                         TRUE, %s::jsonb)
                    ON CONFLICT (slug) DO UPDATE
                        SET display_name    = EXCLUDED.display_name,
                            institution_type = EXCLUDED.institution_type,
                            is_active       = TRUE,
                            configuration   = EXCLUDED.configuration
                    """,
                    (
                        inst_id,
                        data["slug"],
                        data["display_name"],
                        data["display_name"],
                        data["institution_type"],
                        json.dumps(config),
                    ),
                )
                inserted += 1

    print(f"SA institutions seed complete: {inserted} rows upserted (new or updated).")


if __name__ == "__main__":
    url = (
        os.environ.get("MIGRATION_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
        or os.environ.get("STAGING_DATABASE_URL")
    )
    if not url:
        print("ERROR: Set MIGRATION_DATABASE_URL, DATABASE_URL, or STAGING_DATABASE_URL.")
        sys.exit(1)
    seed(url)
