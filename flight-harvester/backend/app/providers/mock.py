"""
Mock flight provider — generates realistic dummy data for pipeline testing.

Enable by setting MOCK_PROVIDER_KEY=any-non-empty-value in .env.
Never enable in production (the key "MOCK_PROVIDER_KEY" is a dev-only sentinel).
"""
from __future__ import annotations

import hashlib
import random
from datetime import date

from app.providers.base import ProviderResult

# Realistic airline codes used on common routes
_AIRLINES = ["AC", "WS", "UA", "AA", "DL", "EK", "CX", "JL", "KE", "NH", "SQ", "TK"]

# Realistic price bands per region pair (CAD)
_PRICE_RANGE = (350, 2200)


class MockProvider:
    """Returns deterministic-but-varied fake flight data for local testing."""

    name = "mock"

    def __init__(self, key: str = "mock") -> None:
        self.key = key

    def is_configured(self) -> bool:
        return bool(self.key)

    async def search_one_way(
        self,
        origin: str,
        destination: str,
        depart_date: date,
        adults: int = 1,
        cabin: str = "economy",
    ) -> list[ProviderResult]:
        # Seed RNG from the route + date so results are deterministic per run
        seed_str = f"{origin}{destination}{depart_date.isoformat()}"
        seed = int(hashlib.md5(seed_str.encode()).hexdigest(), 16) % (2**32)
        rng = random.Random(seed)

        results: list[ProviderResult] = []
        num_results = rng.randint(2, 5)

        for _ in range(num_results):
            price = round(rng.uniform(*_PRICE_RANGE), 2)
            airline = rng.choice(_AIRLINES)
            stops = rng.choices([0, 1, 2], weights=[50, 35, 15])[0]
            # Duration: direct ~8-14h, 1-stop +3h, 2-stop +6h
            base_hours = rng.uniform(7, 14)
            duration_minutes = int((base_hours + stops * 3) * 60)

            results.append(
                ProviderResult(
                    price=price,
                    currency="CAD",
                    airline=airline,
                    deep_link=f"https://example.com/book/{origin}-{destination}-{depart_date}",
                    provider="mock",
                    stops=stops,
                    duration_minutes=duration_minutes,
                )
            )

        results.sort(key=lambda r: r.price)
        return results

    async def close(self) -> None:
        pass
