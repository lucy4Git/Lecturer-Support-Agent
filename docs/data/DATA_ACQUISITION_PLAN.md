# Data Acquisition Plan

**Project:** Lecturer Support Agent  
**Version:** 2.5.1  
**Date:** 2026-08-03  
**Status:** Active

## Objective

Establish a legally reusable, deployment-ready dataset foundation for the
Lecturer Support Agent covering all supported academic disciplines, qualification
levels, and teaching functions.

## Governing Principles

1. Only publicly available, openly licensed, public domain, or officially
   open-data material may be acquired.
2. Every dataset must pass through the governed approval gate before ingest.
3. Rights-unclear material is quarantined as `PENDING_RIGHTS_REVIEW`.
4. No real institutional users or assessments are scraped or auto-created.
5. Large datasets are not stored in Git — object storage only.
6. Production approval is always a human decision.

## Acquisition Methods

| Method | Examples | Notes |
|--------|----------|-------|
| REST API | OER Commons, OpenAlex, Crossref, DOAB | Rate limits apply; polite-pool headers required |
| HTTP Download | MIT OCW, OpenStax, UNESCO UNESDOC | robots.txt and terms checked before download |
| File system | Internal synthetic fixtures | Internally authored; no external acquisition |

## Prioritised Dataset Pipeline

| Priority | Dataset ID | Title | Governance State | Next Action |
|----------|-----------|-------|-----------------|-------------|
| 1 | DS-009 | Bloom's Taxonomy | APPROVED_FOR_LOCAL | Download reference summary |
| 2 | DS-010 | Synthetic Rubric Templates | APPROVED_FOR_LOCAL | Already in fixtures |
| 3 | DS-011 | Citation Evaluation Corpus | APPROVED_FOR_LOCAL | Already in evaluation |
| 4 | DS-003 | OpenStax Textbooks | APPROVED_FOR_LOCAL | Controlled download during onboarding |
| 5 | DS-004 | OpenAlex Education Subset | APPROVED_FOR_LOCAL | API ingest via pipeline |
| 6 | DS-008 | UNESCO OER Guidelines | APPROVED_FOR_LOCAL | Download PDF |
| 7 | DS-002 | MIT OpenCourseWare | APPROVED_FOR_LOCAL | Controlled download (NC — local/staging only) |
| 8 | DS-001 | OER Commons Index | APPROVED_FOR_LOCAL | API ingest with per-item rights check |
| 9 | DS-007 | DOAB Open Books | APPROVED_FOR_LOCAL | Filter CC BY; controlled download |
| Quarantined | DS-006, DS-012 | MERLOT items | PENDING_RIGHTS_REVIEW | Per-item legal review required |

## Discipline Gap Registry

The following disciplines have approved datasets planned but not yet downloaded:

- Agriculture
- Art and Design  
- Hospitality and Consumer Sciences
- Law (legal restrictions require separate review)
- Health Sciences (ethical and regulatory review required)

These gaps are recorded and must not be misrepresented as covered.

## Not in Scope

- Confidential institutional examination papers
- Leaked assessments
- Student personal records
- Private lecturer information
- Copyrighted textbooks without permission
- Content behind authentication walls
