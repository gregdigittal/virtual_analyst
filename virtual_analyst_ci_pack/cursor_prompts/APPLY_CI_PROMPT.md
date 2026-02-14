# Cursor Prompt — Apply Virtual Analyst CI (Option B)

Update the app to match the Virtual Analyst CI pack.

1) Tokens
- Merge `tokens/tailwind.theme.snippet.ts` into tailwind.config and ensure classes like `bg-va-midnight` work.
- Set global defaults: background = va.midnight, text = va.text.

2) Fonts
- Add Inter + Sora + JetBrains Mono (Google Fonts or self-host via `next/font/google`).
- Configure Tailwind fontFamily keys: brand/sans/mono (using CSS variables from layout).

3) Logos
- Use `logos/svg/virtual-analyst-icon.svg` for app icon (favicon via `app/icon.svg`), sidebar/nav icon (e.g. `public/va-icon.svg`).
- Use `logos/svg/virtual-analyst-wordmark.svg` on landing/login; for report exports use the same asset in the export template when generating PDF/HTML.

4) Components
- Implement: Button, Card, Input, Badge, Tabs using the tokens (see `components/ui/`: VAButton, VACard, VAInput, VABadge, VATabs).
- Add: EvidenceChip (source + confidence), StatePill (Draft/Selected/Committed), RiskBadge (low/medium/high).

5) Screens
- Apply styling to Draft Mode, Modeling Dashboard, Monte Carlo panel, and evidence areas (assumption tree, pending proposals) using va.* tokens and the UI components.

6) QA
- Ensure contrast AA on midnight background (va.text on va.midnight meets AA).
- Focus rings: use `focus-visible:ring-2 focus-visible:ring-va-blue` (no heavy glow); global fallback in `globals.css` with `*:focus-visible { box-shadow: 0 0 0 2px var(--va-blue); }`.
