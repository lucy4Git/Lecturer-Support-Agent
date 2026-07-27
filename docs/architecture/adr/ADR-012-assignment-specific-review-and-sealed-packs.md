# ADR-012: Assignment-Specific Review and Sealed Review Packs

- **Status:** Accepted
- **Date:** 2026-07-25

## Context

Role-based permission alone is too broad for internal and external moderation. A moderator may be permitted to review assessments generally but must still see only the exact assessment version assigned to that engagement. Lecturer edits made after assignment must not alter the evidence being reviewed.

## Decision

The system will create a `ReviewCycle` and a sealed `ReviewPack` for every moderation or external-review engagement. Each task identifies an exact assignee, pack, output version, round, due date and action snapshot. External users also require an active, time-limited grant whose actions and resource scope match the task.

Reviewer findings and submissions are immutable evidence after submission. Reviewer recommendations remain separate from the formal academic decision. Correction work creates new output versions, packs and task rounds rather than replacing previous evidence.

## Consequences

### Positive

- defensible audit trail;
- no silent version substitution;
- least-privilege external access;
- independent academic decision authority;
- repeatable correction cycles;
- support for multiple reviewers and HEI structures.

### Costs

- more tables and workflow states;
- explicit expiry processing;
- additional owner-machine security tests;
- UI must communicate version and round clearly.

## Rejected alternatives

- giving moderators access to an entire department;
- allowing a role permission to bypass assignment checks;
- replacing review packs when lecturers edit outputs;
- treating a moderator recommendation as automatic approval;
- creating a separate moderation application.
