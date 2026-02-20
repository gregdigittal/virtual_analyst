import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { NextResponse, type NextRequest } from "next/server";
import { logger } from "@/lib/logger";

export async function GET(request: NextRequest) {
  const { searchParams, origin } = request.nextUrl;
  const code = searchParams.get("code");
  const token = searchParams.get("token");
  const next = searchParams.get("next") ?? "/baselines";

  // Validate `next` is a safe relative path
  const safeNext =
    next && next.startsWith("/") && !next.startsWith("//")
      ? next
      : "/baselines";

  // R11-07: SAML SSO flow — token is a JWT issued by the API
  if (token) {
    const tenantId = searchParams.get("tenant_id") ?? "";
    const response = NextResponse.redirect(new URL(safeNext, origin));
    response.cookies.set("va-saml-token", token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      maxAge: 3600,
      path: "/",
    });
    if (tenantId) {
      response.cookies.set("va-tenant-id", tenantId, {
        httpOnly: false,
        secure: process.env.NODE_ENV === "production",
        sameSite: "lax",
        maxAge: 3600,
        path: "/",
      });
    }
    return response;
  }

  if (code) {
    const cookieStore = await cookies();
    const supabase = createServerClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL ?? "",
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "",
      {
        cookies: {
          getAll() {
            return cookieStore.getAll();
          },
          setAll(cookiesToSet: { name: string; value: string; options?: object }[]) {
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options)
            );
          },
        },
      },
    );

    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) {
      return NextResponse.redirect(new URL(safeNext, origin));
    }
    logger.error("[auth/callback] code exchange failed", { message: error.message });
  }

  // If code is missing or exchange failed, send to login with an error hint
  const loginUrl = new URL("/login", origin);
  loginUrl.searchParams.set("error", "auth_callback_failed");
  return NextResponse.redirect(loginUrl);
}
