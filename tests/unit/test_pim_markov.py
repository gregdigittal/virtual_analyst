"""Unit tests for PIM Markov chain engine — PIM-3.1 through PIM-3.5."""

from __future__ import annotations

import numpy as np
import pytest

from apps.api.app.services.pim.markov import (
    N_STATES,
    compute_steady_state,
    current_state_from_cis,
    decode_state,
    discretise_gdp,
    discretise_momentum,
    discretise_quality,
    discretise_sentiment,
    encode_state,
    estimate_transition_matrix,
    n_step_distribution,
    simulate_trajectory,
    state_label,
)

# ---------------------------------------------------------------------------
# PIM-3.1 — State encoding / decoding
# ---------------------------------------------------------------------------


class TestStateEncoding:
    def test_state_space_size(self):
        assert N_STATES == 81

    def test_encode_all_corners(self):
        assert encode_state(0, 0, 0, 0) == 0
        assert encode_state(2, 2, 2, 2) == 80
        assert encode_state(1, 1, 1, 1) == 40

    def test_encode_decode_roundtrip(self):
        for idx in range(N_STATES):
            decoded = decode_state(idx)
            assert encode_state(*decoded) == idx

    def test_decode_known_state(self):
        # state 0 = (0,0,0,0)
        assert decode_state(0) == (0, 0, 0, 0)
        # state 80 = (2,2,2,2)
        assert decode_state(80) == (2, 2, 2, 2)
        # state 27 = gdp=1, rest=0
        assert decode_state(27) == (1, 0, 0, 0)

    def test_encode_invalid_dimension_raises(self):
        with pytest.raises(ValueError, match="gdp"):
            encode_state(3, 0, 0, 0)
        with pytest.raises(ValueError, match="sentiment"):
            encode_state(0, -1, 0, 0)

    def test_decode_out_of_range_raises(self):
        with pytest.raises(ValueError):
            decode_state(-1)
        with pytest.raises(ValueError):
            decode_state(81)

    def test_all_81_states_unique(self):
        indices = {encode_state(g, s, q, m) for g in range(3) for s in range(3) for q in range(3) for m in range(3)}
        assert len(indices) == 81

    def test_state_label_format(self):
        label = state_label(0)
        assert label == "contraction/negative/weak/declining"
        label80 = state_label(80)
        assert label80 == "expansion/positive/strong/improving"


# ---------------------------------------------------------------------------
# PIM-3.2 — Transition matrix estimation
# ---------------------------------------------------------------------------


class TestTransitionMatrixEstimation:
    def test_uniform_matrix_when_no_observations(self):
        result = estimate_transition_matrix([], alpha=1.0)
        assert result.matrix.shape == (81, 81)
        assert result.n_observations == 0
        # Each row should sum to 1.0 (Laplace uniform)
        assert np.allclose(result.matrix.sum(axis=1), 1.0, atol=1e-9)
        # All cells equal (uniform)
        assert np.allclose(result.matrix, 1.0 / 81, atol=1e-9)

    def test_single_observation_no_transitions(self):
        result = estimate_transition_matrix([(0, 0, 0, 0)], alpha=1.0)
        assert result.n_observations == 0

    def test_row_sums_one(self):
        obs = [(g, s, q, m) for g in range(3) for s in range(3) for q in range(3) for m in range(3)]
        # Repeat twice to create transitions
        obs = obs + obs
        result = estimate_transition_matrix(obs)
        assert np.allclose(result.matrix.sum(axis=1), 1.0, atol=1e-9)

    def test_counts_match_observations(self):
        # Simple 2-state sequence: always (0,0,0,0) → (1,1,1,1) → (0,0,0,0) → ...
        obs = [(0, 0, 0, 0), (1, 1, 1, 1)] * 10
        result = estimate_transition_matrix(obs, alpha=0.0)
        # With alpha=0, raw counts drive probabilities
        idx0 = encode_state(0, 0, 0, 0)
        idx1 = encode_state(1, 1, 1, 1)
        # From state 0: should always go to state 1
        assert result.matrix[idx0, idx1] > 0.99
        # From state 1: should always go to state 0
        assert result.matrix[idx1, idx0] > 0.99

    def test_laplace_smoothing_no_zero_probs(self):
        # Even with sparse data, no probability should be exactly 0 (SR-4)
        obs = [(0, 0, 0, 0), (1, 0, 0, 0)]
        result = estimate_transition_matrix(obs, alpha=1.0)
        assert (result.matrix > 0).all()

    def test_alpha_default_is_one(self):
        result = estimate_transition_matrix([(0, 0, 0, 0), (0, 0, 0, 1)])
        assert result.alpha == 1.0

    def test_n_observations_correct(self):
        obs = [(0, 0, 0, 0)] * 5 + [(1, 0, 0, 0)] * 5
        result = estimate_transition_matrix(obs)
        # 10 elements → 9 transitions
        assert result.n_observations == 9


# ---------------------------------------------------------------------------
# PIM-3.3 — Steady-state computation
# ---------------------------------------------------------------------------


