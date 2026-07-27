# Teaching Output Artifact Schemas

These Draft 2020-12 JSON Schemas define portable, provider-neutral structures for inline teaching outputs. They are **contracts**, not separate workspaces: the unified conversation renders, edits, versions and exports them in place.

- `teaching_output.schema.json` — common envelope and source/provenance model.
- `lesson_plan.schema.json` — lesson and practical-session structure.
- `assessment_package.schema.json` — quizzes, tests, assignments and examinations.
- `rubric.schema.json` — analytic or holistic marking criteria.
- `marking_guide.schema.json` — confidential marking and memorandum content.

Assessment schemas require human review. Marking guides are confidential and cannot be released as student copies. Runtime implementations must also apply tenant, role, module-scope and assessment-safety controls; schema validity alone never constitutes academic approval.
