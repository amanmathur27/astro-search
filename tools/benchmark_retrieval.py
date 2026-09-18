"""Reproducible offline retrieval benchmark, not a live-web quality score."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import statistics
import time
from unittest.mock import patch

from astro_search.core import AstroSearch
from astro_search.evidence import filter_evidence
from astro_search.interpretation import interpret
from astro_search.intent import classify
from astro_search.ranker import rank


def evaluate(cases):
    with patch("astro_search.core.SQLiteCache", return_value=None):
        engine = AstroSearch()
    details = []
    for case in cases:
        started = time.perf_counter()
        intent, entities = classify(case["query"])
        spec = interpret(case["query"])
        detail = {
            "id": case["id"], "intent": intent, "answer_status": "not_evaluated",
            "candidates": bool(case.get("candidates")) or bool(case.get("evidence_candidates")),
        }
        # Optional labels: a case contributes only to metrics it actually labels.
        if "expected_scope" in case:
            detail["scope_correct"] = spec.scope == case["expected_scope"]
        if "expected_subject" in case:
            detail["subject_correct"] = spec.subject == case["expected_subject"]
        if "expected_property" in case:
            detail["property_correct"] = spec.property == case["expected_property"]
        if detail["candidates"]:
            selected = {s.name for s in engine._select(intent, entities, case.get("category", "all"))}
            detail["required_sources_selected"] = set(case.get("required_sources", [])).issubset(selected)
            detail["selected_sources"] = sorted(selected)
            ranked = rank(deepcopy(case["candidates"]), case["query"], intent)
            ids = [r["id"] for r in ranked]
            relevant = set(case["relevant_ids"])
            k = min(5, len(ids))
            first = next((i for i, ident in enumerate(ids, 1) if ident in relevant), None)
            detail.update(
                intent_correct=intent == case["intent"],
                ranked_ids=ids,
                precision_at_5=len(set(ids[:5]) & relevant) / 5,
                precision_at_available_k=len(set(ids[:k]) & relevant) / k if k else 0,
                recall_at_5=len(set(ids[:5]) & relevant) / len(relevant) if relevant else 0,
                reciprocal_rank=1 / first if first else 0,
            )
        if case.get("evidence_candidates"):
            for row in deepcopy(case["evidence_candidates"]):
                row.setdefault("extra", {})
                row["extra"].setdefault("document_url", row.get("url", ""))
            _, status = filter_evidence(case["evidence_candidates"], spec)
            detail["evidence_status"] = status
            detail["evidence_correct"] = status == case.get("expect_answer_status")
        detail["latency_ms"] = (time.perf_counter() - started) * 1000
        details.append(detail)
    if not details:
        raise ValueError("Benchmark requires at least one labeled case")
    latencies = sorted(row["latency_ms"] for row in details)
    ranking = [r for r in details if r.get("candidates")]
    if not ranking:
        raise ValueError("Benchmark requires at least one ranking case")
    summary = {
        "scope": "Offline fixture interpretation/routing/ranking only; no live retrieval, citations or scientific verification",
        "cases": len(details),
        "intent_accuracy": statistics.mean(r["intent_correct"] for r in ranking),
        "source_coverage": statistics.mean(r["required_sources_selected"] for r in ranking),
        "mean_reciprocal_rank": statistics.mean(r["reciprocal_rank"] for r in ranking),
        "mean_precision_at_5": statistics.mean(r["precision_at_5"] for r in ranking),
        "mean_recall_at_5": statistics.mean(r["recall_at_5"] for r in ranking),
        "median_latency_ms": statistics.median(latencies),
        "p95_latency_ms": latencies[min(len(latencies) - 1, int(len(latencies) * .95))],
    }
    for metric in ("scope", "subject", "property", "evidence"):
        labeled = [r for r in details if metric + "_correct" in r]
        if labeled:
            summary[metric + "_accuracy"] = statistics.mean(r[metric + "_correct"] for r in labeled)
    summary["details"] = details
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=Path(__file__).resolve().parents[1] / "benchmarks" / "retrieval.json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    result = evaluate(json.loads(args.cases.read_text(encoding="utf-8")))
    text = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text)
    perfect = (result["intent_accuracy"] == result["source_coverage"] == 1
               and result["mean_reciprocal_rank"] >= .9)
    # Optional labeled metrics, when present in the case file, must be perfect.
    for metric in ("scope_accuracy", "subject_accuracy", "property_accuracy", "evidence_accuracy"):
        if metric in result and result[metric] != 1:
            perfect = False
    return 0 if perfect else 1


if __name__ == "__main__":
    raise SystemExit(main())
