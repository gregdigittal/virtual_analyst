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

### Production: avoid localhost redirect

If "Sign up / Sign in with SSO" sends users to **localhost** after the provider (Google/Microsoft) returns, fix it as follows:

1. **Set the app base URL in production**  
   In your production environment (e.g. Vercel), set:
   ```bash
   NEXT_PUBLIC_APP_URL=https://your-production-domain.com
   ```
   Use your real production URL (e.g. `https://virtual-analyst-ten.vercel.app` or your custom domain). The app uses this for OAuth `redirectTo` and email links so redirects go to production, not localhost.

2. **Supabase URL Configuration**  
   In the **same** Supabase project used by production:
   - **Authentication** → **URL Configuration**
   - Set **Site URL** to your production app URL (e.g. `https://your-production-domain.com`).
   - In **Redirect URLs**, ensure the production callback is listed (e.g. `https://your-production-domain.com/auth/callback`). You can keep `http://localhost:3000/auth/callback` for local dev if you use the same project.

3. **OAuth provider (Google / Microsoft)**  
   In the provider’s app config, **Authorized redirect URIs** must point to **Supabase**, not your app (e.g. `https://<project-ref>.supabase.co/auth/v1/callback`). Do not add your app’s `/auth/callback` URL there. Supabase then redirects the user to your app using the Redirect URLs from step 2.

After redeploying with `NEXT_PUBLIC_APP_URL` set and updating Supabase, SSO should redirect users to your production app.

### SAML (tenant SSO) — IdP certificate required in production

If you use **SAML** sign-in (tenant-configured IdP), the API requires an **IdP certificate** for production:

1. **Why**: The API verifies the SAML response XML signature using the IdP’s public certificate. Without it, the ACS endpoint returns 400 in production.
2. **Where to set it**: Use the SAML config API (`PUT /api/v1/auth/saml/config`) with the `idp_certificate` field set to the IdP’s PEM-formatted X.509 certificate (from your IdP’s metadata or admin).
3. **Format**: PEM text, e.g. `-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----`.
4. **Check**: `GET /api/v1/auth/saml/config` returns `idp_certificate_configured: true` when a certificate is stored.

Without a stored certificate in production, SAML ACS will return 400 and users cannot sign in via SAML.

## 3. API auth (JWT verification)

So the backend can trust tenant/user instead of trusting client-sent headers, set **SUPABASE_JWT_SECRET** on the API (same value as in Supabase: **Project Settings → API → JWT Secret**). The API will then verify `Authorization: Bearer <access_token>` and set `X-Tenant-ID` / `X-User-ID` from the token. The web app sends the Supabase access token with API requests when the user is signed in.

## 4. Optional: tenant / domain allowlist

To restrict sign-in to certain domains (e.g. your company), use Supabase Auth hooks or enforce in your API after the user is created. The VA app does not enforce domain allowlisting by default.
