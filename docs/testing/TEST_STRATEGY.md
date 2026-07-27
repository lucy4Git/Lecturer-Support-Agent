# Test Strategy

Layers: unit; API/event contract; integration with database/object store/queue/search/vector/AI gateway; role-based E2E; tenant/authorization/file/prompt-injection security; automated plus manual accessibility; performance/load; AI pedagogy/assessment/citation/safety regression; retry/resume/backup/degraded-provider recovery.

Release blockers include cross-tenant leakage, broken role separation, fabricated citations, destructive version behaviour, inaccessible core journeys, critical security defects or missing live-preview evidence.
