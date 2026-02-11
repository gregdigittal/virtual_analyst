export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col items-start gap-6 px-6 py-16">
      <div className="space-y-3">
        <p className="text-sm uppercase tracking-widest text-muted-foreground">
          Virtual Analyst
        </p>
        <h1 className="text-4xl font-semibold tracking-tight">
          Deterministic financial modeling with an LLM-assisted draft layer.
        </h1>
        <p className="text-lg text-muted-foreground">
          This environment is ready for hosted testing and continuous delivery.
        </p>
      </div>
      <div className="rounded-lg border border-border bg-card p-4 text-sm text-card-foreground">
        API health: <span className="font-medium">/api/v1/health/live</span>
      </div>
    </main>
  );
}
