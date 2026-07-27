# Bulk Upload Scenarios

Bulk upload is a contextual permission-controlled action in the same product interface. It may appear in the composer attachment menu, module page, department page, library/content view, assignment or onboarding flow.

## BU-01 Institution onboarding — Institution Administrator

Import policies, templates, organisational/programme/module catalogues, calendars and initial user roster. Produce tenant-scoped batches, previews, validation reports and complete provenance without overwrite.

## BU-02 Annual institutional refresh — Institution Administrator

Upload revised policies, templates, calendars and grading rules. Create effective-dated versions; preserve prior versions; change canonical pointers only after authorised review.

## BU-03 Department semester readiness — Head of Department

Upload module descriptors, allocation sheets, teaching plans, moderation schedules, laboratory guidance and handover packs. Link to department/modules/lecturers and report metadata gaps.

## BU-04 Historical department migration — Head of Department

Migrate years of teaching and moderation evidence. Retain distinct academic periods, versions and upload provenance. Flag duplicate clusters without deleting them.

## BU-05 Lecturer semester pack — Lecturer

Upload slides, notes, readings, practicals, tutorials, assessments, rubrics, marking guides and student resources for assigned modules. Suggest week/type metadata and require confirmation before publication.

## BU-06 Lecturer evidence and handover — Lecturer

Upload delivery evidence, revised materials, reflections, assessment analysis and handover content. Link new immutable versions to earlier material and apply appropriate visibility.

## BU-07 Programme alignment set — Coordinator

Upload module outlines, outcomes, assessment plans, shared rubrics and curriculum-review evidence. Preserve every source version used in gap/duplication analysis.

## BU-08 Common assessment deployment — Coordinator or Head of Department

Upload common assessment packs for multiple groups/campuses/modules. Use references and child versions for local adaptations rather than replacement.

## BU-09 Moderation feedback — Moderator

Upload assigned annotations, forms, evidence and findings. Limit upload to the review assignment; feedback cannot mutate the submitted assessment version.

## BU-10 Temporary external review evidence — External Reviewer

Upload notes/evidence only where the grant permits it. Upload permission expires with the assignment.

## BU-11 Interrupted upload — Any authorised role

Use chunked/resumable upload, checksums and idempotency to continue safely after network failure.

## BU-12 Duplicate material — Any authorised role

Show exact checksum matches and probable similarity. Offer create new version, link to existing, create new item or cancel. Never overwrite.

## Required stages

Authorize; create immutable batch; upload/resume and checksum; malware scan; extract/classify; detect duplicates; request confirmation for uncertainty; commit each item as identity/version; index asynchronously; produce processing, error, duplicate, provenance and audit report.
