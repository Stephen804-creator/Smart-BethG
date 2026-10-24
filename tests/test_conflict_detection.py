from services.conflict_detection import pair_conflict_signal, find_pairwise_conflicts


def test_detects_negation_disagreement_without_choosing_truth():
    result = pair_conflict_signal(
        "The service is available in production",
        "The service is not available in production",
    )
    assert result is not None
    assert result["kind"] == "polarity_difference"


def test_detects_numeric_disagreement_on_similar_claims():
    result = pair_conflict_signal(
        "The retention period is 30 days",
        "The retention period is 90 days",
    )
    assert result is not None
    assert result["kind"] == "numeric_difference"


def test_ignores_unrelated_statements():
    assert pair_conflict_signal(
        "Python is used for data analysis",
        "The dashboard has a blue sidebar",
    ) is None


def test_pairwise_results_preserve_source_labels():
    results = find_pairwise_conflicts([
        {"content": "The limit is 10 requests", "citation": "policy-a"},
        {"content": "The limit is 100 requests", "citation": "policy-b"},
    ])
    assert len(results) == 1
    assert results[0]["left_source"] == "policy-a"
    assert results[0]["right_source"] == "policy-b"
