# Round 4 — Code Review Fixes

Apply every fix below **exactly**. Do NOT skip, reorder, or refactor anything beyond what is specified.

---

## FIX 1 (MEDIUM): `emailRedirectTo` should route through `/auth/callback`

**File:** `apps/web/app/signup/page.tsx`
**Line:** 61

The email confirmation link uses PKCE and appends a `code` param. Currently it points to `/login` which doesn't exchange the code. Route through `/auth/callback` so the user is auto-logged-in after confirming their email.

**Replace:**
```ts
options: { emailRedirectTo: `${window.location.origin}/login${next ? `?next=${encodeURIComponent(next)}` : ""}` },
```

**With:**
```ts
options: { emailRedirectTo: `${window.location.origin}/auth/callback${next ? `?next=${encodeURIComponent(next)}` : ""}` },
```

---

## FIX 2 (MEDIUM): Login page should display OAuth callback error

**File:** `apps/web/app/login/page.tsx`

The auth callback redirects to `/login?error=auth_callback_failed` on failure, but the login page ignores it.

**Step A — read the error param.** After line 13 (`const next = ...`), add:

```ts
const callbackError = searchParams.get("error");
```

**Step B — initialize error state from the param.** Change line 16 from:

```ts
const [error, setError] = useState<string | null>(null);
```

to:

```ts
const [error, setError] = useState<string | null>(
  callbackError === "auth_callback_failed"
    ? "Sign-in failed. Please try again."
    : null,
);
```

---

## FIX 3 (MEDIUM): Replace non-existent Supabase Docker image

**File:** `docker-compose.yml`

`supabase/supabase-dev:latest` does not exist on Docker Hub. Replace the entire `supabase` service with a comment directing developers to use the Supabase CLI instead.

**Replace the entire `supabase:` service block (lines 32–45):**

```yaml
  supabase:
    image: supabase/supabase-dev:latest
    environment:
      POSTGRES_PASSWORD: postgres
    ports:
      - "54321:8000"
    volumes:
      - supabase_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "exit 0"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 20s
```

**With:**

```yaml
  # Supabase: use the Supabase CLI for local dev (npx supabase start).
  # See https://supabase.com/docs/guides/local-development
  # The CLI starts its own containers for Auth, Storage, Studio, etc.
```

**Also remove `supabase_data:` from the `volumes:` block at the bottom** (keep `postgres_data:` and `redis_data:`).

---

## FIX 4 (LOW): Log OAuth exchange errors in auth callback

**File:** `apps/web/app/auth/callback/route.ts`

When `exchangeCodeForSession` fails, the error is silently discarded. Log it for debugging.

**Replace lines 35–38:**

```ts
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) {
      return NextResponse.redirect(new URL(safeNext, origin));
    }
```

**With:**

```ts
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) {
      return NextResponse.redirect(new URL(safeNext, origin));
    }
    console.error("[auth/callback] code exchange failed:", error.message);
```

---

## Verification checklist

After applying all fixes:
1. `npm run build` in `apps/web/` succeeds with no TypeScript errors
2. On signup, the email confirmation link should route through `/auth/callback`
3. Visiting `/login?error=auth_callback_failed` shows "Sign-in failed. Please try again."
4. `docker-compose config` parses without errors
5. Auth callback errors are logged to the server console
