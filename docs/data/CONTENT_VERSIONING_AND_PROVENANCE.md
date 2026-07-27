# Content Versioning and Provenance

A `ContentItem` represents the stable conceptual object. Every upload or edit creates a new immutable `ContentVersion`; earlier bytes and metadata never change.

## Required version metadata

Version/content IDs; tenant and organisational scope; version number and parent; created/effective/academic periods; actor identity snapshot, active role and delegated authority; source system, batch and original path; filename, MIME, size, checksum and object version; classification, sensitivity, visibility, lifecycle/review status and change reason; links to module/course, programme, assessment, conversation, review and citations.

## Current/canonical

“Latest” is calculated from sequence/effective date. “Canonical” is an authorised pointer. Moving either pointer never alters prior versions.

## Duplicate handling

Exact checksum matches and similar content produce candidate relationships. Authorised choices are: link as provenance, create new version, create new content identity, or cancel. No choice overwrites another user's material.

## Deletion

Normal deletion archives visibility and records the action. Physical purge requires retention authority and a tombstone audit record.
