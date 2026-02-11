# Frontend Stack Specification
**Date:** 2026-02-08

## Framework: Next.js 14+ (App Router)
- TypeScript (strict mode)
- App Router with server components (default) and client components (interactive)
- Tailwind CSS for styling
- shadcn/ui component library (built on Radix primitives)
- Deployed on Vercel (or self-hosted with `next start`)

## State Management
- **Server state:** TanStack Query (React Query) v5 for API data fetching, caching, invalidation
- **Client state:** Zustand for UI state (sidebar open, active tab, draft workspace local edits)
- **Form state:** React Hook Form + Zod validation
- No Redux — the app is mostly server-state-driven

## Auth Flow
- Supabase Auth client library (`@supabase/supabase-js`)
- Auth context provider wraps the app
- Login page: email/password form, magic link option
- Protected routes: middleware checks session, redirects to /login if expired
- JWT passed to API via `Authorization: Bearer {access_token}` header
- Token refresh handled automatically by Supabase client

## Routing Structure
```
/                           → Redirect to /dashboard
/login                      → Auth page
/dashboard                  → Overview (recent runs, active baseline summary)
/baselines                  → Baseline list
/baselines/[id]             → Baseline detail (assumptions, history)
/drafts                     → Draft session list
/drafts/[id]                → Draft workspace (chat + assumptions editor)
/runs                       → Run list
/runs/[id]                  → Run results (statements, KPIs, charts)
/runs/[id]/mc               → Monte Carlo results (fan charts, distributions)
/runs/[id]/valuation        → Valuation outputs
/scenarios                  → Scenario management
/ventures                   → Venture list
/ventures/new               → New venture wizard (template selection + questions)
/integrations               → ERP connections + sync status
/excel                      → Excel connection management
/memos                      → Memo list
/memos/[id]                 → Memo viewer
/settings                   → Tenant settings
/settings/billing           → Billing + usage
/settings/users             → User management
/settings/llm               → LLM routing policy config
```

## Key Components

### Draft Workspace (`/drafts/[id]`)
The primary work surface. Split layout:
- **Left panel (60%):** Assumption editor
  - Tree view of model_config structure
  - Inline editing of values
  - Evidence indicators (green dot = high confidence, amber = medium, red = low, grey = none)
  - Pending proposal badges (click to review)
  - Integrity check status bar at top
- **Right panel (40%):** Chat
  - Message history (user + assistant)
  - Input box with send button
  - Proposal cards: accept/reject buttons, evidence display
  - Collapsible for more editor space
- **Bottom bar:** Status (draft/ready/committed), Mark Ready button, Commit button

### Run Results (`/runs/[id]`)
Tabbed layout:
- **Statements tab:** IS/BS/CF tables (months as columns, rows as line items)
  - Conditional formatting: negative values in red
  - Expandable sections (e.g., expand Revenue to see streams)
- **KPIs tab:** Dashboard cards + sparkline charts
- **Charts tab:** Revenue/EBITDA/FCF line charts over time

### Monte Carlo Results (`/runs/[id]/mc`)
- Fan chart: P10/P25/P50/P75/P90 bands over time
- Tornado chart: horizontal bars showing sensitivity per driver
- Histogram: distribution of terminal FCF or enterprise value
- Percentile table: P5 through P95 for key metrics

### Venture Wizard (`/ventures/new`)
Multi-step form:
1. Select template (cards with icons for each business model)
2. Answer question_plan questions (grouped by section)
3. Review LLM-generated initial assumptions
4. Edit/accept assumptions
5. Commit → creates baseline → redirect to run

## API Client
Centralized API client with:
- Base URL from environment variable
- Automatic JWT header injection
- Response envelope unwrapping (`response.data.data`)
- Error handling with toast notifications
- Request/response TypeScript types generated from OpenAPI spec (or manually maintained)

```typescript
// apps/web/lib/api.ts
const api = {
  baselines: {
    list: () => get<Baseline[]>('/api/v1/baselines'),
    get: (id: string) => get<Baseline>(`/api/v1/baselines/${id}`),
    create: (data: CreateBaselineInput) => post<Baseline>('/api/v1/baselines', data),
  },
  runs: {
    create: (data: CreateRunInput) => post<Run>('/api/v1/runs', data),
    get: (id: string) => get<Run>(`/api/v1/runs/${id}`),
    statements: (id: string) => get<Statements>(`/api/v1/runs/${id}/statements`),
  },
  drafts: {
    create: (data: CreateDraftInput) => post<DraftSession>('/api/v1/drafts', data),
    chat: (id: string, message: string) => post<ChatResponse>(`/api/v1/drafts/${id}/chat`, { message }),
    commit: (id: string) => post<CommitResult>(`/api/v1/drafts/${id}/commit`),
  },
  // ... etc
};
```

## Charting Library
- **Recharts** for standard charts (line, bar, area)
- **D3** for custom visualizations (tornado, fan charts) if Recharts is insufficient
- Charts are client components (`"use client"`)

## Real-time Updates
- Supabase Realtime subscription for:
  - Run status changes (queued → running → succeeded)
  - Excel sync events (pull/push notifications)
  - Draft session collaboration (future: multi-user editing)
- Implementation: `useEffect` with Supabase channel subscription, invalidate React Query cache on event

## Responsive Design
- Desktop-first (primary users are analysts on large screens)
- Minimum supported width: 1024px
- Tables scroll horizontally on smaller screens
- Sidebar collapses to hamburger menu on tablet
- Mobile: read-only views of runs and memos (no draft editing)

## Environment Variables
```
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
NEXT_PUBLIC_API_URL=http://localhost:8000
```
