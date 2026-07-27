from services.api.app.services.source_integrity import canonical_source_identifier


def test_doi_is_preferred_and_normalised() -> None:
    assert canonical_source_identifier(
        doi=" 10.1000/ABC ", url="https://example.org", title="Example"
    ) == "doi:10.1000/abc"


def test_title_fallback_is_deterministic() -> None:
    first = canonical_source_identifier(doi=None, url=None, title="Constructive Alignment")
    second = canonical_source_identifier(doi=None, url=None, title=" constructive alignment ")
    assert first == second
    assert first.startswith("title-sha256:")


def test_stable_source_identifier_prevents_institutional_title_collision() -> None:
    first = canonical_source_identifier(
        doi=None, url=None, title="Module guide v1", stable_key="document-version:111"
    )
    second = canonical_source_identifier(
        doi=None, url=None, title="Module guide v1", stable_key="document-version:222"
    )
    assert first == "stable:document-version:111"
    assert first != second
