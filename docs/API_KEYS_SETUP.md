# Replacing Placeholder API Keys with Actual Keys

The API uses **environment variables** for LLM and other secrets. Placeholders (empty or example values) are in `.env.example` only; real values go in a **local `.env`** file that is not committed.

## Steps

### 1. Create or edit your local `.env`

From the project root:

```bash
# If you don't have .env yet, copy the example
cp .env.example .env

# Then edit .env (use your editor of choice)
# e.g. code .env   or   nano .env
```

### 2. Set the LLM API keys

In `.env`, set **real** values (no quotes needed unless the value contains spaces):

```env
# Anthropic (Claude) — get from https://console.anthropic.com/ → API Keys
ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# OpenAI (GPT) — get from https://platform.openai.com/api-keys
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

- **Anthropic**: [Console](https://console.anthropic.com/) → **API Keys** → Create key.  
- **OpenAI**: [API keys](https://platform.openai.com/api-keys) → Create new secret key.

You can set one or both. The LLM router uses policy and fallback; if one provider is missing or fails, the other is used when configured.

### 3. Restart the API so it picks up changes

Environment variables are read at process start:

```bash
# If running with uvicorn
uvicorn apps.api.app.main:app --reload

# Or your usual run command
```

After restart, the API will use the keys from `.env` (or from the shell if you export them there).

### 4. Keep keys out of version control

- **Do not** put real keys in `.env.example` or any file that is committed.
- `.env` and `.env.local` are listed in `.gitignore`; keep it that way.
- In CI or production, use the platform’s secret store (e.g. Vercel env vars, GitHub Secrets) and set `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` there instead of using a `.env` file.

## Optional: other secrets in `.env`

`.env.example` also includes placeholders for:

- **Supabase**: `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY`, `SUPABASE_JWT_SECRET`
- **Stripe** (billing): `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_ID_*`
- **OAuth**: `OAUTH_STATE_SECRET`, `OAUTH_ENCRYPTION_KEY`
- **Integrations**: `XERO_*`, `QUICKBOOKS_*`

Replace those in `.env` when you enable the corresponding features.

## Verifying

- With valid keys, LLM-backed features (drafts, memo generation, Excel classification, etc.) should succeed instead of failing with 401 or “provider not available”.
- With keys missing or invalid, the router may return errors such as “All providers failed” or 401 from the provider.
