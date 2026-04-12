from __future__ import annotations

import pytest

from app.providers.kiwi import KiwiProvider

SAMPLE_KIWI_RESPONSE = {
    "data": [
        {
            "price": 1587,
            "deep_link": "https://www.kiwi.com/deep?from=YYZ&to=TYO",
            "duration": {"total": 52200},
            "route": [
                {"airline": "AC", "flyFrom": "YYZ", "flyTo": "NRT", "flight_no": 5},
            ],
        },
        {
            "price": 2100,
            "deep_link": "https://www.kiwi.com/deep?from=YYZ&to=TYO&v=2",
            "duration": {"total": 72000},
            "route": [
                {"airline": "UA", "flyFrom": "YYZ", "flyTo": "ORD", "flight_no": 123},
                {"airline": "UA", "flyFrom": "ORD", "flyTo": "NRT", "flight_no": 456},
            ],
        },
    ]
}


def test_kiwi_normalize_returns_sorted_results() -> None:
    provider = KiwiProvider(api_key="test")
    results = provider._normalize(SAMPLE_KIWI_RESPONSE)
    assert len(results) == 2
    assert results[0].price == 1587
    assert results[0].airline == "AC"
    assert results[0].stops == 0
    assert results[1].price == 2100
    assert results[1].stops == 1


def test_kiwi_normalize_duration() -> None:
    provider = KiwiProvider(api_key="test")
    results = provider._normalize(SAMPLE_KIWI_RESPONSE)
    assert results[0].duration_minutes == 870  # 52200 // 60


def test_kiwi_normalize_handles_empty_response() -> None:
    provider = KiwiProvider(api_key="test")
    results = provider._normalize({"data": []})
    assert results == []


def test_kiwi_normalize_handles_missing_fields() -> None:
    provider = KiwiProvider(api_key="test")
    results = provider._normalize({"data": [{"price": 500}]})
    assert results == []


def test_kiwi_normalize_skips_zero_price() -> None:
    provider = KiwiProvider(api_key="test")
    results = provider._normalize(
        {
            "data": [
                {
                    "price": 0,
                    "route": [{"airline": "AC"}],
                    "duration": {"total": 3600},
                }
            ]
        }
    )
    assert results == []


def test_kiwi_is_configured() -> None:
    assert KiwiProvider(api_key="key123").is_configured() is True
    assert KiwiProvider(api_key="").is_configured() is False
