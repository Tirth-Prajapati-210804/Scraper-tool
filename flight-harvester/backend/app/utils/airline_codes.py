from __future__ import annotations

AIRLINE_MAP: dict[str, str] = {
    # Full names → IATA codes
    "EMIRATES": "EK",
    "DELTA": "DL",
    "LUFTHANSA": "LH",
    "LUFTHANSANA": "LH",
    "LUTHANSA": "LH",
    "AUSTRIAN": "OS",
    "JAPAN": "JL",
    "KOREAN AIR": "KE",
    "CATHAY PACIFIC": "CX",
    "EVA AIR": "BR",
    "AIR CANADA": "AC",
    "TURKISH AIRLINES": "TK",
    "QATAR AIRWAYS": "QR",
    "ANA": "NH",
    "SINGAPORE AIRLINES": "SQ",
    "AIR FRANCE": "AF",
    "BRITISH AIRWAYS": "BA",
    "SWISS": "LX",
    # Short codes — pass through
    "AC": "AC",
    "UA": "UA",
    "AA": "AA",
    "CP": "CP",
    "KA": "KA",
    "CE": "CE",
    "CA": "CA",
    "QA": "QA",
    "AF": "AF",
    "AI": "AI",
    "EA": "EA",
    "PA": "PA",
    "TA": "TA",
    "NZ": "NZ",
    "CS": "CS",
    "HKA": "HKA",
    "KLM": "KLM",
    "DL": "DL",
    "EK": "EK",
    # Partial matches found in client data
    "J A": "JL",
    "EVA A": "BR",
    "K A": "KA",
    "A F": "AF",
    "A I": "AI",
    "C A": "CA",
    "C P": "CP",
}


def normalize_airline(raw: str) -> str:
    if not raw or not raw.strip():
        return "-"
    cleaned = raw.strip().upper()
    if cleaned in AIRLINE_MAP:
        return AIRLINE_MAP[cleaned]
    if len(cleaned) <= 3:
        return cleaned
    first_word = cleaned.split()[0]
    if first_word in AIRLINE_MAP:
        return AIRLINE_MAP[first_word]
    return cleaned[:2]
