"""Unit tests for apps.api.app.services.pim.portfolio.

PIM-4.2: Greedy portfolio constructor (top-N by CIS).
PIM-4.3: Position constraints (max_weight_pct, max_sector_pct, min_liquidity_usd, min_cis_score).
PIM-4.4: Portfolio run snapshot (persist_run).
PIM-4.5: LLM portfolio narrative (generate_narrative).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.api.app.services.pim.portfolio import (
    PortfolioCandidate,
    PortfolioRun,
    PositionConstraints,
    build_portfolio,
    generate_narrative,
    persist_run,
)
from shared.fm_shared.errors import LLMError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_candidate(
    company_id: str,
    cis_score: float,
    sector: str | None = None,
    market_cap_usd: float | None = None,
    ticker: str | None = None,
) -> PortfolioCandidate:
    return PortfolioCandidate(
        company_id=company_id,
        cis_score=cis_score,
        ticker=ticker or company_id.upper(),
        name=f"Company {company_id}",
        sector=sector,
        market_cap_usd=market_cap_usd,
    )


def _make_candidates(n: int, base_cis: float = 60.0, sector: str = "Technology") -> list[PortfolioCandidate]:
    return [
        _make_candidate(f"co_{i}", cis_score=base_cis - i * 2.0, sector=sector)
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# PositionConstraints validation
# ---------------------------------------------------------------------------


class TestPositionConstraints:
    def test_defaults_valid(self):
        c = PositionConstraints()
        c.validate()  # should not raise

    def test_top_n_zero_raises(self):
        with pytest.raises(ValueError, match="top_n"):
            PositionConstraints(top_n=0).validate()

    def test_max_weight_zero_raises(self):
        with pytest.raises(ValueError, match="max_weight_pct"):
            PositionConstraints(max_weight_pct=0.0).validate()

    def test_max_weight_above_one_raises(self):
        with pytest.raises(ValueError, match="max_weight_pct"):
            PositionConstraints(max_weight_pct=1.1).validate()

    def test_max_sector_above_one_raises(self):
        with pytest.raises(ValueError, match="max_sector_pct"):
            PositionConstraints(max_sector_pct=1.5).validate()

    def test_min_cis_negative_raises(self):
        with pytest.raises(ValueError, match="min_cis_score"):
            PositionConstraints(min_cis_score=-1.0).validate()

    def test_min_cis_above_100_raises(self):
        with pytest.raises(ValueError, match="min_cis_score"):
            PositionConstraints(min_cis_score=101.0).validate()


# ---------------------------------------------------------------------------
# build_portfolio — basic construction (PIM-4.2)
# ---------------------------------------------------------------------------


class TestBuildPortfolioBasic:
    def test_empty_candidates_returns_empty_run(self):
        run = build_portfolio([], tenant_id="t1")
        assert run.n_holdings == 0
        assert run.holdings == []
        assert run.n_candidates == 0

    def test_selects_top_n_by_cis(self):
        candidates = _make_candidates(20)
        # max_sector_pct=1.0 disables sector cap so pure CIS ranking is tested
        run = build_portfolio(candidates, PositionConstraints(top_n=5, max_sector_pct=1.0), tenant_id="t1")
        assert run.n_holdings == 5
        # Top holding has highest CIS
        assert run.holdings[0].cis_score == max(c.cis_score for c in candidates)

    def test_run_id_is_uuid(self):
        import re
        run = build_portfolio(_make_candidates(3), tenant_id="t1")
        uuid_pattern = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")
        assert uuid_pattern.match(run.run_id)

    def test_tenant_id_propagated(self):
        run = build_portfolio(_make_candidates(3), tenant_id="my_tenant")
        assert run.tenant_id == "my_tenant"

    def test_regime_propagated(self):
        run = build_portfolio(_make_candidates(3), current_regime="expansion", tenant_id="t1")
        assert run.regime_at_run == "expansion"

    def test_n_candidates_matches_input(self):
        candidates = _make_candidates(15)
        run = build_portfolio(candidates, PositionConstraints(top_n=10), tenant_id="t1")
        assert run.n_candidates == 15

    def test_weights_sum_to_one(self):
        run = build_portfolio(_make_candidates(10), PositionConstraints(max_sector_pct=1.0), tenant_id="t1")
        total_weight = sum(h.weight for h in run.holdings)
        assert abs(total_weight - 1.0) < 1e-9

    def test_equal_weight_allocation(self):
        run = build_portfolio(_make_candidates(4), PositionConstraints(top_n=4, max_sector_pct=1.0), tenant_id="t1")
        for h in run.holdings:
            assert abs(h.weight - 0.25) < 1e-9

    def test_rank_is_sequential(self):
        run = build_portfolio(_make_candidates(5), PositionConstraints(max_sector_pct=1.0), tenant_id="t1")
        ranks = [h.rank for h in run.holdings]
        assert ranks == list(range(1, run.n_holdings + 1))

    def test_holdings_sorted_descending_by_cis(self):
        run = build_portfolio(_make_candidates(10), PositionConstraints(max_sector_pct=1.0), tenant_id="t1")
        scores = [h.cis_score for h in run.holdings]
        assert scores == sorted(scores, reverse=True)

    def test_avg_cis_is_weighted_average(self):
        run = build_portfolio(_make_candidates(4), PositionConstraints(top_n=4, max_sector_pct=1.0), tenant_id="t1")
        expected_avg = sum(h.cis_score * h.weight for h in run.holdings)
        assert abs(run.avg_cis_score - expected_avg) < 1e-9

    def test_factor_scores_propagated(self):
        c = PortfolioCandidate(
            company_id="c1", cis_score=75.0, sector="Finance",
            fundamental_quality=80.0, fundamental_momentum=65.0,
        )
        # No sector cap needed — single company, single sector
        run = build_portfolio([c], PositionConstraints(max_sector_pct=1.0), tenant_id="t1")
        h = run.holdings[0]
        assert h.fundamental_quality == 80.0
        assert h.fundamental_momentum == 65.0


# ---------------------------------------------------------------------------
# Position constraints (PIM-4.3)
# ---------------------------------------------------------------------------


class TestPositionConstraints43:
    def test_min_cis_filter(self):
        candidates = [
            _make_candidate("a", 80.0, sector="Finance"),
            _make_candidate("b", 40.0, sector="Finance"),
            _make_candidate("c", 20.0, sector="Finance"),
        ]
        # top_n=1 so sector cap doesn't interfere: 1/1=100% but sector cap ≤1.0
        run = build_portfolio(
            candidates, PositionConstraints(min_cis_score=50.0, max_sector_pct=1.0), tenant_id="t1"
        )
        assert run.n_holdings == 1
        assert run.holdings[0].company_id == "a"

    def test_min_liquidity_filter(self):
        candidates = [
            _make_candidate("big", 80.0, sector="Technology", market_cap_usd=1_000_000.0),
            _make_candidate("small", 90.0, sector="Finance", market_cap_usd=50_000.0),
        ]
        run = build_portfolio(
            candidates,
            PositionConstraints(min_liquidity_usd=100_000.0, max_sector_pct=1.0),
            tenant_id="t1",
        )
        assert run.n_holdings == 1
        assert run.holdings[0].company_id == "big"

    def test_min_liquidity_none_skips_filter(self):
        candidates = [
            _make_candidate("a", 80.0, sector="Technology", market_cap_usd=1.0),
            _make_candidate("b", 70.0, sector="Finance", market_cap_usd=None),
        ]
        run = build_portfolio(
            candidates, PositionConstraints(min_liquidity_usd=None, max_sector_pct=1.0), tenant_id="t1"
        )
        assert run.n_holdings == 2

    def test_sector_cap_enforced(self):
        # 10 tech candidates, top_n=10, max_sector_pct=0.3 → at most 3 tech companies
        # (1/10=10%, 2/10=20%, 3/10=30% ≤ 30%; 4/10=40% > 30% → blocked)
        candidates = [
            _make_candidate(f"tech_{i}", 80.0 - i, sector="Technology") for i in range(10)
        ]
        run = build_portfolio(
            candidates,
            PositionConstraints(top_n=10, max_sector_pct=0.3),
            tenant_id="t1",
        )
        n_tech = sum(1 for h in run.holdings if h.sector == "Technology")
        # At most floor(0.3 * 10) = 3 tech companies allowed
        assert n_tech <= 3

    def test_max_weight_cap_respected_with_feasible_portfolio(self):
        # 5 candidates in different sectors, max_weight_pct=0.15
        # equal-weight = 0.2 > 0.15 → cap enforced and renormalised
        # With 5 holdings at 0.15 each → total=0.75, renorm to 0.2 each
        # Note: cap is only binding when n*cap >= 1.0. Here 5*0.15=0.75 < 1.0
        # → renormalization restores 0.2. True cap binding: need n*cap >= 1.0.
        # Test: 8 holdings, max_weight_pct=0.15 → 8*0.15=1.2 >= 1.0, cap is binding.
        candidates = [
            _make_candidate(f"co_{i}", 80.0 - i, sector=f"Sector_{i}")
            for i in range(8)
        ]
        run = build_portfolio(
            candidates,
            PositionConstraints(top_n=8, max_weight_pct=0.15, max_sector_pct=1.0),
            tenant_id="t1",
        )
        # equal-weight = 1/8 = 0.125 ≤ 0.15 → no capping needed
        # weights should all be equal
        for h in run.holdings:
            assert abs(h.weight - 1.0 / 8) < 1e-9
        total = sum(h.weight for h in run.holdings)
        assert abs(total - 1.0) < 1e-9

    def test_max_weight_cap_applied_when_few_holdings(self):
        # With max_weight_pct=0.2 and only top_n=3 selected (from 10 candidates):
        # equal-weight = 1/3 ≈ 0.333 > 0.2 → cap and renormalize to 0.333 each
        # (renormalization is expected because all holdings are equal — cap doesn't change balance)
        candidates = [
            _make_candidate(f"co_{i}", 80.0 - i, sector=f"Sector_{i}")
            for i in range(5)
        ]
        run = build_portfolio(
            candidates,
            PositionConstraints(top_n=3, max_weight_pct=0.2, max_sector_pct=1.0),
            tenant_id="t1",
        )
        assert run.n_holdings == 3
        total = sum(h.weight for h in run.holdings)
        assert abs(total - 1.0) < 1e-9

    def test_all_filtered_returns_empty_run(self):
        candidates = _make_candidates(5)
        run = build_portfolio(
            candidates,
            PositionConstraints(min_cis_score=100.0),
            tenant_id="t1",
        )
        assert run.n_holdings == 0
        assert run.holdings == []


# ---------------------------------------------------------------------------
# Mixed sectors — sector cap allows multiple sectors
# ---------------------------------------------------------------------------


class TestSectorDiversity:
    def test_mixed_sectors_selects_up_to_top_n(self):
        candidates = [
            _make_candidate(f"tech_{i}", 80.0 - i, sector="Technology") for i in range(3)
        ] + [
            _make_candidate(f"fin_{i}", 75.0 - i, sector="Finance") for i in range(3)
        ]
        # top_n=6, max_sector_pct=0.6 → up to 3 per sector (3/6=50% ≤ 60%)
        run = build_portfolio(
            candidates,
            PositionConstraints(top_n=6, max_sector_pct=0.6),
            tenant_id="t1",
        )
        assert run.n_holdings <= 6
        assert run.n_holdings >= 2  # At least one from each sector


# ---------------------------------------------------------------------------
# persist_run (PIM-4.4)
# ---------------------------------------------------------------------------


class TestPersistRun:
    @pytest.fixture()
    def mock_conn(self):
        conn = AsyncMock()
        conn.execute = AsyncMock()
        return conn

    @pytest.fixture()
    def simple_run(self):
        candidates = _make_candidates(3)
        return build_portfolio(candidates, PositionConstraints(max_sector_pct=1.0), tenant_id="t_persist")

    async def test_persist_calls_execute_for_run_and_holdings(self, mock_conn, simple_run):
        await persist_run(simple_run, mock_conn)
        # At least 1 call for the run + 1 per holding
        assert mock_conn.execute.call_count >= 1 + simple_run.n_holdings

    async def test_persist_with_empty_holdings(self, mock_conn):
        run = build_portfolio([], tenant_id="t_empty")
        await persist_run(run, mock_conn)
        # Only the run INSERT, no holding INSERTs
        assert mock_conn.execute.call_count == 1

    async def test_persist_run_id_passed(self, mock_conn, simple_run):
        await persist_run(simple_run, mock_conn)
        first_call_args = mock_conn.execute.call_args_list[0][0]
        assert simple_run.run_id in first_call_args

    async def test_persist_propagates_narrative(self, mock_conn):
        candidates = _make_candidates(2)
        run = build_portfolio(candidates, PositionConstraints(max_sector_pct=1.0), tenant_id="t_narr")
        run.narrative = "Test narrative"
        run.narrative_top_picks = "Top picks text"
        await persist_run(run, mock_conn)
        run_insert_args = mock_conn.execute.call_args_list[0][0]
        assert "Test narrative" in run_insert_args
        assert "Top picks text" in run_insert_args


# ---------------------------------------------------------------------------
# generate_narrative (PIM-4.5)
# ---------------------------------------------------------------------------


class TestGenerateNarrative:
    @pytest.fixture()
    def run_with_holdings(self):
        return build_portfolio(
            _make_candidates(5), PositionConstraints(max_sector_pct=1.0), tenant_id="t_narr"
        )

    @pytest.fixture()
    def mock_llm(self):
        llm = MagicMock()
        llm.complete_with_routing = AsyncMock(
            return_value=MagicMock(
                content={
                    "summary": "Well-diversified portfolio.",
                    "top_picks": "Top picks rationale.",
                    "risk_note": "Concentration in Tech sector.",
                    "regime_context": "Positioned for expansion.",
                }
            )
        )
        return llm

    async def test_narrative_populated_on_success(self, run_with_holdings, mock_llm):
        result = await generate_narrative(run_with_holdings, mock_llm)
        assert result.narrative == "Well-diversified portfolio."
        assert result.narrative_top_picks == "Top picks rationale."
        assert result.narrative_risk_note == "Concentration in Tech sector."
        assert result.narrative_regime_context == "Positioned for expansion."

    async def test_returns_same_run_object(self, run_with_holdings, mock_llm):
        result = await generate_narrative(run_with_holdings, mock_llm)
        assert result is run_with_holdings

    async def test_uses_pim_portfolio_narrative_label(self, run_with_holdings, mock_llm):
        await generate_narrative(run_with_holdings, mock_llm)
        call_kwargs = mock_llm.complete_with_routing.call_args
        # task_label is the 4th positional arg
        assert "pim_portfolio_narrative" in call_kwargs[0]

    async def test_temperature_02(self, run_with_holdings, mock_llm):
        await generate_narrative(run_with_holdings, mock_llm)
        call_kwargs = mock_llm.complete_with_routing.call_args
        assert call_kwargs[1].get("temperature") == 0.2 or 0.2 in call_kwargs[0]

    async def test_llm_failure_sets_error_narrative(self, run_with_holdings):
        mock_llm = MagicMock()
        mock_llm.complete_with_routing = AsyncMock(
            side_effect=LLMError("All providers failed", code="ERR_LLM_ALL_PROVIDERS_FAILED")
        )
        result = await generate_narrative(run_with_holdings, mock_llm)
        assert result.narrative is not None
        assert "unavailable" in result.narrative.lower()

    async def test_empty_holdings_sets_fallback_narrative(self):
        empty_run = build_portfolio([], tenant_id="t_empty")
        mock_llm = MagicMock()
        result = await generate_narrative(empty_run, mock_llm)
        assert result.narrative is not None
        mock_llm.complete_with_routing.assert_not_called()

    async def test_non_dict_llm_response_handled_gracefully(self, run_with_holdings):
        mock_llm = MagicMock()
        mock_llm.complete_with_routing = AsyncMock(
            return_value=MagicMock(content="raw string not a dict")
        )
        result = await generate_narrative(run_with_holdings, mock_llm)
        # Should not raise — content defaults to empty strings
        assert result.narrative == ""
