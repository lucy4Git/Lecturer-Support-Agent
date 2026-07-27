# Source Verification Data Model

## 1. Objective

Provide ChatGPT-like source cards while preventing fabricated citations. A citation is displayed only when an actual retrieval event and evidence record support the associated claim.

## 2. Core entities

### SourceRecord
Stable identity for a work, webpage, policy, dataset or institutional document. Includes title, creators, organisation, identifiers, canonical URL, publisher, dates, type, licence, authority, tenant scope and status.

### SourceVersion
Represents a specific edition, web snapshot, policy version or document version. Includes version label, effective dates, content hash, retrieval location and correction/retraction state.

### RetrievalEvent
Records user request, query, tool/connector, timestamp, tenant/scope, filters, rank, score and access decision.

### SourceEvidence
Stores the exact evidence used: passage or structured fields, location, source version, extraction method, evidence hash, support strength and reviewer status.

### GeneratedClaim
A bounded factual or normative statement extracted from the AI output. Includes claim text, claim type, risk level, sentence/span location and verification requirement.

### ClaimCitation
Links a claim to evidence and records relationship: supports, partially supports, contradicts, background only or unresolved.

### VerificationDecision
Records automated and human checks, confidence, limitations and display eligibility.

## 3. Citation display gate

A citation may be displayed only when:

- `SourceRecord` and `SourceVersion` exist;
- a real `RetrievalEvent` is linked;
- `SourceEvidence` contains an accessible evidence location;
- the evidence relationship is `SUPPORTS` or clearly labelled partial/background;
- the source has not been blocked, retracted or superseded for the claim;
- licence and access rules permit display;
- tenant and user scope permit disclosure.

A model-generated URL, DOI or title without retrieval evidence is rejected.

## 4. Source types

- peer-reviewed article;
- academic book or chapter;
- official policy/regulation/standard;
- institutional document;
- open textbook/OER;
- reputable technical documentation;
- professional body guidance;
- dataset;
- web source;
- user-provided document;
- generated example (never presented as external evidence).

## 5. Authority and applicability

Source quality is multidimensional: authority, peer review, recency, directness, jurisdiction, discipline, licence and correction status. The system may use a source as background while stating that it does not prove institutional compliance.

## 6. Institutional versus generic evidence

Source cards label:

- **Institutional source:** tenant-owned and permission checked;
- **External verified source:** retrieved from an approved external source;
- **User-provided source:** uploaded in the current authorised context;
- **General AI synthesis:** generated content not directly attributed to a source.

A response may combine these types but must not blur them.

## 7. Claim types requiring verification

- current facts, statistics and technical specifications;
- academic or professional standards;
- health, safety, legal or regulatory statements;
- named policies and institutional requirements;
- direct quotations;
- claims attributed to a person, paper or organisation;
- assertions of approval, compliance or accreditation.

Creative examples and pedagogical suggestions may be generic but should state assumptions when they depend on unknown context.

## 8. Retractions, corrections and change

Source versions record correction, retraction and supersession links. Scheduled jobs revalidate high-impact sources and links. Existing outputs retain historical evidence but display a warning when a source later changes materially.

## 9. API representation

A response source card should expose source ID, title, creator/organisation, date, type, URL/identifier, evidence summary, access label, verification status and why it was used. Restricted passages are not exposed beyond permission.

## 10. Metrics

- citation precision and recall;
- fabricated identifier rate;
- claim support rate;
- source-link resolution rate;
- authority/applicability score;
- correction/retraction detection time;
- percentage of high-risk claims verified;
- user source-card usefulness rating.
