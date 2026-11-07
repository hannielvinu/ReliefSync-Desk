import asyncio
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

import httpx
from rapidfuzz.fuzz import ratio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import Settings  # noqa: E402
from app.extractor import Extractor  # noqa: E402


async def main() -> None:
    settings = Settings()
    dataset = [
        json.loads(line)
        for line in (ROOT / "data/eval/labeled_messages.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line
    ]
    groups: dict = defaultdict(list)
    modes: Counter = Counter()
    latencies, details = [], []
    async with httpx.AsyncClient() as client:
        extractor = Extractor(settings, client)
        for label in dataset:
            start = time.perf_counter()
            actual, mode = await extractor.extract(label["text"])
            latencies.append((time.perf_counter() - start) * 1000)
            modes[mode] += 1
            checks = {
                "intent_accuracy": actual.intent == label["intent"],
                "category_accuracy": actual.category == label["category"],
                "item_accuracy": ratio(actual.item_en.casefold(), label["item_en"].casefold())
                >= 80,
                "location_accuracy": actual.location_text.casefold()
                == label["location_text"].casefold(),
                "urgency_within_one": abs(actual.urgency - label["urgency"]) <= 1,
                "misinformation_accuracy": actual.possible_misinformation
                == label["possible_misinformation"],
            }
            groups[label["language_group"]].append(checks)
            groups["overall"].append(checks)
            details.append(
                {
                    "text": label["text"],
                    "expected": label,
                    "actual": actual.model_dump(),
                    "extractor": mode,
                    "checks": checks,
                }
            )

    def metrics(rows: list[dict]) -> dict:
        return {
            "count": len(rows),
            **{key: round(sum(row[key] for row in rows) / len(rows), 4) for key in rows[0]},
        }

    report = {
        "date": datetime.now(UTC).isoformat(),
        "dataset_size": len(dataset),
        "dataset_kind": "Synthetic template-based smoke benchmark; not evidence of real-world accuracy",
        "extractor_used": dict(modes),
        "median_latency_ms": round(statistics.median(latencies), 3),
        "command": "python scripts/eval.py",
        "overall": metrics(groups["overall"]),
        "per_language": {key: metrics(rows) for key, rows in groups.items() if key != "overall"},
        "details": details,
    }
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports/eval_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    summary = f"# Evaluation\n\nSynthetic smoke benchmark. Extractor counts: {dict(modes)}.\n\nDataset: {len(dataset)}. Date: {report['date']}. Median latency: {report['median_latency_ms']} ms.\n\n"
    summary += "\n".join(
        f"- {key}: {value:.1%}" for key, value in report["overall"].items() if key != "count"
    )
    summary += "\n\nReproduce: `python scripts/eval.py`. These templates are not a held-out real-world benchmark.\n"
    (ROOT / "reports/eval_report.md").write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    asyncio.run(main())
