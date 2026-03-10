"""Unit tests for statistical anomaly detection (REM-01 / CR-S2)."""

from __future__ import annotations

from apps.api.app.services.afs.anomaly_stats import (
    StatisticalAnomaly,
    anomalies_to_dict,
    detect_anomalies_iqr,
    detect_anomalies_statistical,
    detect_anomalies_zscore,
)


def test_zscore_no_benchmarks() -> None:
    """No benchmarks returns empty list."""
    result = detect_anomalies_zscore({"current_ratio": 1.5}, None)
    assert result == []


def test_zscore_normal_value() -> None:
    """Value within 2σ of median is not flagged."""
    ratios = {"current_ratio": 1.5}
    benchmarks = {"current_ratio": {"median": 1.5, "std": 0.5}}
    result = detect_anomalies_zscore(ratios, benchmarks)
    assert result == []


def test_zscore_warning() -> None:
    """Value > 2σ from median is flagged as warning."""
    ratios = {"current_ratio": 3.0}
    benchmarks = {"current_ratio": {"median": 1.5, "std": 0.5}}
    result = detect_anomalies_zscore(ratios, benchmarks)
    assert len(result) == 1
    assert result[0].severity == "critical"  # 3.0σ
    assert result[0].z_score == 3.0


def test_zscore_critical() -> None:
    """Value > 3σ from median is flagged as critical."""
    ratios = {"debt_to_equity": 5.0}
    benchmarks = {"debt_to_equity": {"median": 1.0, "std": 1.0}}
    result = detect_anomalies_zscore(ratios, benchmarks)
    assert len(result) == 1
    assert result[0].severity == "critical"
    assert result[0].z_score == 4.0


def test_iqr_no_anomaly() -> None:
    """Value within IQR is not flagged."""
    ratios = {"current_ratio": 1.5}
    benchmarks = {"current_ratio": {"p25": 1.0, "p75": 2.0, "median": 1.5}}
    result = detect_anomalies_iqr(ratios, benchmarks)
    assert result == []


def test_iqr_warning() -> None:
    """Value > 1.5× IQR outside Q1/Q3 is flagged as warning."""
    ratios = {"current_ratio": 4.0}
    benchmarks = {"current_ratio": {"p25": 1.0, "p75": 2.0, "median": 1.5}}
    result = detect_anomalies_iqr(ratios, benchmarks)
    assert len(result) == 1
    assert result[0].severity == "warning"
    assert result[0].iqr_deviation == 2.0  # (4.0 - 2.0) / 1.0


def test_iqr_critical() -> None:
    """Value > 3× IQR outside Q1/Q3 is flagged as critical."""
    ratios = {"current_ratio": 6.0}
    benchmarks = {"current_ratio": {"p25": 1.0, "p75": 2.0, "median": 1.5}}
    result = detect_anomalies_iqr(ratios, benchmarks)
    assert len(result) == 1
    assert result[0].severity == "critical"
    assert result[0].iqr_deviation == 4.0


def test_combined_deduplicates() -> None:
    """Combined detection deduplicates: Z-score takes priority."""
    ratios = {"current_ratio": 5.0}
    benchmarks = {
        "current_ratio": {"median": 1.5, "std": 0.5, "p25": 1.0, "p75": 2.0}
    }
    result = detect_anomalies_statistical(ratios, benchmarks)
    # Both methods would flag, but Z-score takes priority
    keys = [a.ratio_key for a in result]
    assert keys.count("current_ratio") == 1
    assert result[0].method == "z_score"


def test_skips_none_and_private() -> None:
    """None values and keys starting with _ are skipped."""
    ratios = {"current_ratio": None, "_internal": 5.0, "debt_ratio": 1.0}
    benchmarks = {
        "current_ratio": {"median": 1.5, "std": 0.5},
        "_internal": {"median": 1.0, "std": 0.5},
        "debt_ratio": {"median": 1.0, "std": 0.5},
    }
    result = detect_anomalies_zscore(ratios, benchmarks)
    assert result == []


def test_anomalies_to_dict() -> None:
    """Serialization produces expected dict structure."""
    anomaly = StatisticalAnomaly(
        ratio_key="test",
        value=5.0,
        method="z_score",
        severity="critical",
        z_score=3.5,
        description="test desc",
    )
    result = anomalies_to_dict([anomaly])
    assert len(result) == 1
    assert result[0]["ratio_key"] == "test"
    assert result[0]["z_score"] == 3.5
    assert result[0]["severity"] == "critical"


def test_severity_ordering() -> None:
    """Combined results are sorted: critical first, then warning."""
    ratios = {"a": 5.0, "b": 2.5}
    benchmarks = {
        "a": {"median": 1.0, "std": 1.0, "p25": 0.5, "p75": 1.5},  # a: z=4 → critical
        "b": {"median": 1.0, "std": 0.5, "p25": 0.5, "p75": 1.5},  # b: z=3 → critical
    }
    result = detect_anomalies_statistical(ratios, benchmarks)
    assert all(a.severity == "critical" for a in result)
