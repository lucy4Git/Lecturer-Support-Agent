# Citation Integrity Guard v1.5

## Problem addressed

A general AI model may output plausible-looking but nonexistent references. The platform must show useful source cards without accepting model-invented URLs, DOIs, authors, or citation numbers.

## Controls

1. Source discovery happens before generation.
2. Every source receives an internal key and numbered marker such as `[S1]`.
3. The model is instructed to cite only the supplied source pack.
4. After generation, the integrity guard:
   - retains markers that map to retrieved sources;
   - removes unknown markers;
   - removes URLs not present in the source pack;
   - removes DOIs not present in the source pack;
   - records an integrity warning whenever removal occurs.
5. A database citation may only reference a `SourceRetrieval` created for the same `AIRequest` as the output.
6. Retrieval verification and claim entailment are kept separate.

## Interpretation of source states

- **Retrieved:** source metadata was actually received from an approved connector or provider grounding payload.
- **Cited:** the response contains the matching source marker.
- **Partially verified:** the source and identifier are real and retrieved, but full claim-level entailment still requires automated evaluation or human review.
- **Verified:** reserved for a later claim-level process that confirms source identity, locator, and support for the cited claim.

## Current discovery connector

v1.5 includes a Crossref metadata connector for scholarly works. It does not download copyrighted full text and does not imply that Crossref metadata alone proves a pedagogical claim. Additional approved connectors can be added through the same contract.
