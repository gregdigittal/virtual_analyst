"""Markov Chain Engine — PIM-3.1 through PIM-3.5.

81-state Markov model over the Cartesian product of 4 discretised dimensions:
  gdp_state        (0=contraction, 1=neutral, 2=expansion)
  sentiment_state  (0=negative,    1=neutral,  2=positive)
  quality_state    (0=weak,        1=average,  2=strong)
  momentum_state   (0=declining,   1=stable,   2=improving)

State index = gdp*27 + sentiment*9 + quality*3 + momentum  ∈ [0, 80].

PIM-3.1: Model definition (state space, encoding/decoding).
PIM-3.2: Transition matrix estimation from historical observations + Laplace smoothing (SR-4).
PIM-3.3: QuantEcon MarkovChain wrapper — steady-state distribution, ergodicity check.
PIM-3.5: Numba-JIT accelerated hot loops for transition counting and probability mass.

SR-4: Laplace smoothing with α=1.0 pseudocount prevents zero-probability cells.
SR-1: All computations derived from observable data — no fabrication.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Optional Numba — graceful degradation when not installed (PIM-3.5)
# ---------------------------------------------------------------------------
try:
    from numba import njit as _njit  # type: ignore[import]

    _NUMBA_AVAILABLE = True
except ImportError:  # pragma: no cover
    _NUMBA_AVAILABLE = False

    def _njit(func):  # type: ignore[misc]
        return func


# ---------------------------------------------------------------------------
# Optional QuantEcon — graceful degradation when not installed (PIM-3.3)
# ---------------------------------------------------------------------------
try:
    from quantecon import MarkovChain as _QEMarkovChain  # type: ignore[import]

    _QUANTECON_AVAILABLE = True
except ImportError:  # pragma: no cover
    _QUANTECON_AVAILABLE = False
    _QEMarkovChain = None

# ---------------------------------------------------------------------------
# PIM-3.1 — State space definition
# ---------------------------------------------------------------------------

N_DIMS = 4
N_LEVELS = 3  # 0=low/neg/declining, 1=medium/neutral/stable, 2=high/pos/improving
N_STATES = N_LEVELS**N_DIMS  # 81

# Dimension strides for state encoding
_STRIDES = (27, 9, 3, 1)  # gdp, sentiment, quality, momentum

# Human-readable level labels per dimension
_DIM_LABELS: tuple[tuple[str, str, str], ...] = (
    ("contraction", "neutral", "expansion"),    # gdp
    ("negative", "neutral", "positive"),         # sentiment
    ("weak", "average", "strong"),               # quality
    ("declining", "stable", "improving"),        # momentum
)


def encode_state(gdp: int, sentiment: int, quality: int, momentum: int) -> int:
    """Encode a 4-tuple of dimension levels to a state index [0, 80].

    Each dimension must be in {0, 1, 2}.  (PIM-3.1)
    """
    for val, name in zip((gdp, sentiment, quality, momentum),
                          ("gdp", "sentiment", "quality", "momentum")):
        if val not in (0, 1, 2):
            raise ValueError(f"{name} must be 0, 1, or 2; got {val}")
    return gdp * 27 + sentiment * 9 + quality * 3 + momentum


def decode_state(state_index: int) -> tuple[int, int, int, int]:
    """Decode a state index to (gdp, sentiment, quality, momentum).  (PIM-3.1)"""
    if not 0 <= state_index < N_STATES:
        raise ValueError(f"state_index must be in [0, {N_STATES - 1}]; got {state_index}")
    gdp = state_index // 27
    rem = state_index % 27
    sentiment = rem // 9
    rem = rem % 9
    quality = rem // 3
    momentum = rem % 3
    return gdp, sentiment, quality, momentum


def state_label(state_index: int) -> str:
    """Human-readable label for a state index.  e.g. 'expansion/positive/strong/improving'"""
    gdp, sentiment, quality, momentum = decode_state(state_index)
    return (
        f"{_DIM_LABELS[0][gdp]}/"
        f"{_DIM_LABELS[1][sentiment]}/"
        f"{_DIM_LABELS[2][quality]}/"
        f"{_DIM_LABELS[3][momentum]}"
    )


# ---------------------------------------------------------------------------
# PIM-3.5 — Numba-JIT hot loops
# ---------------------------------------------------------------------------

@_njit
def _count_transitions_jit(
    from_states: np.ndarray,  # int64 array of shape (T,)
    to_states: np.ndarray,    # int64 array of shape (T,)
    n_states: int,
    counts: np.ndarray,       # int64 array of shape (n_states, n_states) — modified in place
) -> None:
    """Count state transitions into a pre-allocated counts matrix.  (PIM-3.5)

    Pure numeric function — Numba @njit compatible.
    No Python objects, no exceptions, no dynamic dispatch.
    """
    for i in range(len(from_states)):
        counts[from_states[i], to_states[i]] += 1


@_njit
def _row_normalise_jit(
    counts: np.ndarray,  # float64 (n_states, n_states)
    alpha: float,        # Laplace smoothing pseudocount (SR-4)
    result: np.ndarray,  # float64 (n_states, n_states) — output
) -> None:
    """Laplace-smooth and row-normalise a transition count matrix.  (PIM-3.5 / SR-4)

    result[i, j] = (counts[i, j] + alpha) / sum_j(counts[i, j] + alpha)

    Pure numeric function — Numba @njit compatible.
    """
    n = counts.shape[0]
    for i in range(n):
        row_sum = 0.0
        for j in range(n):
            row_sum += counts[i, j] + alpha
        for j in range(n):
            result[i, j] = (counts[i, j] + alpha) / row_sum


# ---------------------------------------------------------------------------
# PIM-3.2 — Transition matrix estimation
# ---------------------------------------------------------------------------

@dataclass
class MarkovEstimationResult:
    """Output of estimate_transition_matrix.  (PIM-3.2)"""

    matrix: np.ndarray          # float64 (81, 81) — row-normalised probability matrix
    raw_counts: np.ndarray      # int64  (81, 81) — observed transition counts (pre-smoothing)
    n_observations: int         # total transitions observed
    alpha: float                # Laplace smoothing parameter used
    is_ergodic: bool | None     # None if QuantEcon not available


def estimate_transition_matrix(
    observations: list[tuple[int, int, int, int]],
    alpha: float = 1.0,
) -> MarkovEstimationResult:
    """Estimate an 81×81 Markov transition probability matrix from state observations.

    PIM-3.2: Statistical estimation using maximum-likelihood counts + Laplace smoothing.
    SR-4: Laplace smoothing (alpha=1.0) prevents zero-probability transitions.

    Args:
        observations: Ordered list of (gdp, sentiment, quality, momentum) tuples.
                      Must have at least 2 observations to produce any transitions.
        alpha:        Laplace smoothing pseudocount (default 1.0 per SR-4).

    Returns:
        MarkovEstimationResult with normalised probability matrix and diagnostics.
    """
    if len(observations) < 2:
        # Return uniform matrix when no data — fully Laplace-smoothed (1/81 everywhere)
        prob = np.full((N_STATES, N_STATES), alpha, dtype=np.float64)
        row_sums = prob.sum(axis=1, keepdims=True)
        prob /= row_sums
        is_ergodic = _check_ergodicity(prob)
        return MarkovEstimationResult(
            matrix=prob,
            raw_counts=np.zeros((N_STATES, N_STATES), dtype=np.int64),
            n_observations=0,
            alpha=alpha,
            is_ergodic=is_ergodic,
        )

    # Encode observations to state indices
    state_indices = np.array(
        [encode_state(*obs) for obs in observations], dtype=np.int64
    )

    # Build from/to arrays (consecutive pairs)
    from_states = state_indices[:-1]
    to_states = state_indices[1:]
    n_obs = len(from_states)

    # Count transitions via JIT loop
    raw_counts = np.zeros((N_STATES, N_STATES), dtype=np.int64)
    _count_transitions_jit(from_states, to_states, N_STATES, raw_counts)

    # Laplace-smooth and row-normalise via JIT loop
    matrix = np.zeros((N_STATES, N_STATES), dtype=np.float64)
    _row_normalise_jit(raw_counts.astype(np.float64), alpha, matrix)

    # Fix any NaN/Inf rows (occurs when alpha=0 and a state was never observed as a
    # "from" state — the row has all-zero counts and zero row_sum → 0/0 = NaN).
    # Replace those rows with uniform distribution (SR-4 compliant when alpha=0 is used
    # deliberately for testing; in production alpha>=1 prevents this entirely).
    nan_rows = ~np.isfinite(matrix).all(axis=1)
    if nan_rows.any():
        matrix[nan_rows] = 1.0 / N_STATES

    # Validate row sums (assert probability axiom)
    row_sums = matrix.sum(axis=1)
    if not np.allclose(row_sums, 1.0, atol=1e-9):
        raise ValueError(
            f"Row-normalisation failed: max deviation = {abs(row_sums - 1.0).max():.2e}"
        )

    is_ergodic = _check_ergodicity(matrix)

    return MarkovEstimationResult(
        matrix=matrix,
        raw_counts=raw_counts,
        n_observations=n_obs,
        alpha=alpha,
        is_ergodic=is_ergodic,
    )


# ---------------------------------------------------------------------------
# PIM-3.3 — QuantEcon wrapper
# ---------------------------------------------------------------------------

@dataclass
class SteadyStateResult:
    """Steady-state distribution and ergodicity diagnostics.  (PIM-3.3)"""

    stationary_distribution: np.ndarray  # float64 (81,) — long-run state probabilities
    is_ergodic: bool
    top_states: list[dict[str, Any]]     # top-10 states by stationary probability
    quantecon_available: bool            # False if QuantEcon not installed


def _check_ergodicity(matrix: np.ndarray) -> bool | None:
    """Check ergodicity via QuantEcon; return None if not installed.  (PIM-3.3)"""
    if not _QUANTECON_AVAILABLE or _QEMarkovChain is None:
        return None
    try:
        mc = _QEMarkovChain(matrix)
        return bool(mc.is_irreducible)
    except Exception:  # noqa: BLE001 — QuantEcon raises various errors
        return None


def compute_steady_state(matrix: np.ndarray) -> SteadyStateResult:
    """Compute steady-state (stationary) distribution of the Markov chain.  (PIM-3.3)

    Uses QuantEcon when available; falls back to power iteration otherwise.
    The stationary distribution π satisfies: π = π × T and sum(π) = 1.
    """
    # Validate input
    if matrix.shape != (N_STATES, N_STATES):
        raise ValueError(f"Expected ({N_STATES},{N_STATES}) matrix; got {matrix.shape}")
    row_sums = matrix.sum(axis=1)
    if not np.allclose(row_sums, 1.0, atol=1e-9):
        raise ValueError("Matrix rows must sum to 1.0 (not a valid probability matrix)")

    is_ergodic: bool
    stationary: np.ndarray

    if _QUANTECON_AVAILABLE and _QEMarkovChain is not None:
        mc = _QEMarkovChain(matrix)
        is_ergodic = bool(mc.is_irreducible)
        # QuantEcon returns shape (1, N) for ergodic chains
        sd = mc.stationary_distributions
        stationary = sd[0] if sd.ndim == 2 else sd
    else:
        # Power iteration fallback: multiply row vector by T until convergence
        is_ergodic = False  # unknown without QuantEcon
        pi = np.ones(N_STATES, dtype=np.float64) / N_STATES
        for _ in range(10_000):
            pi_new = pi @ matrix
            if np.allclose(pi_new, pi, atol=1e-12):
                break
            pi = pi_new
        stationary = pi

    # Top-10 states by stationary probability
    top_idx = np.argsort(stationary)[::-1][:10]
    top_states = [
        {
            "state_index": int(i),
            "label": state_label(int(i)),
            "probability": round(float(stationary[i]), 6),
        }
        for i in top_idx
    ]

    return SteadyStateResult(
        stationary_distribution=stationary,
        is_ergodic=is_ergodic,
        top_states=top_states,
        quantecon_available=_QUANTECON_AVAILABLE,
    )


# ---------------------------------------------------------------------------
# Forward simulation (used by portfolio scoring)
# ---------------------------------------------------------------------------

def simulate_trajectory(
    matrix: np.ndarray,
    initial_state: int,
    n_steps: int,
) -> list[int]:
    """Simulate a single Markov chain trajectory via random sampling.

    Returns a list of n_steps+1 state indices (including initial state).
    Not JIT-compiled — used for small simulations only (diagnostics, UI).
    For large MC sweeps, call the Numba path directly.
    """
    if not 0 <= initial_state < N_STATES:
        raise ValueError(f"initial_state must be in [0, {N_STATES - 1}]")
    rng = np.random.default_rng()
    trajectory: list[int] = [initial_state]
    state = initial_state
    for _ in range(n_steps):
        row = matrix[state]
        state = int(rng.choice(N_STATES, p=row))
        trajectory.append(state)
    return trajectory


def n_step_distribution(
    matrix: np.ndarray,
    initial_state: int,
    n_steps: int,
) -> np.ndarray:
    """Compute the exact n-step state distribution from initial_state.

    Returns float64 array of shape (81,) — probability of being in each state
    after exactly n_steps transitions.
    """
    if not 0 <= initial_state < N_STATES:
        raise ValueError(f"initial_state must be in [0, {N_STATES - 1}]")
    pi = np.zeros(N_STATES, dtype=np.float64)
    pi[initial_state] = 1.0
    t_n = np.linalg.matrix_power(matrix, n_steps)
    return pi @ t_n


# ---------------------------------------------------------------------------
# Discretisation helpers (map continuous signals → state levels)
# ---------------------------------------------------------------------------

def discretise_gdp(gdp_growth_pct: float | None) -> int:
    """Map GDP QoQ growth % to {0=contraction, 1=neutral, 2=expansion}."""
    if gdp_growth_pct is None:
        return 1  # neutral default
    if gdp_growth_pct < -0.5:
        return 0
    if gdp_growth_pct > 1.0:
        return 2
    return 1


def discretise_sentiment(avg_sentiment: float | None) -> int:
    """Map avg_sentiment [-1, +1] to {0=negative, 1=neutral, 2=positive}."""
    if avg_sentiment is None:
        return 1
    if avg_sentiment < -0.15:
        return 0
    if avg_sentiment > 0.15:
        return 2
    return 1


def discretise_quality(cis_quality_score: float | None) -> int:
    """Map CIS fundamental quality score [0, 100] to {0=weak, 1=average, 2=strong}."""
    if cis_quality_score is None:
        return 1
    if cis_quality_score < 35.0:
        return 0
    if cis_quality_score > 65.0:
        return 2
    return 1


def discretise_momentum(cis_momentum_score: float | None) -> int:
    """Map CIS fundamental momentum score [0, 100] to {0=declining, 1=stable, 2=improving}."""
    if cis_momentum_score is None:
        return 1
    if cis_momentum_score < 35.0:
        return 0
    if cis_momentum_score > 65.0:
        return 2
    return 1


def current_state_from_cis(
    gdp_growth_pct: float | None,
    avg_sentiment: float | None,
    cis_quality_score: float | None,
    cis_momentum_score: float | None,
) -> int:
    """Derive current Markov state index from live CIS/economic signals."""
    return encode_state(
        gdp=discretise_gdp(gdp_growth_pct),
        sentiment=discretise_sentiment(avg_sentiment),
        quality=discretise_quality(cis_quality_score),
        momentum=discretise_momentum(cis_momentum_score),
    )
