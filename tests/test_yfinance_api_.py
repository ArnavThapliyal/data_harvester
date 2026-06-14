import requests
import pandas as pd
import json
from pathlib import Path

# CHANGE THIS
BASE_URL = "http://65.0.104.9"

OUTPUT_DIR = Path("api_downloads")
OUTPUT_DIR.mkdir(exist_ok=True)

def save_json(url, filename):
    r = requests.get(url, timeout=30)
    r.raise_for_status()

    data = r.json()

    with open(OUTPUT_DIR / filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Saved JSON: {filename}")
    return data


# --------------------------------------------------
# Download API info
# --------------------------------------------------
api_info = save_json(
    f"{BASE_URL}/",
    "api_info.json"
)

# Optional CSV export of endpoint list
if isinstance(api_info, dict) and "endpoints" in api_info:
    endpoints = []

    for endpoint, details in api_info["endpoints"].items():
        row = {"endpoint": endpoint}

        if isinstance(details, dict):
            row.update(details)

        endpoints.append(row)

    pd.DataFrame(endpoints).to_csv(
        OUTPUT_DIR / "api_endpoints.csv",
        index=False
    )

    print("Saved CSV: api_endpoints.csv")


# --------------------------------------------------
# Download symbols
# --------------------------------------------------
symbols_data = save_json(
    f"{BASE_URL}/symbols",
    "symbols.json"
)

if "symbols" in symbols_data:
    df = pd.DataFrame(symbols_data["symbols"])

    df.to_csv(
        OUTPUT_DIR / "symbols.csv",
        index=False
    )

    print(f"Saved CSV: symbols.csv ({len(df)} symbols)")

print("\nDone.")