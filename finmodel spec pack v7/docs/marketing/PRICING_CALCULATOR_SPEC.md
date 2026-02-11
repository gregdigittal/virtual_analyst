# Pricing Calculator Spec (Internal) — Inputs, Outputs, Sheets
**Date:** 2026-02-07

This spec aligns to artifacts:
- llm_call_log_v1 → usage_meter_v1 → billing_subscription_v1

## Sheet 1: Customer Inputs
- Segment (Advisory / CFO / Lender / PE / Public markets)
- Seats (owners/admin/analyst/investor)
- Entities, ventures, countries
- Forecast resolution (monthly/annual)
- Data sources per month:
  - PDFs: docs/month, pages/month
  - Excel uploads: files/month
  - ERP connectors: count + sync frequency
  - Granular feeds: yes/no (sales, AR/AP, bank, inventory)
- Usage per month:
  - Runs/month
  - Scenarios/run
  - Monte Carlo runs/month + sims/run
  - Memo packs/month
  - Deep research sessions/month
  - Excel refreshes/day, pushes/day
- LLM policy (balanced/low-cost/high-quality) + BYO-key yes/no

## Sheet 2: Plan Selection
- Starter / Pro / Enterprise
- Included seats, included tokens, included runs, included pages
- Add-ons toggles: Excel live links, memo packs, extra connectors, dedicated env, SSO

## Sheet 3: Revenue Model
- Base subscription
- Seat overages
- Connector packs
- Usage bundles: tokens/pages/MC/storage
- Discounts: annual prepay, pilot credit

## Sheet 4: Cost Model (COGS)
- LLM cost by task category (from routing policy assumptions)
- OCR / extraction cost per page (if applicable)
- Compute cost per MC run or per 1k sims
- Storage cost per GB-month
- Support/onboarding allocation (optional)

## Sheet 5: Margin & Recommendation
- Gross margin
- Contribution margin (optional)
- Suggested tier + rationale
- Risk flags: overage exposure, heavy OCR usage, extreme MC compute

## Sheet 6: Scenario Sensitivity
- Low/Expected/High usage scenarios
- Break-even and overage triggers
