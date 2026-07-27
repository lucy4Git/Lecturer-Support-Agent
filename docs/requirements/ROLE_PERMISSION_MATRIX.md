# Role and Permission Matrix

Roles are independent. A person may hold multiple roles only through an explicit scoped assignment.

| Capability | Lecturer | Coordinator | Head of Department | Institution Admin | Moderator | External Reviewer |
|---|---:|---:|---:|---:|---:|---:|
| Unified AI work area | Own scope | Assigned scope | Department | Tenant admin scope | Assigned review | Assigned review |
| Generate/edit teaching content | Yes | Yes | Only if academically assigned | Not by admin role alone | No unless separately assigned | Comments only if granted |
| Generate/edit assessments | Assigned modules | Assigned modules/programmes | Oversight; authoring only if assigned | No by admin role alone | Review only | Review only |
| Bulk upload | Module content | Programme/module content | Department content | Tenant/onboarding content | Assigned review evidence | Only if grant permits |
| Assign courses to lecturers | No | No | Yes | No by admin role alone | No | No |
| Add users/assign tenant roles | No | No | No | Yes | No | No |
| Configure hierarchy/terminology | No | Propose | Propose | Yes | No | No |
| Appoint moderators | No | Recommend | Yes within department | Configure eligibility only | No | No |
| Cross-module alignment | Own/assigned | Yes | Yes | No by admin role alone | Assigned assessment only | Assigned task only |
| Confidential assessment access | Own/assigned | Assigned | Department policy scope | Metadata only unless explicitly granted | Assigned only | Assigned only |
| Invite external reviewer | Request | Request | Sponsor within policy | Provision/account controls | No | No |
| Audit access | Own actions | Assigned scope | Department | Tenant | Own assignment | Own assignment |
| Designate canonical version | Own where permitted | Assigned scope | Department | Institutional content | Recommend only | No |

## Separation rules

1. Institution Administrator does not inherit academic authoring or Head of Department authority.
2. Head of Department does not inherit tenant user/role administration.
3. Administrative metadata access does not imply access to confidential assessment bytes.
4. External access is explicit, time-bound, scope-bound, revocable and logged.
5. Backend authorization is authoritative; hidden UI controls are not enforcement.


## v1.8 moderation permissions

| Capability | Institution Admin | HOD | Module/Programme Coordinator | Lecturer | Internal Moderator | External Moderator/Reviewer |
|---|---:|---:|---:|---:|---:|---:|
| Create/assign review cycle | No | Yes, scoped | Yes, scoped | No | No | No |
| Read assigned task | No automatic academic access | Oversight, scoped | Oversight, scoped | Own output/findings | Assigned only | Assigned + valid grant only |
| Record findings and recommendation | No | Only when separately assigned | Only when separately assigned | No | Assigned only | Assigned + valid grant only |
| Respond to findings | No automatic academic access | Yes, scoped | Yes, scoped | Own output | No | No |
| Record formal academic decision | No | Yes, scoped | Yes, scoped | No | No | No |
| Release approved output | No automatic authority | Yes, scoped | Yes, scoped | No | No | No |
