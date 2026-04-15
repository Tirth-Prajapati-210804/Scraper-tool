"""
Mock flight provider — generates realistic dummy data for pipeline testing.

Enable by setting MOCK_PROVIDER_KEY=any-non-empty-value in .env.
Never enable in production (the key "MOCK_PROVIDER_KEY" is a dev-only sentinel).

HOW IT WORKS:
  For any origin/destination/date combination, it seeds Python's random number
  generator using an MD5 hash of the route+date string. This makes the output
  deterministic — the same search always returns the same fake prices — so test
  runs are reproducible without needing real API keys.
"""
from __future__ import annotations

import hashlib
import random
from datetime import date

from app.providers.base import ProviderResult

# Realistic airline codes used on common international routes
_AIRLINES = ["AC", "WS", "UA", "AA", "DL", "EK", "CX", "JL", "KE", "NH", "SQ", "TK"]

# Fake price range in CAD — wide enough to cover typical long-haul fares
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
        """
        Generate 2–5 fake flight offers for the given route and date.

        The MD5 seed ensures the same route+date always produces the same output,
        making tests fully reproducible without needing real API credentials.
        """
        # Build a deterministic seed from the route + date so re-running the
        # same search always returns the same fake prices (reproducible tests)
        seed_str = f"{origin}{destination}{depart_date.isoformat()}"
        seed = int(hashlib.md5(seed_str.encode()).hexdigest(), 16) % (2**32)
        rng = random.Random(seed)

        results: list[ProviderResult] = []
        num_results = rng.randint(2, 5)  # simulate a realistic number of offers

        for _ in range(num_results):
            price = round(rng.uniform(*_PRICE_RANGE), 2)
            airline = rng.choice(_AIRLINES)
            # Weight distribution: 50% direct, 35% one-stop, 15% two-stop
            stops = rng.choices([0, 1, 2], weights=[50, 35, 15])[0]
            # Duration formula: base 7–14h for long-haul, +3h per stop for connections
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

        # Return cheapest first — mirrors how real providers rank results
        results.sort(key=lambda r: r.price)
        return results

    async def close(self) -> None:
        pass
