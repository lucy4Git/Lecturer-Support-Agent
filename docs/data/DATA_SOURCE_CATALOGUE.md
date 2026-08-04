# Data Source Catalogue

**Project:** Lecturer Support Agent  
**Version:** 2.5.1  
**Date:** 2026-08-03

## Purpose

Human-readable companion to `data/catalogue/dataset_catalogue.yaml`. Lists every
discovered source with its governance state and intended use. The YAML/JSON files
are authoritative; this document is for human review.

## Approved for Local Use

| ID | Title | Licence | Content | Disciplines |
|----|-------|---------|---------|-------------|
| DS-001 | OER Commons Index | Various CC (per item) | Lesson plans, syllabi, assessments | All |
| DS-002 | MIT OpenCourseWare | CC BY-NC-SA 4.0 | Course materials, problem sets, exams | All (non-commercial) |
| DS-003 | OpenStax Textbooks | CC BY 4.0 | Open textbooks | Sciences, Maths, Business, Humanities |
| DS-004 | OpenAlex — Education | CC0 | Scholarly metadata, abstracts | Education |
| DS-005 | Crossref API | CC0 (metadata) | DOI metadata, citation records | All |
| DS-007 | DOAB Open Books | Various CC | Academic books | All |
| DS-008 | UNESCO OER Guidelines | CC BY-SA 3.0 IGO | Policy documents | Education |
| DS-009 | Bloom's Taxonomy | Public Domain | Cognitive framework | All |
| DS-010 | Synthetic Templates (internal) | MIT | Assessment/rubric templates | All |
| DS-011 | Citation Evaluation Corpus (internal) | MIT | Hallucination challenges | All |

## Pending Rights Review (quarantined — do not ingest)

| ID | Title | Reason |
|----|-------|--------|
| DS-006 | MERLOT Teaching Materials | Per-item licence verification required |
| DS-012 | MERLOT Item-Level Materials | Per-item licence verification required |

## Discipline Coverage Matrix

| Discipline | Covered | Primary Source(s) | Gap Notes |
|------------|---------|------------------|-----------|
| Computing & IT | PARTIAL | DS-002, DS-001 | No dedicated computing OER source yet |
| Engineering | PARTIAL | DS-002 | No engineering-specific OER |
| Natural Sciences | PARTIAL | DS-002, DS-003 | Good breadth in OpenStax |
| Mathematics & Statistics | PARTIAL | DS-002, DS-003 | OpenStax covers calculus, stats |
| Business & Management | PARTIAL | DS-002, DS-003 | OpenStax business texts |
| Economics & Accounting | PARTIAL | DS-003 | OpenStax Economics |
| Education | GOOD | DS-001, DS-004, DS-008, DS-009 | Strong coverage |
| Humanities | PARTIAL | DS-002, DS-007 | DOAB covers philosophy, history |
| Social Sciences | PARTIAL | DS-003, DS-007 | OpenStax sociology |
| Law | NONE | — | Jurisdiction-specific; legal review required |
| Health Sciences | NONE | — | Ethical & regulatory review required |
| Agriculture | NONE | — | No approved open source identified |
| Environmental Studies | PARTIAL | DS-007 | DOAB titles only |
| Media & Communication | PARTIAL | DS-007 | Limited coverage |
| Art & Design | NONE | — | No approved open source identified |
| Hospitality & Consumer Sciences | NONE | — | No approved open source identified |

## Qualification Level Coverage

| Level | Coverage |
|-------|----------|
| Certificate | PARTIAL |
| Diploma | PARTIAL |
| Higher Certificate | PARTIAL |
| Advanced Diploma | PARTIAL |
| Bachelor's degree | GOOD |
| Honours | PARTIAL |
| Postgraduate Diploma | PARTIAL |
| Master's degree | PARTIAL |
| Doctoral | LIMITED |
| Professional & Continuing Education | LIMITED |
