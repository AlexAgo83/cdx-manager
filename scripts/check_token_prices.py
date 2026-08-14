#!/usr/bin/env python3
"""Compare cdx's token price table against what the vendors publish.

Deliberately not part of `npm test`: it needs the network, and a CI job that
fails because a vendor's marketing page moved is a job people learn to ignore.
Run it when the staleness test asks, or before cutting a release.

    python3 scripts/check_token_prices.py               # report differences
    python3 scripts/check_token_prices.py --from-history # models you actually use
    python3 scripts/check_token_prices.py --json         # machine-readable

Exit code is 1 when a difference is found, so it can gate a release script.

`docs/token-prices-runbook.md` records where the numbers actually live and
which sources refuse to be read, so the next person does not rediscover it.

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
    token_prices,
)

SOURCES = {
    # Carries the numbers, but as a transposed table -- one column per model --
    # so an id and its price never share a line. Reported unverified, by design.
    "claude": "https://platform.claude.com/docs/en/about-claude/models/overview.md",
    # openai.com/api/pricing answers 403 to automated fetches, so this is a
    # third-party aggregator. Corroborate before trusting a change from it.
    "gpt": "https://modelpricing.ai/models/openai",
}
TIMEOUT_SECONDS = 20

#: Output-to-input ratios seen in the wild. A model outside this set is not
#: necessarily wrong, but it is a structural surprise worth a human look --
#: exactly the shape of the discovery that OpenAI bills output at 6x where
#: Anthropic bills 5x, which a price-only check would have missed.
KNOWN_OUTPUT_RATIOS = (5.0, 6.0)


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


def ratio_surprises(models=None):
    """Models whose output-to-input ratio is not one we have seen before."""
    surprises = []
    for model, rate in sorted((models or DEFAULT_TOKEN_PRICES).items()):
        ratio = round(rate["output"] / rate["input"], 3)
        if ratio not in KNOWN_OUTPUT_RATIOS:
            surprises.append({"model": model, "ratio": ratio})
    return surprises


def models_in_use(env=None):
    """Models seen in real launch history, and whether cdx can price them.

    The calendar says *when* to look; this says *what changed*. A model
    appearing here unpriced is the actual trigger for a corrective release --
    somebody started using something the table has never heard of.
    """
    from src.config import get_cdx_home
    from src.session_store import create_session_store

    history_path = Path(get_cdx_home(env)) / "state" / "launch_history.jsonl"
    if not history_path.is_file():
        return []
    store = create_session_store(str(history_path.parent.parent))
    seen = {}
    for entry in store["list_launch_history"](limit=0):
        model = entry.get("usage_model")
        if model:
            seen[model] = seen.get(model, 0) + 1
    table = token_prices(env)[0]
    return [{"model": m, "runs": n, "priced": m in table}
            for m, n in sorted(seen.items(), key=lambda kv: -kv[1])]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--from-history", action="store_true",
                        help="list the models this machine actually ran, priced or not")
    args = parser.parse_args()

    if args.from_history:
        rows = models_in_use()
        if args.json:
            print(json.dumps(rows, indent=2))
            return 0
        if not rows:
            print("No run in launch history records a model yet.")
            return 0
        print(f"{'MODEL':28} {'RUNS':>6}  PRICED")
        for row in rows:
            print(f"{row['model']:28} {row['runs']:>6}  {'yes' if row['priced'] else 'NO'}")
        missing = [r["model"] for r in rows if not r["priced"]]
        if missing:
            print(f"\nUnpriced and in use: {', '.join(missing)}")
            print("See docs/token-prices-runbook.md before adding them.")
        return 1 if missing else 0

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
        for surprise in ratio_surprises():
            print(f"\nratio surprise: {surprise['model']} bills output at "
                  f"{surprise['ratio']}x input, not {' or '.join(str(r) for r in KNOWN_OUTPUT_RATIOS)}x. "
                  "Check the weighting assumptions, not just the number.")
        if differs:
            print("\nUpdate DEFAULT_TOKEN_PRICES and TOKEN_PRICES_REVIEWED in "
                  "src/run_usage.py, then cut a corrective release. "
                  "docs/token-prices-runbook.md has the steps.")
    return 1 if any(r["status"] == "differs" for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
