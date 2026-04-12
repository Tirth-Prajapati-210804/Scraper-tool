from __future__ import annotations

import pytest

from app.providers.serper import DURATION_PATTERN, PRICE_PATTERN, SerperProvider


def test_serper_price_regex_matches_cad() -> None:
    match = PRICE_PATTERN.search("Flights from CAD 1,587 round trip")
    assert match
    assert match.group(1) == "1,587"


def test_serper_price_regex_matches_dollar() -> None:
    match = PRICE_PATTERN.search("Starting at $2,100.50")
    assert match
    assert match.group(1) == "2,100.50"


def test_serper_price_regex_matches_c_dollar() -> None:
    match = PRICE_PATTERN.search("From C$899 one-way")
    assert match
    assert match.group(1) == "899"


def test_serper_duration_regex() -> None:
    match = DURATION_PATTERN.search("Flight duration: 14h 30m")
    assert match
    assert int(match.group(1)) == 14
    assert int(match.group(2)) == 30


def test_serper_duration_regex_hours_only() -> None:
    match = DURATION_PATTERN.search("Direct 10h flight")
    assert match
    assert int(match.group(1)) == 10


def test_serper_normalize_extracts_prices() -> None:
    provider = SerperProvider(api_key="test")
    sample = {
        "organic": [
            {
                "title": "Cheap flights YYZ to NRT",
                "snippet": "From CAD 1,450 one-way with Air Canada",
                "link": "https://example.com/1",
            },
            {
                "title": "No price here",
                "snippet": "Book your flight today",
                "link": "https://example.com/2",
            },
        ]
    }
    results = provider._normalize(sample)
    assert len(results) == 1
    assert results[0].price == 1450.0


def test_serper_normalize_empty() -> None:
    provider = SerperProvider(api_key="test")
    assert provider._normalize({}) == []
    assert provider._normalize({"organic": []}) == []


def test_serper_is_configured() -> None:
    assert SerperProvider(api_key="key123").is_configured() is True
    assert SerperProvider(api_key="").is_configured() is False
