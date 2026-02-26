import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// --- Next.js mocks ---
let mockPathname = "/baselines";
const mockPush = vi.fn();
const mockRefresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush, refresh: mockRefresh }),
  usePathname: () => mockPathname,
}));

vi.mock("next/link", () => ({
  __esModule: true,
  default: ({
    children,
    href,
    ...props
  }: {
    children: React.ReactNode;
    href: string;
    [k: string]: unknown;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("next/image", () => ({
  __esModule: true,
  default: (props: Record<string, unknown>) => <img {...props} />,
}));

// --- Auth mock ---
vi.mock("@/lib/auth", () => ({
  getAuthContext: vi.fn(async () => ({
    tenantId: "tenant-test",
    userId: "user-test",
    accessToken: "mock-token",
    tenantIdIsFallback: false,
  })),
  signOut: vi.fn(async () => {}),
}));

// --- API mock ---
vi.mock("@/lib/api", () => ({
  api: {
    setAccessToken: vi.fn(),
    notifications: {
      list: vi.fn(async () => ({ items: [], total: 0, unread_count: 3 })),
    },
  },
}));

import { VASidebar } from "@/components/VASidebar";

describe("VASidebar", () => {
  beforeEach(() => {
    localStorage.clear();
    mockPathname = "/baselines";
    mockPush.mockClear();
    mockRefresh.mockClear();
  });

  it("renders all 4 group headings", async () => {
    render(<VASidebar />);
    await screen.findByRole("navigation");
    expect(screen.getByText("SETUP")).toBeInTheDocument();
    expect(screen.getByText("CONFIGURE")).toBeInTheDocument();
    expect(screen.getByText("ANALYZE")).toBeInTheDocument();
    expect(screen.getByText("REPORT")).toBeInTheDocument();
  });

  it("renders nav links in the SETUP group", async () => {
    render(<VASidebar />);
    const nav = await screen.findByRole("navigation");
    expect(within(nav).getByText("Dashboard")).toBeInTheDocument();
    expect(within(nav).getByText("Marketplace")).toBeInTheDocument();
    expect(within(nav).getByText("Import Excel")).toBeInTheDocument();
    expect(within(nav).getByText("Groups")).toBeInTheDocument();
  });

  it("renders nav links in the CONFIGURE group", async () => {
    render(<VASidebar />);
    const nav = await screen.findByRole("navigation");
    expect(within(nav).getByText("Baselines")).toBeInTheDocument();
    expect(within(nav).getByText("Drafts")).toBeInTheDocument();
    expect(within(nav).getByText("Scenarios")).toBeInTheDocument();
  });

  it("renders nav links in the ANALYZE group", async () => {
    render(<VASidebar />);
    const nav = await screen.findByRole("navigation");
    expect(within(nav).getByText("Runs")).toBeInTheDocument();
    expect(within(nav).getByText("Budgets")).toBeInTheDocument();
    expect(within(nav).getByText("Covenants")).toBeInTheDocument();
  });

  it("renders nav links in the REPORT group", async () => {
    render(<VASidebar />);
    const nav = await screen.findByRole("navigation");
    expect(within(nav).getByText("Board Packs")).toBeInTheDocument();
    expect(within(nav).getByText("Memos")).toBeInTheDocument();
    expect(within(nav).getByText("Documents")).toBeInTheDocument();
  });

  it("renders utility links", async () => {
    render(<VASidebar />);
    const nav = await screen.findByRole("navigation");
    expect(within(nav).getByText("Workflows")).toBeInTheDocument();
    expect(within(nav).getByText("Changesets")).toBeInTheDocument();
    expect(within(nav).getByText("Inbox")).toBeInTheDocument();
    expect(within(nav).getByText("Notifications")).toBeInTheDocument();
    expect(within(nav).getByText("Settings")).toBeInTheDocument();
  });

  it("renders notification badge with unread count", async () => {
    render(<VASidebar />);
    const badge = await screen.findByText("3");
    expect(badge).toBeInTheDocument();
    expect(badge.className).toMatch(/bg-va-danger/);
  });

  it("renders VA logo linking to /baselines", async () => {
    render(<VASidebar />);
    await screen.findByRole("navigation");
    const logo = screen.getByAltText("Virtual Analyst");
    expect(logo).toBeInTheDocument();
    expect(logo.tagName).toBe("IMG");
    const link = logo.closest("a");
    expect(link).not.toBeNull();
    expect(link).toHaveAttribute("href", "/baselines");
  });

  it("highlights active link based on pathname", async () => {
    mockPathname = "/baselines";
    render(<VASidebar />);
    await screen.findByRole("navigation");
    const activeLink = screen.getByRole("link", { name: "Baselines" });
    expect(activeLink.className).toMatch(/text-va-blue/);
  });

  it("does not highlight non-active links", async () => {
    mockPathname = "/baselines";
    render(<VASidebar />);
    await screen.findByRole("navigation");
    const inactiveLink = screen.getByRole("link", { name: "Runs" });
    expect(inactiveLink.className).not.toMatch(/text-va-blue/);
  });

  it("toggles group collapse on header click", async () => {
    const user = userEvent.setup();
    render(<VASidebar />);
    await screen.findByRole("navigation");
    const setupHeader = screen.getByRole("button", { name: /SETUP/i });
    // Links in SETUP should be visible initially
    expect(screen.getByText("Dashboard")).toBeVisible();
    // Click to collapse
    await user.click(setupHeader);
    // Links should be hidden
    expect(screen.queryByText("Dashboard")).not.toBeVisible();
    // Click to expand again
    await user.click(setupHeader);
    expect(screen.getByText("Dashboard")).toBeVisible();
  });

  it("renders sign out button", async () => {
    render(<VASidebar />);
    await screen.findByRole("navigation");
    expect(
      screen.getByRole("button", { name: /sign out/i }),
    ).toBeInTheDocument();
  });

  it("persists collapse state to localStorage", async () => {
    const user = userEvent.setup();
    render(<VASidebar />);
    await screen.findByRole("navigation");
    const collapseBtn = screen.getByRole("button", { name: /collapse sidebar/i });
    await user.click(collapseBtn);
    expect(localStorage.getItem("va-sidebar-collapsed")).toBe("true");
  });

  it("restores collapse state from localStorage", async () => {
    localStorage.setItem("va-sidebar-collapsed", "true");
    render(<VASidebar />);
    const nav = await screen.findByRole("navigation");
    expect(nav.className).toMatch(/w-16/);
  });

  it("persists group collapse state to localStorage", async () => {
    const user = userEvent.setup();
    render(<VASidebar />);
    await screen.findByRole("navigation");
    const setupHeader = screen.getByRole("button", { name: /SETUP/i });
    await user.click(setupHeader);
    const stored = JSON.parse(localStorage.getItem("va-sidebar-groups") ?? "{}");
    expect(stored.setup).toBe(true);
  });

  it("accepts onClose prop for mobile drawer", async () => {
    const onClose = vi.fn();
    render(<VASidebar mobileOpen onClose={onClose} />);
    const nav = await screen.findByRole("navigation");
    expect(nav).toBeInTheDocument();
    const user = userEvent.setup();
    const closeBtn = screen.getByRole("button", { name: /close menu/i });
    await user.click(closeBtn);
    expect(onClose).toHaveBeenCalled();
  });

  it("renders backdrop when mobileOpen is true", async () => {
    render(<VASidebar mobileOpen onClose={vi.fn()} />);
    await screen.findByRole("navigation");
    expect(document.querySelector("[data-testid='mobile-backdrop']")).toBeInTheDocument();
  });

  it("toggles rail mode when collapse button is clicked", async () => {
    const user = userEvent.setup();
    render(<VASidebar />);
    await screen.findByRole("navigation");
    const sidebar = screen.getByRole("navigation");
    // Should start expanded (w-56)
    expect(sidebar.className).toMatch(/w-56/);
    // Click collapse button
    const collapseBtn = screen.getByRole("button", {
      name: /collapse sidebar/i,
    });
    await user.click(collapseBtn);
    // Should be collapsed (w-16)
    expect(sidebar.className).toMatch(/w-16/);
    // Group heading full text should not be in the document in rail mode
    expect(screen.queryByText("SETUP")).not.toBeInTheDocument();
    // Click expand button
    const expandBtn = screen.getByRole("button", {
      name: /expand sidebar/i,
    });
    await user.click(expandBtn);
    expect(sidebar.className).toMatch(/w-56/);
  });
});
