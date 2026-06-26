"""Unit tests for Stage A fairness and blocked protected characteristics."""
import pytest
from app.ranking.stage_a_reranker import _validate_features, BLOCKED_FEATURES


def test_blocked_features_raise_error():
    """Verify any protected characteristic proxy triggers ValueError."""
    for feat in BLOCKED_FEATURES:
        with pytest.raises(ValueError, match="protected-characteristic proxies"):
            _validate_features({"retrieval_score", feat})


def test_clean_features_pass():
    """Verify legitimate features pass validation."""
    _validate_features({"retrieval_score", "domain_years", "education_level"})
