# ADR-006: Multi-Provider and Ollama Model Fabric

**Status:** Accepted  
**Date:** 21 July 2026

## Context

The platform requires high availability, provider choice, local privacy options, multimodal capability and protection from vendor lock-in. OpenAI must not be the only runtime provider.

## Decision

Implement a provider-neutral AI gateway with initial adapters for OpenAI, Anthropic Claude, Google Gemini, DeepSeek API and Ollama. Ordinary users never select models. Routing uses internal capability aliases, tenant/data policy, evaluation evidence, health, cost and latency.

Cloud model identifiers are discovered and administrator-approved rather than hard-coded. Ollama model profiles are installed locally through controlled PowerShell scripts and remain candidate models until evaluated.

## Consequences

Benefits include resilience, offline development, local processing options and capability diversity. Costs include adapter maintenance, broader evaluation, provider-specific policy tracking, more observability and more complex fallback logic.

## Non-negotiable constraints

- no fallback that weakens privacy or tenant policy;
- no provider-generated citation accepted without retrieval verification;
- no model binary in source control or the project ZIP;
- no production use before model, licence, security and quality approval;
- complete routing and model-version audit trail.
