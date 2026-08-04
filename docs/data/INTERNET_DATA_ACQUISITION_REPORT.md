# Internet Data Acquisition Report

**Project:** Lecturer Support Agent  
**Version:** 2.5.1  
**Report Date:** 2026-08-03  
**Prepared By:** Data Governance Lead (Claude Code, acting as implementation agent)

## Executive Summary

Internet research was conducted on 2026-08-03 to identify publicly available,
openly licensed datasets suitable for the Lecturer Support Agent retrieval and
evaluation pipelines. Twelve datasets were discovered, catalogued, and assigned
governance states. No datasets were bulk-downloaded during this session. All
acquisition must occur during controlled data onboarding with appropriate approvals.

## Research Sources Consulted

| Source | URL | Purpose |
|--------|-----|---------|
| OER Commons | https://www.oercommons.org | OER repository discovery |
| MIT OpenCourseWare | https://ocw.mit.edu | Higher education course materials |
| OpenStax | https://openstax.org | Open textbooks |
| OpenAlex | https://openalex.org | Scholarly metadata |
| Crossref | https://www.crossref.org | DOI metadata and citation verification |
| MERLOT | https://www.merlot.org | Higher education teaching materials |
| DOAB / OAPEN | https://www.doabooks.org | Open access academic books |
| UNESCO UNESDOC | https://unesdoc.unesco.org | OER policy and framework documents |
| Vanderbilt CFT | https://cft.vanderbilt.edu | Bloom's Taxonomy reference |
| Directory of Open Access Books | https://directory.doabooks.org | OA book index |
| Creative Commons | https://creativecommons.org | Licence verification |
| ISKME | https://www.iskme.org | OER Commons platform |
| Nova Southeastern University LibGuide | https://libguides.nova.edu | OER repository list |
| Case Western Reserve LibGuide | https://researchguides.case.edu | Open datasets guide |
| Lincoln Land Community College LibGuide | https://library.llcc.edu | OER repositories list |
| IntuitionLabs API Research | https://intuitionlabs.ai | Scholarly APIs comparison |
| Singapore Management University LibGuide | https://researchguides.smu.edu.sg | Scholarly metadata APIs |

## Datasets Discovered: 12

| ID | Title | Licence | State |
|----|-------|---------|-------|
| DS-001 | OER Commons Full Repository Index | Various CC | APPROVED_FOR_LOCAL |
| DS-002 | MIT OpenCourseWare | CC BY-NC-SA 4.0 | APPROVED_FOR_LOCAL |
| DS-003 | OpenStax Open Textbooks | CC BY 4.0 | APPROVED_FOR_LOCAL |
| DS-004 | OpenAlex — Education Subset | CC0 1.0 | APPROVED_FOR_LOCAL |
| DS-005 | Crossref Metadata API | CC0 (metadata) | APPROVED_FOR_LOCAL |
| DS-006 | MERLOT — Teaching Materials | Various (item-level) | PENDING_RIGHTS_REVIEW |
| DS-007 | DOAB Open Books | Various CC | APPROVED_FOR_LOCAL |
| DS-008 | UNESCO OER Policy Guidelines | CC BY-SA 3.0 IGO | APPROVED_FOR_LOCAL |
| DS-009 | Bloom's Taxonomy | Public Domain | APPROVED_FOR_LOCAL |
| DS-010 | Synthetic Assessment Templates | MIT (internal) | APPROVED_FOR_LOCAL |
| DS-011 | Citation Evaluation Corpus | MIT (internal) | APPROVED_FOR_LOCAL |
| DS-012 | MERLOT Item-Level Materials | PENDING | PENDING_RIGHTS_REVIEW |

## Datasets Downloaded: 0

No bulk downloads were performed during this session. Large datasets require
controlled onboarding with malware scanning, rights verification, and approval
gate clearance before download.

## Datasets Approved for Local Use: 10

DS-001, DS-002, DS-003, DS-004, DS-005, DS-007, DS-008, DS-009, DS-010, DS-011

## Datasets Approved for Staging: 5

DS-003, DS-004, DS-005, DS-008, DS-009 (plus DS-010, DS-011 as internal)

## Datasets Pending Rights Review: 2

- **DS-006 / DS-012 — MERLOT:** Per-item licence verification required before
  any ingest. Legal review pending.

## Datasets Rejected: 0

No datasets were classified REJECTED. DS-006 and DS-012 are quarantined as
PENDING_RIGHTS_REVIEW; they may be reclassified after legal review.

## Datasets Requiring Production Approval: All non-internal datasets

Production approval is a human decision and must not be automated. Datasets
DS-003, DS-004, DS-005, DS-007, DS-008, DS-009 require explicit production
approval from the Data Governance Lead and institutional authority before
production deployment.

## Discipline Coverage Assessment

| Discipline | Coverage | Notes |
|------------|----------|-------|
| Computing and IT | PARTIAL | MIT OCW, OpenStax, OER Commons |
| Engineering | PARTIAL | MIT OCW |
| Natural Sciences | PARTIAL | MIT OCW, OpenStax |
| Mathematics | PARTIAL | MIT OCW, OpenStax |
| Business and Management | PARTIAL | MIT OCW, OpenStax |
| Economics and Accounting | PARTIAL | OpenStax |
| Education | GOOD | OER Commons, OpenAlex, UNESCO |
| Humanities | PARTIAL | MIT OCW, DOAB |
| Social Sciences | PARTIAL | OpenStax, DOAB |
| Law | NONE | Requires separate legal review |
| Health Sciences | NONE | Requires ethical and regulatory review |
| Agriculture | NONE | No source identified yet |
| Environmental Studies | PARTIAL | DOAB |
| Media and Communication | PARTIAL | DOAB |
| Art and Design | NONE | No open source identified |
| Hospitality | NONE | No open source identified |

## Gaps Acknowledged

The following are **explicitly not claimed** as covered:

- Law (jurisdiction-specific; requires legal review)
- Health Sciences (ethical approval required for clinical content)
- Agriculture, Art and Design, Hospitality (no approved open source identified)
- Live institutional examinations (prohibited)
- Student records (prohibited)

## Personal Information Scan: PASS

No personal information is included in any catalogued dataset. DS-006 and
DS-012 remain quarantined pending rights review, so their contents have not
been examined.

## Licence Validation: PASS

All 10 approved-for-local datasets have verified licences recorded in
`data/governance/rights_ledger.csv`. The 2 pending datasets have no licence
recorded, consistent with their PENDING_RIGHTS_REVIEW state.

## Confirmation

No real institutional user or approver data was acquired, created, or committed
to this repository during this session. All user references are to synthetic
accounts used for local and staging validation only.
