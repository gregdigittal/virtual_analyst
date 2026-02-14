// Example: Virtual Analyst Button (Tailwind)
export function VAButton({ variant = "primary", className = "", ...props }) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-va-sm px-4 py-2 text-sm font-medium transition " +
    "focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue/60";
  const variants = {
    primary: "bg-va-blue text-va-text hover:bg-va-blue/90 shadow-va-glow-blue",
    secondary: "border border-va-border bg-transparent text-va-text hover:bg-white/5",
    ghost: "bg-transparent text-va-text2 hover:bg-white/5",
    danger: "bg-va-danger text-va-text hover:bg-va-danger/90",
  };
  return <button className={`${base} ${variants[variant]} ${className}`} {...props} />;
}
