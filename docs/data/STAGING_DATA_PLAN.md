# Staging Data Plan

**Project:** Lecturer Support Agent  
**Version:** 2.5.1  
**Date:** 2026-08-03

## Objective

Staging reproduces a complete, governed environment using only:
- Synthetic institution and synthetic users
- Approved open datasets
- Clean Redis state
- Rebuilt Qdrant indexes from approved files

## Staging Datasets

| ID | Title | State |
|----|-------|-------|
| DS-003 | OpenStax Textbooks | APPROVED_FOR_STAGING |
| DS-004 | OpenAlex — Education | APPROVED_FOR_STAGING |
| DS-005 | Crossref Metadata | APPROVED_FOR_STAGING |
| DS-008 | UNESCO OER Guidelines | APPROVED_FOR_STAGING |
| DS-009 | Bloom's Taxonomy | APPROVED_FOR_STAGING |
| DS-010 | Synthetic Templates | APPROVED_FOR_STAGING |
| DS-011 | Citation Evaluation Corpus | APPROVED_FOR_STAGING |

## Synthetic Institution

- Institution code: `demo-north` (or `staging-north` for staging isolation)
- All eight synthetic roles seeded
- No real user data
- Credentials rotated on each staging deploy

## Staging Checklist

- [ ] Run Alembic migrations to head (`20260726_0011`)
- [ ] Seed synthetic institution and eight roles
- [ ] Run ingestion pipeline for all staging-approved datasets
- [ ] Rebuild Qdrant from deployed, approved files
- [ ] Run data parity verifier: `python scripts/data/data_parity_verifier.py --env staging`
- [ ] Confirm `redis_clean_start=true` in manifest
- [ ] Run full test suite
- [ ] Record staging manifest hash

## What Must NOT Appear in Staging

- Real institutional users
- Production credentials
- Real examination papers
- Student records
- Private lecturer information
- Object-storage exports from production
