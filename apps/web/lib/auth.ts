import { createClient } from "@/lib/supabase/client";

export interface AuthContext {
  tenantId: string;
  userId: string;
  /** Supabase access token for API Authorization header (C1). */
  accessToken: string | null;
  /**
   * True when tenant_id was not found in user metadata and fell back to user.id.
   * Use this flag to surface warnings in dev or gate features in production.
   */
  tenantIdIsFallback: boolean;
}

/**
 * Resolve the tenant_id for the current user.
 *
 * Resolution order:
 *   1. user.app_metadata.tenant_id  (set by Supabase Auth Hook / service role)
 *   2. user.user_metadata.tenant_id (set during sign-up via client)
 *   3. user.id                      (single-org fallback — development only)
 *
 * When NEXT_PUBLIC_REQUIRE_TENANT_ID=true, resolution path 3 is treated as an
 * error: getAuthContext() returns null and the user is redirected to /login.
 * Enable this env var once Supabase Auth is configured to inject tenant_id for
 * all users via an Auth Hook (Database Webhook on auth.users insert).
 *
 * ## Enabling strict multi-tenancy
 *
 * 1. Create a Supabase Auth Hook that sets raw_app_meta_data->>'tenant_id'
 *    to the appropriate organisation UUID for each new user.
 * 2. For existing users, run a one-off migration:
 *    UPDATE auth.users
 *    SET raw_app_meta_data = raw_app_meta_data || jsonb_build_object('tenant_id', id)
 *    WHERE raw_app_meta_data->>'tenant_id' IS NULL;
 * 3. Set NEXT_PUBLIC_REQUIRE_TENANT_ID=true in production environment variables.
 * 4. Remove the tenantIdIsFallback field once all users have explicit tenant_ids.
 */
export async function getAuthContext(): Promise<AuthContext | null> {
  const supabase = createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user?.id) return null;
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const accessToken = session?.access_token ?? null;

  const explicitTenantId =
    (user.app_metadata?.tenant_id as string | undefined) ??
    (user.user_metadata?.tenant_id as string | undefined);

  const requireTenantId =
    process.env.NEXT_PUBLIC_REQUIRE_TENANT_ID === "true";

  if (!explicitTenantId) {
    if (requireTenantId) {
      // Hard-fail: tenant_id is required but not present. Force re-login.
      console.warn(
        "[auth] tenant_id missing from user metadata and NEXT_PUBLIC_REQUIRE_TENANT_ID=true. " +
          `user_id=${user.id}. Returning null to force re-authentication.`
      );
      return null;
    }
    // Development fallback: warn once per session to avoid log spam.
    if (typeof window !== "undefined") {
      const warnKey = `va_tenant_fallback_warned_${user.id}`;
      if (!sessionStorage.getItem(warnKey)) {
        console.warn(
          "[auth] tenant_id not found in user metadata. Falling back to user.id as tenant_id. " +
            "Set NEXT_PUBLIC_REQUIRE_TENANT_ID=true once Auth Hooks inject tenant_id for all users."
        );
        sessionStorage.setItem(warnKey, "1");
      }
    }
    return {
      tenantId: user.id,
      userId: user.id,
      accessToken,
      tenantIdIsFallback: true,
    };
  }

  return {
    tenantId: explicitTenantId,
    userId: user.id,
    accessToken,
    tenantIdIsFallback: false,
  };
}

/** Sign out the current user via the shared Supabase client. */
export async function signOut(): Promise<void> {
  const supabase = createClient();
  await supabase.auth.signOut();
}
