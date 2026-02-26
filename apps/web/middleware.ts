import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

const protectedPaths = [
  "/baselines", "/runs", "/dashboard", "/drafts", "/scenarios", "/changesets",
  "/notifications", "/settings", "/inbox", "/assignments",
  "/budgets", "/memos", "/documents", "/activity",
  "/excel-connections", "/excel-import", "/afs", "/covenants",
  "/org-structures", "/ventures", "/board-packs",
  "/import", "/benchmark", "/marketplace", "/compare", "/workflows",
];

function isProtected(pathname: string): boolean {
  return protectedPaths.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}

export async function middleware(request: NextRequest) {
  const response = NextResponse.next({ request });

  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
  const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

  const supabase = createServerClient(supabaseUrl, supabaseAnonKey, {
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll(cookiesToSet: { name: string; value: string; options?: object }[]) {
        cookiesToSet.forEach(({ name, value, options }) =>
          response.cookies.set(name, value, options)
        );
      },
    },
  });

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (isProtected(request.nextUrl.pathname) && !user) {
    const redirect = new URL("/login", request.url);
    redirect.searchParams.set("next", request.nextUrl.pathname);
    return NextResponse.redirect(redirect);
  }

  if ((request.nextUrl.pathname === "/login" || request.nextUrl.pathname === "/signup") && user) {
    return NextResponse.redirect(new URL("/baselines", request.url));
  }

  return response;
}

export const config = {
  matcher: [
    "/",
    "/login",
    "/signup",
    "/baselines/:path*",
    "/runs/:path*",
    "/dashboard/:path*",
    "/drafts/:path*",
    "/scenarios/:path*",
    "/changesets/:path*",
    "/notifications/:path*",
    "/settings/:path*",
    "/inbox/:path*",
    "/assignments/:path*",
    "/budgets/:path*",
    "/memos/:path*",
    "/documents/:path*",
    "/activity/:path*",
    "/excel-connections/:path*",
    "/excel-import/:path*",
    "/afs/:path*",
    "/covenants/:path*",
    "/org-structures/:path*",
    "/ventures/:path*",
    "/board-packs/:path*",
    "/import/:path*",
    "/benchmark/:path*",
    "/marketplace/:path*",
    "/compare/:path*",
    "/workflows/:path*",
  ],
};
