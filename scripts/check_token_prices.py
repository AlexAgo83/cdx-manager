#!/usr/bin/env python3
"""Compare cdx's token price table against what the vendors publish.

Deliberately not part of `npm test`: it needs the network, and a CI job that
fails because a vendor's marketing page moved is a job people learn to ignore.
Run it when the staleness test asks, or before cutting a release.

    python3 scripts/check_token_prices.py            # report differences
    python3 scripts/check_token_prices.py --json     # machine-readable

Exit code is 1 when a difference is found, so it can gate a release script.

The vendor pages are read as text and matched loosely, because they are
marketing pages rather than an API. A row this cannot confirm is reported as
`unverified` and never as `ok`: "we could not check" must not read as a pass.
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.run_usage import (  # noqa: E402
    DEFAULT_TOKEN_PRICES,
    TOKEN_PRICES_MAX_AGE_DAYS,
    TOKEN_PRICES_REVIEWED,
)

SOURCES = {
    "claude": "https://platform.claude.com/docs/en/about-claude/models/overview.md",
    "gpt": "https://modelpricing.ai/models/openai",
}
TIMEOUT_SECONDS = 20


def _fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "cdx-price-check"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, OSError, ValueError) as error:
        return f"__unreachable__ {error}"


def _prices_near(text, model):
    """Every dollar figure on the line mentioning this model.

    Row-per-model layouts only. Anthropic's model table is transposed -- one
    column per model -- so an id and its price never share a line and this
    finds nothing. That is reported as unverified rather than worked around:
    a scraper taught the shape of one vendor's marketing table is a scraper
    that breaks silently the next time it is redesigned.
    """
    found = []
    for line in text.splitlines():
        if model.lower() in line.lower().replace(" ", "-"):
            found += [float(v) for v in re.findall(r"\$\s?([0-9]+(?:\.[0-9]+)?)", line)]
    return found


def check(models=None):
    pages = {key: _fetch(url) for key, url in SOURCES.items()}
    results = []
    for model, rate in sorted((models or DEFAULT_TOKEN_PRICES).items()):
        page = pages["claude"] if model.startswith("claude") else pages["gpt"]
        if page.startswith("__unreachable__"):
            results.append({"model": model, "status": "unverified",
                            "detail": page.removeprefix("__unreachable__ ").strip()})
            continue
        seen = _prices_near(page, model)
        if not seen:
            results.append({"model": model, "status": "unverified",
                            "detail": "no row-per-model price on the page; check by hand"})
        elif rate["input"] in seen and rate["output"] in seen:
            results.append({"model": model, "status": "ok"})
        else:
            results.append({"model": model, "status": "differs",
                            "detail": f"table says {rate['input']}/{rate['output']}, "
                                      f"page shows {sorted(set(seen))}"})
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    results = check()
    if args.json:
        print(json.dumps({"reviewed": TOKEN_PRICES_REVIEWED,
                          "max_age_days": TOKEN_PRICES_MAX_AGE_DAYS,
                          "results": results}, indent=2))
    else:
        print(f"Table last reviewed {TOKEN_PRICES_REVIEWED} "
              f"(stale after {TOKEN_PRICES_MAX_AGE_DAYS} days)\n")
        for row in results:
            mark = {"ok": "  ok", "differs": "DIFF", "unverified": "  ??"}[row["status"]]
            print(f"{mark}  {row['model']:24} {row.get('detail', '')}")
        differs = [r for r in results if r["status"] == "differs"]
        unverified = [r for r in results if r["status"] == "unverified"]
        print(f"\n{len(differs)} differing, {len(unverified)} unverified, "
              f"{len(results) - len(differs) - len(unverified)} confirmed.")
        if differs:
            print("\nUpdate DEFAULT_TOKEN_PRICES and TOKEN_PRICES_REVIEWED in "
                  "src/run_usage.py, then cut a corrective release.")
    return 1 if any(r["status"] == "differs" for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
