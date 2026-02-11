import "./globals.css";

export const metadata = {
  title: "Virtual Analyst",
  description: "Deterministic financial modeling platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-background text-foreground antialiased">
        {children}
      </body>
    </html>
  );
}
