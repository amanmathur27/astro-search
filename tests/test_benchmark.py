"""Offline benchmark smoke and metric denominator regression."""
import json
from pathlib import Path
import pytest
from tools.benchmark_retrieval import evaluate


def test_labeled_retrieval_baseline():
    cases = json.loads((Path(__file__).resolve().parents[1] / 'benchmarks' / 'retrieval.json').read_text())
    result = evaluate(cases)
    assert result['intent_accuracy'] == 1, result['details']
    assert result['source_coverage'] == 1, result['details']
    assert result['mean_reciprocal_rank'] >= .9
    assert result['mean_precision_at_5'] == pytest.approx(.2)
    assert result['mean_recall_at_5'] == 1


def test_empty_benchmark_rejected():
    with pytest.raises(ValueError):
        evaluate([])
