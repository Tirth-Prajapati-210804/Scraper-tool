from __future__ import annotations

import pytest

from app.providers.flightapi import FlightApiProvider

SAMPLE_FLIGHTAPI_FPI = {
    "fpiTrips": [
        {
            "totalPrice": 1800,
            "legs": [{"carriers": ["AC"]}],
            "deepLink": "https://flightapi.io/link/1",
        },
        {
            "totalPrice": 2500,
            "legs": [{"carriers": ["UA"]}],
            "deepLink": "https://flightapi.io/link/2",
        },
    ]
}

SAMPLE_FLIGHTAPI_ITINS = {
    "itineraries": [
        {
            "pricing": {"total": 1650},
            "legs": [{"carriers": ["KE"]}],
            "deepLink": "https://flightapi.io/link/3",
        }
    ]
}


def test_flightapi_normalize_fpi_trips() -> None:
    provider = FlightApiProvider(api_key="test")
    results = provider._normalize(SAMPLE_FLIGHTAPI_FPI)
    assert len(results) == 2
    assert results[0].price == 1800
    assert results[0].airline == "AC"


def test_flightapi_normalize_itineraries() -> None:
    provider = FlightApiProvider(api_key="test")
    results = provider._normalize(SAMPLE_FLIGHTAPI_ITINS)
    assert len(results) == 1
    assert results[0].price == 1650
    assert results[0].airline == "KE"


def test_flightapi_normalize_empty() -> None:
    provider = FlightApiProvider(api_key="test")
    assert provider._normalize({}) == []
    assert provider._normalize({"fpiTrips": []}) == []


def test_flightapi_normalize_sorted() -> None:
    provider = FlightApiProvider(api_key="test")
    results = provider._normalize(SAMPLE_FLIGHTAPI_FPI)
    assert results[0].price <= results[1].price


def test_flightapi_is_configured() -> None:
    assert FlightApiProvider(api_key="key123").is_configured() is True
    assert FlightApiProvider(api_key="").is_configured() is False
