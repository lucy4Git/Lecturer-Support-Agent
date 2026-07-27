from __future__ import annotations

import re

from .contracts import IntegrityResult, SourceCandidate


class CitationIntegrityGuard:
    """Fail-closed control for references emitted by a model.

    The guard accepts only source markers and identifiers that were present in
    the actual source pack. It does not claim that a cited source entails every
    statement; claim-level verification remains a separate evaluation step.
    """

    _marker_pattern = re.compile(r"\[S(\d+)\]")
    _url_pattern = re.compile(r"https?://[^\s)\]>]+", re.IGNORECASE)
    _doi_pattern = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)

    def validate(self, text: str, sources: list[SourceCandidate]) -> IntegrityResult:
        allowed_urls = {str(s.canonical_url).rstrip(".,") for s in sources if s.canonical_url}
        allowed_dois = {s.doi.lower() for s in sources if s.doi}
        source_keys = {index + 1: source.source_key for index, source in enumerate(sources)}
        warnings: list[str] = []
        removed = 0

        def marker_replacement(match: re.Match[str]) -> str:
            nonlocal removed
            number = int(match.group(1))
            if number not in source_keys:
                removed += 1
                return "[unverified citation removed]"
            return match.group(0)

        cleaned = self._marker_pattern.sub(marker_replacement, text)

        for url in set(self._url_pattern.findall(cleaned)):
            canonical = url.rstrip(".,")
            if canonical not in allowed_urls:
                cleaned = cleaned.replace(url, "[unverified link removed]")
                removed += 1
        for doi in set(self._doi_pattern.findall(cleaned)):
            if doi.lower().rstrip(".,") not in allowed_dois:
                cleaned = cleaned.replace(doi, "[unverified DOI removed]")
                removed += 1

        cited_numbers = sorted(
            {int(value) for value in self._marker_pattern.findall(cleaned) if int(value) in source_keys}
        )
        if removed:
            warnings.append(
                "One or more model-generated references were removed because they were not in the verified source pack."
            )
        return IntegrityResult(
            text=cleaned,
            cited_source_keys=[source_keys[number] for number in cited_numbers],
            warnings=warnings,
            removed_unverified_references=removed,
        )


class ClaimCitationVerifier:
    """Heuristic claim-to-citation coverage control.

    This control does not claim semantic entailment. It identifies factual or
    quantitative sentences that lack a verified source marker, allowing the UI
    and review workflow to flag unsupported claims before release.
    """

    _sentence_pattern = re.compile(r"(?<=[.!?])\s+")
    _factual_signal = re.compile(
        r"\b(?:\d+(?:\.\d+)?%?|according to|research|study|evidence|standard|policy|"
        r"requires?|demonstrates?|shows?|indicates?|is associated with|causes?|improves?|"
        r"reduces?|increases?|decreases?)\b",
        re.IGNORECASE,
    )

    def verify(self, text: str, sources: list[SourceCandidate]) -> dict[str, object]:
        allowed = {index + 1 for index, _ in enumerate(sources)}
        claims: list[dict[str, object]] = []
        unsupported = 0
        for sequence, sentence in enumerate(self._sentence_pattern.split(text.strip()), start=1):
            sentence = sentence.strip()
            if not sentence or not self._factual_signal.search(sentence):
                continue
            cited = {int(value) for value in CitationIntegrityGuard._marker_pattern.findall(sentence)}
            verified = sorted(cited & allowed)
            supported = bool(verified)
            unsupported += 0 if supported else 1
            claims.append(
                {
                    "sequence": sequence,
                    "text": sentence[:1000],
                    "verified_source_numbers": verified,
                    "status": "citation_present" if supported else "citation_missing",
                }
            )
        return {
            "claim_count": len(claims),
            "unsupported_claim_count": unsupported,
            "coverage": 1.0 if not claims else round((len(claims) - unsupported) / len(claims), 4),
            "claims": claims,
            "semantic_entailment_verified": False,
        }
