# Moderation and External Review Architecture

A review assignment defines reviewer, tenant, scope, immutable content set, criteria, permitted actions, start, expiry and revocation. The reviewer cannot mutate source assessment versions. Findings, annotations, responses and decisions are append-only. Revisions create child versions linked to findings. External sessions may require stronger authentication and expire automatically.
