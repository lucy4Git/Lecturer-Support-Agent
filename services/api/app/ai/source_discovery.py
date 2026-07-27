from __future__ import annotations

import hashlib
from typing import Any

import httpx

from ..core.settings import Settings
from .contracts import SourceCandidate


class CrossrefSourceDiscovery:
    """Retrieve genuine scholarly metadata from Crossref.

    This connector retrieves metadata, not full text. The returned records may
    be shown as source cards and supplied to a model, but are not automatically
    treated as proof that every generated claim is supported.
    """

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self._client = client

    async def discover(self, query: str, *, limit: int | None = None) -> list[SourceCandidate]:
        if not self.settings.source_discovery_enabled:
            return []
        rows = min(limit or self.settings.source_discovery_max_results, 10)
        if rows <= 0:
            return []
        params: dict[str, str | int] = {
            "query.bibliographic": query,
            "rows": rows,
            "select": "DOI,title,author,publisher,published-print,published-online,URL,type,license,score",
        }
        if self.settings.crossref_contact_email:
            params["mailto"] = self.settings.crossref_contact_email
        headers = {"User-Agent": self._user_agent()}
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(
            timeout=self.settings.source_http_timeout_seconds,
            follow_redirects=True,
        )
        try:
            response = await client.get(
                f"{self.settings.crossref_base_url.rstrip('/')}/works",
                params=params,
                headers=headers,
            )
            response.raise_for_status()
            payload = response.json()
            items = payload.get("message", {}).get("items", [])
            return [candidate for rank, item in enumerate(items, start=1) if (candidate := self._parse(item, query, rank))]
        except (httpx.HTTPError, ValueError, TypeError):
            return []
        finally:
            if owns_client:
                await client.aclose()

    def _user_agent(self) -> str:
        contact = self.settings.crossref_contact_email or "not-configured"
        return f"LecturerSupportAgent/1.5 (mailto:{contact})"

    @staticmethod
    def _parse(item: dict[str, Any], query: str, rank: int) -> SourceCandidate | None:
        titles = item.get("title") or []
        title = str(titles[0]).strip() if titles else ""
        doi = str(item.get("DOI") or "").strip() or None
        url = str(item.get("URL") or "").strip() or (f"https://doi.org/{doi}" if doi else None)
        if not title or not url:
            return None
        authors: list[str] = []
        for author in item.get("author") or []:
            name = " ".join(part for part in (author.get("given"), author.get("family")) if part)
            if name:
                authors.append(name)
        date_parts = (item.get("published-print") or item.get("published-online") or {}).get("date-parts") or []
        publication_date = "-".join(str(part) for part in date_parts[0]) if date_parts else None
        licences = item.get("license") or []
        licence = licences[0].get("URL") if licences else None
        source_key = hashlib.sha256((doi or url).lower().encode("utf-8")).hexdigest()[:20]
        return SourceCandidate(
            source_key=source_key,
            source_type=str(item.get("type") or "scholarly_work"),
            title=title,
            authors=authors,
            publisher_or_organisation=item.get("publisher"),
            publication_date=publication_date,
            canonical_url=url,
            doi=doi,
            licence=licence,
            reliability_tier="crossref_member_metadata",
            retrieved_by="crossref_rest_api",
            retrieval_query=query,
            rank=rank,
            relevance_score=float(item.get("score")) if item.get("score") is not None else None,
            metadata={"recorded_from_actual_retrieval": True},
        )


class OpenAlexSourceDiscovery:
    """Retrieve scholarly metadata from the OpenAlex Works API.

    OpenAlex records are metadata only. A work being returned does not itself
    prove that a generated claim is supported; claim-level verification remains
    a separate control.
    """

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self._client = client

    async def discover(self, query: str, *, limit: int | None = None) -> list[SourceCandidate]:
        if not self.settings.source_discovery_enabled or not self.settings.openalex_enabled:
            return []
        rows = min(limit or self.settings.source_discovery_max_results, 10)
        params: dict[str, str | int] = {
            "search": query,
            "per-page": rows,
            "select": "id,doi,title,authorships,primary_location,publication_year,type,open_access,relevance_score",
        }
        if self.settings.openalex_api_key:
            params["api_key"] = self.settings.openalex_api_key.get_secret_value()
        if self.settings.openalex_contact_email:
            params["mailto"] = self.settings.openalex_contact_email
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(
            timeout=self.settings.source_http_timeout_seconds,
            follow_redirects=True,
        )
        try:
            response = await client.get(
                f"{self.settings.openalex_base_url.rstrip('/')}/works",
                params=params,
                headers={"User-Agent": self._user_agent()},
            )
            response.raise_for_status()
            items = response.json().get("results", [])
            return [candidate for rank, item in enumerate(items, start=1) if (candidate := self._parse(item, query, rank))]
        except (httpx.HTTPError, ValueError, TypeError):
            return []
        finally:
            if owns_client:
                await client.aclose()

    def _user_agent(self) -> str:
        contact = self.settings.openalex_contact_email or "not-configured"
        return f"LecturerSupportAgent/2.5 (mailto:{contact})"

    @staticmethod
    def _parse(item: dict[str, Any], query: str, rank: int) -> SourceCandidate | None:
        title = str(item.get("title") or "").strip()
        openalex_id = str(item.get("id") or "").strip()
        doi_url = str(item.get("doi") or "").strip() or None
        doi = doi_url.removeprefix("https://doi.org/") if doi_url else None
        location = item.get("primary_location") or {}
        landing = str(location.get("landing_page_url") or "").strip() or doi_url or openalex_id
        if not title or not landing:
            return None
        authors: list[str] = []
        for authorship in item.get("authorships") or []:
            author = authorship.get("author") or {}
            name = str(author.get("display_name") or "").strip()
            if name:
                authors.append(name)
        source = (location.get("source") or {}) if isinstance(location, dict) else {}
        source_key = hashlib.sha256((doi or openalex_id or landing).lower().encode("utf-8")).hexdigest()[:20]
        open_access = item.get("open_access") or {}
        return SourceCandidate(
            source_key=source_key,
            source_type=str(item.get("type") or "scholarly_work"),
            title=title,
            authors=authors,
            publisher_or_organisation=source.get("display_name"),
            publication_date=str(item.get("publication_year")) if item.get("publication_year") else None,
            canonical_url=landing,
            doi=doi,
            licence="CC0 metadata",
            reliability_tier="openalex_scholarly_metadata",
            retrieved_by="openalex_works_api",
            retrieval_query=query,
            rank=rank,
            relevance_score=float(item.get("relevance_score")) if item.get("relevance_score") is not None else None,
            metadata={
                "recorded_from_actual_retrieval": True,
                "openalex_id": openalex_id,
                "open_access_status": open_access.get("oa_status"),
                "is_oa": open_access.get("is_oa"),
            },
        )


class CompositeSourceDiscovery:
    """Combine source connectors and remove duplicate DOI/URL records."""

    def __init__(self, connectors: list[Any]) -> None:
        self.connectors = connectors

    async def discover(self, query: str, *, limit: int = 5) -> list[SourceCandidate]:
        combined: list[SourceCandidate] = []
        for connector in self.connectors:
            combined.extend(await connector.discover(query, limit=limit))
        unique: dict[str, SourceCandidate] = {}
        for candidate in combined:
            key = (candidate.doi or str(candidate.canonical_url or candidate.source_key)).lower()
            if key not in unique:
                unique[key] = candidate
        values = list(unique.values())
        values.sort(key=lambda item: (item.rank or 999, -(item.relevance_score or 0.0)))
        return values[:limit]
