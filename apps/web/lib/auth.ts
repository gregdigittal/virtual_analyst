import { createClient } from "@/lib/supabase/client";

export interface AuthContext {
  tenantId: string;
  userId: string;
  /** Supabase access token for API Authorization header (C1). */
  accessToken: string | null;
}

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
  // Use tenant_id from user metadata if available, otherwise fall back to user.id
  // TODO: Once real multi-tenancy is live, require tenant_id in metadata
  const tenantId =
    (user.app_metadata?.tenant_id as string) ??
    (user.user_metadata?.tenant_id as string) ??
    user.id;
  return { tenantId, userId: user.id, accessToken };
}
