import type { Config } from "tailwindcss";

// Virtual Analyst CI (Option B) — tokens from virtual_analyst_ci_pack
const vaTheme = {
  colors: {
    va: {
      midnight: "#0B1020",
      ink: "#10172A",
      surface: "#0F172A",
      panel: "#121A33",
      border: "#22304F",
      blue: "#3B82F6",
      violet: "#7C3AED",
      magenta: "#EC4899",
      ice: "#E6F0FF",
      muted: "#94A3B8",
      text: "#E5E7EB",
      text2: "#B6C2D1",
      success: "#22C55E",
      warning: "#F59E0B",
      danger: "#EF4444",
    },
  },
  borderRadius: {
    "va-xs": "6px",
    "va-sm": "10px",
    "va-md": "14px",
    "va-lg": "18px",
    "va-xl": "24px",
  },
  boxShadow: {
    "va-sm": "0 1px 2px rgba(0,0,0,0.25)",
    "va-md": "0 10px 30px rgba(0,0,0,0.35)",
    "va-glow-blue":
      "0 0 0 1px rgba(59,130,246,0.35), 0 0 30px rgba(59,130,246,0.25)",
    "va-glow-violet":
      "0 0 0 1px rgba(124,58,237,0.35), 0 0 30px rgba(124,58,237,0.25)",
  },
  fontFamily: {
    brand: [
      "var(--font-sora)",
      "Sora",
      "ui-sans-serif",
      "system-ui",
      "sans-serif",
    ],
    sans: [
      "var(--font-inter)",
      "Inter",
      "ui-sans-serif",
      "system-ui",
      "sans-serif",
    ],
    mono: [
      "var(--font-jetbrains)",
      "JetBrains Mono",
      "ui-monospace",
      "monospace",
    ],
  },
};

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ...vaTheme.colors,
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        card: "hsl(var(--card))",
        "card-foreground": "hsl(var(--card-foreground))",
        border: "hsl(var(--border))",
        "muted-foreground": "hsl(var(--muted-foreground))",
      },
      borderRadius: vaTheme.borderRadius,
      boxShadow: vaTheme.boxShadow,
      fontFamily: vaTheme.fontFamily,
      keyframes: {
        "slide-in-right": {
          from: { transform: "translateX(100%)" },
          to: { transform: "translateX(0)" },
        },
      },
      animation: {
        "slide-in-right": "slide-in-right 0.25s ease-out",
      },
    },
  },
  plugins: [],
};

export default config;
