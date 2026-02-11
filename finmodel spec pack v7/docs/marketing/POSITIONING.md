# Positioning — FinModel (working title)
**Date:** 2026-02-07

## One-liner
From messy statements to decision-grade forecasts and valuation — **auditable, evidence-linked, and Excel-native** (with deterministic models compiled from an LLM-assisted draft workflow).

## Core problem
Teams lose days spreading statements, debating assumptions without provenance, rebuilding scenarios, and rewriting memos/board packs.

## Primary ICPs (launch order)
1. Boutique advisory / valuation / fractional CFO firms
2. Growth company CFO + FP&A teams
3. Credit teams / lenders / private debt
4. PE / buy-side analysts / equity research

## How it works
1. **Ingest**: Excel management accounts, AFS PDFs, or granular exports (sales/AR/AP/bank/inventory); supports YTD roll-forward; monthly or annual.
2. **Draft Mode**: analyst chat + parameter workspace proposes drivers/assumptions with evidence and confidence.
3. **Commit**: compile to a locked deterministic model configuration (no runtime LLM guesses).
4. **Run**: 3-statement forecast, working capital + funding options, Monte Carlo, valuation (DCF + multiples).
5. **Deliver**: memo packs + **Excel bidirectional live links** (push/pull).

## Differentiators
- **Draft→Commit compiler boundary** (LLM drafts; deterministic runtime)
- **Evidence-first assumptions** (provenance, conflict detection, confidence)
- **Unified workflow**: spreading → forecast → risk → valuation → memo pack
- **ERP long-tail coverage** via API discovery → publish connector library
- **Excel-native bidirectional links** with validation + role gating + changesets
- **Multi-LLM routing + token cost governance** (procurement-friendly)

## Outcomes
- 70–90% reduction in time from source docs → model → memo
- Repeatable, auditable forecasts and valuation
- Faster funding sizing decisions from integrated WC + downside + MC

## Objections & responses
- “AI hallucinates” → Draft only; commit compiles to deterministic config + review loop + evidence.
- “Our data is messy/incomplete” → data-gap detection + guided collection + tiered fidelity inputs.
- “We live in Excel” → bidirectional add-in; results refresh without losing governance.
