# Institutional Approver Matrix

**Project:** Lecturer Support Agent  
**Version:** 2.5.1  
**Date:** 2026-08-03

## Overview

Every privileged action in the Lecturer Support Agent requires an assigned approver.
The full matrix is in `data/governance/approver_matrix.yaml`. This document is the
human-readable version.

## Local and Staging: Synthetic Approvers Only

For local development and staging validation, synthetic approvers from the
`demo-north` institution are used. These are not real people and must never
be used in production.

## Production: Institutional Personnel Only

All production approver slots must be filled with real, authorised personnel
before the system goes live. Placeholder `REPLACE_WITH_*` values in
`approver_matrix.yaml` must be replaced with actual names and references.

## Approval Domains

| Domain | Minimum Approvers | Production Requirement |
|--------|------------------|-----------------------|
| Tenant onboarding | 1 | Platform operator + IT security |
| Institution Administrator | 1 | Institutional authority |
| Lecturer access | 1 | Head of Department or Admin |
| Coordinator assignment | 1 | Head of Department |
| HoD assignment | 1 | Institution Administrator |
| Internal Moderator | 1 | Head of Department |
| External Moderator | 1 | Admin or HoD |
| External Reviewer | 1 | Head of Department |
| Dataset rights | 1 | Data Governance Lead + Legal |
| Dataset staging | 1 | Data Governance Lead |
| **Dataset production** | **2** | DGL + Legal + Institutional Admin |
| Real-data import | **2** | Admin + Privacy Officer |
| Legal | 1 | Legal Officer |
| Privacy | 1 | DPO |
| Ethics | 1 | Ethics Board |
| IT security | 1 | IT Security Officer |
| **Production release** | **2** | Platform Operator + IT Security + DGL |

## Independence Requirement

Institution Administrator and Head of Department must remain independent
roles. The Institution Administrator must not acquire academic approval
authority (e.g., Head of Department's right to assign lecturers).
