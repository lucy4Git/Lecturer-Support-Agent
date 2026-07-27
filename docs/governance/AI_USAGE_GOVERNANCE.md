# AI Usage Governance

## Objective

Provide predictable, privacy-aware and auditable use of OpenAI, Anthropic Claude, Google Gemini, DeepSeek and Ollama without exposing model selection to ordinary users.

## Effective policy

The runtime resolves the most specific active policy permitted for the tenant and organisational scope. Policies may define:

- provider allow-list and deny-list;
- privacy classes that must use an approved local model;
- teaching tasks that require verified sources;
- monthly request limits;
- monthly input- and output-token limits;
- estimated monthly cost limits;
- warning threshold percentage;
- whether a limit is advisory or a hard block.

## Routing sequence

1. Classify the lecturer-support task and privacy level.
2. Resolve the effective AI usage policy.
3. Calculate the current monthly ledger.
4. Decide whether the request is permitted, warning-only or blocked.
5. Force local-only routing where policy requires it.
6. Require source discovery for configured task types.
7. Pass allowed and denied provider sets to the provider-neutral router.
8. Record execution outcome, token totals, latency and estimated cost.
9. Add any governance warning to the user-visible response metadata.

## Secret boundary

Policies contain provider names and rules only. API keys remain in environment variables or an approved production secret manager. The database may store the reference name, never the credential value.

## Cost accounting

Cost values are estimates derived from configured pricing metadata and should be presented as estimates. Currency is policy-defined; demonstration data uses GBP. Institution-specific configuration may use another supported ISO 4217 currency code.

## Human governance

Institution Administrators configure platform-level provider policy. Academic approval of teaching outputs remains with authorised academic roles and is not transferred to the administrator by this feature.

## Validation

Pure policy and routing rules are unit-tested. Live quota accuracy, provider metadata, concurrent ledger updates and provider failures remain owner-machine validation requirements.
