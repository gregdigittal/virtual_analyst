"""Statistical anomaly detection for financial ratios (REM-01 / CR-S2 / ISA 520).

Provides Z-score and IQR-based pre-screening before LLM narrative generation.
Satisfies ISA 520 requirements: expectation, threshold, investigation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class StatisticalAnomaly:
    """A statistically identified anomaly in financial ratios."""

    ratio_key: str
    value: float
    method: str  # "z_score" or "iqr"
    severity: str  # "info", "warning", "critical"
    z_score: float | None = None
    iqr_deviation: float | None = None
    benchmark_median: float | None = None
    description: str = ""


# ISA 520 thresholds: flag anomalies only when > 2σ from control limits (SR-5)
Z_SCORE_WARNING = 2.0
Z_SCORE_CRITICAL = 3.0

# IQR multipliers for outlier detection (Tukey's fences)
IQR_WARNING = 1.5
IQR_CRITICAL = 3.0


def _severity_from_z(z: float) -> str:
    """Classify severity based on absolute Z-score."""
    abs_z = abs(z)
    if abs_z >= Z_SCORE_CRITICAL:
        return "critical"
    if abs_z >= Z_SCORE_WARNING:
        return "warning"
    return "info"


def _severity_from_iqr(deviation: float) -> str:
    """Classify severity based on IQR deviation multiplier."""
    abs_dev = abs(deviation)
    if abs_dev >= IQR_CRITICAL:
        return "critical"
    if abs_dev >= IQR_WARNING:
        return "warning"
    return "info"


def detect_anomalies_zscore(
    ratios: dict[str, float | None],
    benchmarks: dict[str, dict[str, float]] | None = None,
) -> list[StatisticalAnomaly]:
    """Detect anomalies using Z-score method against industry benchmarks.

    Requires benchmarks with 'median' and 'std' keys per ratio.
    Falls back to IQR method if std is not available.
    """
    if not benchmarks:
        return []
    anomalies: list[StatisticalAnomaly] = []
    for key, value in ratios.items():
        if key.startswith("_") or value is None:
            continue
        bench = benchmarks.get(key)
        if not bench or "median" not in bench:
            continue
        median = bench["median"]
        std = bench.get("std")
        if std and std > 0:
            z = (value - median) / std
            sev = _severity_from_z(z)
            if sev != "info":
                label = key.replace("_", " ").title()
                anomalies.append(StatisticalAnomaly(
                    ratio_key=key,
                    value=value,
                    method="z_score",
                    severity=sev,
                    z_score=round(z, 2),
                    benchmark_median=median,
                    description=f"{label} = {value:.4f} is {abs(z):.1f}σ from industry median ({median:.4f})",
                ))
    return anomalies


def detect_anomalies_iqr(
    ratios: dict[str, float | None],
    benchmarks: dict[str, dict[str, float]] | None = None,
) -> list[StatisticalAnomaly]:
    """Detect anomalies using IQR (interquartile range) method.

    Requires benchmarks with 'p25' and 'p75' keys per ratio.
    """
    if not benchmarks:
        return []
    anomalies: list[StatisticalAnomaly] = []
    for key, value in ratios.items():
        if key.startswith("_") or value is None:
            continue
        bench = benchmarks.get(key)
        if not bench or "p25" not in bench or "p75" not in bench:
            continue
        p25 = bench["p25"]
        p75 = bench["p75"]
        iqr = p75 - p25
        if iqr <= 0:
            continue
        median = bench.get("median", (p25 + p75) / 2)
        if value < p25:
            deviation = (p25 - value) / iqr
        elif value > p75:
            deviation = (value - p75) / iqr
        else:
            continue  # within IQR, no anomaly
        sev = _severity_from_iqr(deviation)
        if sev != "info":
            label = key.replace("_", " ").title()
            direction = "below" if value < p25 else "above"
            anomalies.append(StatisticalAnomaly(
                ratio_key=key,
                value=value,
                method="iqr",
                severity=sev,
                iqr_deviation=round(deviation, 2),
                benchmark_median=median,
                description=f"{label} = {value:.4f} is {deviation:.1f}× IQR {direction} the interquartile range",
            ))
    return anomalies


def detect_anomalies_statistical(
    ratios: dict[str, float | None],
    benchmarks: dict[str, dict[str, float]] | None = None,
) -> list[StatisticalAnomaly]:
    """Combined statistical anomaly detection: Z-score + IQR.

    Returns deduplicated list (Z-score takes priority when both flag the same ratio).
    ISA 520 compliant: establishes expectation (benchmarks), threshold (2σ/1.5×IQR),
    and investigation trigger (anomaly list for downstream review).
    """
    z_anomalies = detect_anomalies_zscore(ratios, benchmarks)
    iqr_anomalies = detect_anomalies_iqr(ratios, benchmarks)
    # Deduplicate: Z-score takes priority
    seen_keys = {a.ratio_key for a in z_anomalies}
    combined = list(z_anomalies)
    for a in iqr_anomalies:
        if a.ratio_key not in seen_keys:
            combined.append(a)
    # Sort by severity: critical first
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    combined.sort(key=lambda a: severity_order.get(a.severity, 3))
    return combined


def anomalies_to_dict(anomalies: list[StatisticalAnomaly]) -> list[dict[str, Any]]:
    """Convert anomalies to JSON-serializable dicts."""
    return [
        {
            "ratio_key": a.ratio_key,
            "value": a.value,
            "method": a.method,
            "severity": a.severity,
            "z_score": a.z_score,
            "iqr_deviation": a.iqr_deviation,
            "benchmark_median": a.benchmark_median,
            "description": a.description,
        }
        for a in anomalies
    ]