class TestSteadyState:
    @pytest.fixture
    def uniform_matrix(self):
        m = np.ones((N_STATES, N_STATES), dtype=np.float64) / N_STATES
        return m

    @pytest.fixture
    def identity_matrix(self):
        # Identity matrix: absorbing chain (not ergodic)
        return np.eye(N_STATES, dtype=np.float64)

    def test_uniform_matrix_steady_state(self, uniform_matrix):
        result = compute_steady_state(uniform_matrix)
        # Stationary distribution of uniform matrix = uniform
        assert np.allclose(result.stationary_distribution, 1.0 / N_STATES, atol=1e-6)

    def test_stationary_distribution_sums_to_one(self, uniform_matrix):
        result = compute_steady_state(uniform_matrix)
        assert abs(result.stationary_distribution.sum() - 1.0) < 1e-9

    def test_top_states_count(self, uniform_matrix):
        result = compute_steady_state(uniform_matrix)
        assert len(result.top_states) == 10

    def test_top_states_have_required_keys(self, uniform_matrix):
        result = compute_steady_state(uniform_matrix)
        for entry in result.top_states:
            assert "state_index" in entry
            assert "label" in entry
            assert "probability" in entry

    def test_invalid_shape_raises(self):
        bad = np.ones((10, 10)) / 10
        with pytest.raises(ValueError, match="Expected"):
            compute_steady_state(bad)

    def test_invalid_row_sums_raises(self):
        bad = np.ones((N_STATES, N_STATES), dtype=np.float64)  # rows sum to 81
        with pytest.raises(ValueError, match="rows must sum"):
            compute_steady_state(bad)


# ---------------------------------------------------------------------------
# PIM-3.5 — JIT functions (tested via Python fallback)
# ---------------------------------------------------------------------------


class TestJITFunctions:
    def test_count_transitions_basic(self):
        from apps.api.app.services.pim.markov import _count_transitions_jit

        from_s = np.array([0, 1, 2], dtype=np.int64)
        to_s = np.array([1, 2, 0], dtype=np.int64)
        counts = np.zeros((N_STATES, N_STATES), dtype=np.int64)
        _count_transitions_jit(from_s, to_s, N_STATES, counts)
        assert counts[0, 1] == 1
        assert counts[1, 2] == 1
        assert counts[2, 0] == 1
        assert counts.sum() == 3

    def test_row_normalise_produces_valid_probabilities(self):
        from apps.api.app.services.pim.markov import _row_normalise_jit

        counts = np.ones((N_STATES, N_STATES), dtype=np.float64)
        result = np.zeros((N_STATES, N_STATES), dtype=np.float64)
        _row_normalise_jit(counts, 0.0, result)
        assert np.allclose(result.sum(axis=1), 1.0, atol=1e-9)


# ---------------------------------------------------------------------------
# Forward simulation
# ---------------------------------------------------------------------------


class TestSimulation:
    def test_trajectory_length(self):
        matrix = np.ones((N_STATES, N_STATES), dtype=np.float64) / N_STATES
        traj = simulate_trajectory(matrix, initial_state=0, n_steps=10)
        assert len(traj) == 11  # n_steps + 1
        assert traj[0] == 0

    def test_trajectory_all_valid_states(self):
        matrix = np.ones((N_STATES, N_STATES), dtype=np.float64) / N_STATES
        traj = simulate_trajectory(matrix, initial_state=0, n_steps=50)
        assert all(0 <= s < N_STATES for s in traj)

    def test_invalid_initial_state_raises(self):
        matrix = np.ones((N_STATES, N_STATES), dtype=np.float64) / N_STATES
        with pytest.raises(ValueError):
            simulate_trajectory(matrix, initial_state=81, n_steps=5)

    def test_n_step_distribution_sums_to_one(self):
        matrix = np.ones((N_STATES, N_STATES), dtype=np.float64) / N_STATES
        dist = n_step_distribution(matrix, initial_state=0, n_steps=3)
        assert abs(dist.sum() - 1.0) < 1e-9

    def test_zero_step_distribution_is_delta(self):
        matrix = np.ones((N_STATES, N_STATES), dtype=np.float64) / N_STATES
        dist = n_step_distribution(matrix, initial_state=5, n_steps=0)
        assert dist[5] == pytest.approx(1.0)
        assert dist.sum() == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Discretisation helpers
# ---------------------------------------------------------------------------


class TestDiscretisation:
    def test_gdp_contraction(self):
        assert discretise_gdp(-1.0) == 0
        assert discretise_gdp(-0.6) == 0

    def test_gdp_neutral(self):
        assert discretise_gdp(0.0) == 1
        assert discretise_gdp(0.5) == 1
        assert discretise_gdp(None) == 1

    def test_gdp_expansion(self):
        assert discretise_gdp(2.0) == 2

    def test_sentiment_levels(self):
        assert discretise_sentiment(-0.5) == 0
        assert discretise_sentiment(0.0) == 1
        assert discretise_sentiment(None) == 1
        assert discretise_sentiment(0.5) == 2

    def test_quality_levels(self):
        assert discretise_quality(20.0) == 0
        assert discretise_quality(50.0) == 1
        assert discretise_quality(None) == 1
        assert discretise_quality(80.0) == 2

    def test_momentum_levels(self):
        assert discretise_momentum(10.0) == 0
        assert discretise_momentum(50.0) == 1
        assert discretise_momentum(None) == 1
        assert discretise_momentum(90.0) == 2

    def test_current_state_from_cis_all_none(self):
        state = current_state_from_cis(None, None, None, None)
        # All None → all neutral → state (1,1,1,1) = 40
        assert state == encode_state(1, 1, 1, 1)
        assert state == 40

    def test_current_state_from_cis_expansion_scenario(self):
        state = current_state_from_cis(
            gdp_growth_pct=2.0,
            avg_sentiment=0.5,
            cis_quality_score=80.0,
            cis_momentum_score=80.0,
        )
        assert state == encode_state(2, 2, 2, 2)  # = 80
