// Tailwind theme extension for Virtual Analyst (Option B)
export const virtualAnalystTheme = {
  extend: {
    colors: {
  "va": {
    "midnight": "#0B1020",
    "ink": "#10172A",
    "surface": "#0F172A",
    "panel": "#121A33",
    "border": "#22304F",
    "blue": "#3B82F6",
    "violet": "#7C3AED",
    "magenta": "#EC4899",
    "ice": "#E6F0FF",
    "muted": "#94A3B8",
    "text": "#E5E7EB",
    "text2": "#B6C2D1",
    "success": "#22C55E",
    "warning": "#F59E0B",
    "danger": "#EF4444"
  }
},
    borderRadius: {
  "va-xs": "6px",
  "va-sm": "10px",
  "va-md": "14px",
  "va-lg": "18px",
  "va-xl": "24px"
},
    boxShadow: {
  "va-sm": "0 1px 2px rgba(0,0,0,0.25)",
  "va-md": "0 10px 30px rgba(0,0,0,0.35)",
  "va-glow-blue": "0 0 0 1px rgba(59,130,246,0.35), 0 0 30px rgba(59,130,246,0.25)",
  "va-glow-violet": "0 0 0 1px rgba(124,58,237,0.35), 0 0 30px rgba(124,58,237,0.25)"
},
    fontFamily: {
  "brand": [
    "Sora",
    "ui-sans-serif",
    "system-ui",
    "-apple-system",
    "Segoe UI",
    "Roboto",
    "Inter",
    "Arial"
  ],
  "sans": [
    "Inter",
    "ui-sans-serif",
    "system-ui",
    "-apple-system",
    "Segoe UI",
    "Roboto",
    "Arial"
  ],
  "mono": [
    "JetBrains Mono",
    "ui-monospace",
    "SFMono-Regular",
    "Menlo",
    "Monaco",
    "Consolas",
    "monospace"
  ]
}
  }
}
