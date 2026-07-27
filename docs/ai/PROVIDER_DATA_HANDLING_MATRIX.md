# Provider Data-Handling Matrix

This matrix is a decision template. Contractual terms, regions, retention and model availability must be verified during tenant onboarding and periodically thereafter.

| Data class | OpenAI | Anthropic | Google Gemini | DeepSeek API | Ollama local |
|---|---|---|---|---|---|
| Public | May be enabled | May be enabled | May be enabled | May be enabled | May be enabled |
| Internal | Tenant contract and policy required | Tenant contract and policy required | Tenant contract and policy required | Tenant contract and policy required | Host controls required |
| Confidential | Explicit approval, minimum context and required privacy terms | Explicit approval, minimum context and required privacy terms | Explicit approval, minimum context and required privacy terms | Explicit approval, minimum context and required privacy terms | Preferred only after host/security approval |
| Restricted assessment or personal data | Deny by default; exceptional documented approval only | Deny by default; exceptional documented approval only | Deny by default; exceptional documented approval only | Deny by default; exceptional documented approval only | Approved isolated deployment only |

## Required registry fields

For every provider/model pair record region, retention, provider-training status, sub-processors, encryption, data-residency options, incident process, deletion capability, approved tenants, approved data classes, model lifecycle, evaluation status and contract evidence.

## Principle

No provider is globally approved. Approval is scoped to a tenant, deployment, model, data class and use case. A fallback cannot silently change these conditions.
