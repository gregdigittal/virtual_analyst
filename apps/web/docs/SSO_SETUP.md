# SSO setup (Google & Microsoft)

To enable "Continue with Google" and "Continue with Microsoft" on the login and signup pages, configure Supabase Auth providers.

## 1. Supabase Dashboard

1. Open your project → **Authentication** → **Providers**.
2. **Google**
   - Enable the Google provider.
   - Add your OAuth 2.0 Client ID and Client Secret from [Google Cloud Console](https://console.cloud.google.com/apis/credentials) (create a OAuth 2.0 Client ID for "Web application", add authorized redirect URI: `https://hfbjypuoojstjquoyqid.supabase.co/auth/v1/callback`).
3. **Microsoft (Azure)**
   - Enable the Azure provider.
   - In [Azure Portal](https://portal.azure.com/) → App registrations → New registration (or use existing). Add a redirect URI: `https://hfbjypuoojstjquoyqid.supabase.co/auth/v1/callback`.
   - Copy Application (client) ID and create a client secret; add them in Supabase.

## 2. Redirect URLs

In **Authentication** → **URL Configuration**, add your app URLs to **Redirect URLs**.

You can have multiple entries simultaneously. Add whichever environments you need:

| Environment | Redirect URL | When to add |
|---|---|---|
| Local dev | `http://localhost:3000/auth/callback` | Only if you want to test OAuth locally (optional) |
| Vercel | `https://virtual-analyst-ten.vercel.app/auth/callback` | Current production URL |
| Custom domain | `https://yourcustomdomain.com/auth/callback` | Once DNS is configured; you can then remove the Vercel entry |

After OAuth, Supabase redirects to `/auth/callback` with a PKCE `code` parameter. The callback route handler (`app/auth/callback/route.ts`) exchanges the code for a session and then redirects the user to `/baselines` (default) or the `next` query parameter path.

## 3. API auth (JWT verification)

So the backend can trust tenant/user instead of trusting client-sent headers, set **SUPABASE_JWT_SECRET** on the API (same value as in Supabase: **Project Settings → API → JWT Secret**). The API will then verify `Authorization: Bearer <access_token>` and set `X-Tenant-ID` / `X-User-ID` from the token. The web app sends the Supabase access token with API requests when the user is signed in.

## 4. Optional: tenant / domain allowlist

To restrict sign-in to certain domains (e.g. your company), use Supabase Auth hooks or enforce in your API after the user is created. The VA app does not enforce domain allowlisting by default.
