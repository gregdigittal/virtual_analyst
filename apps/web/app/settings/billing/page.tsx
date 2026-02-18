"use client";

import { Nav } from "@/components/nav";
import { VAButton, VACard } from "@/components/ui";
import { api, type BillingPlan, type BillingSubscription, type BillingUsageResponse } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { useCallback, useEffect, useState } from "react";

function UsageMeter({
  label,
  used,
  limit,
}: {
  label: string;
  used: number;
  limit: number | null;
}) {
  const pct = limit && limit > 0 ? Math.min(100, (used / limit) * 100) : 0;
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-sm text-va-text2">
        <span>{label}</span>
        <span>
          {used.toLocaleString()}{" "}
          {limit ? `/ ${limit.toLocaleString()}` : "/ Unlimited"}
        </span>
      </div>
      <div className="h-2 rounded-full bg-va-border">
        <div
          className="h-2 rounded-full bg-va-blue"
          style={{ width: limit ? `${pct}%` : "10%" }}
        />
      </div>
    </div>
  );
}

export default function BillingSettingsPage() {
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | undefined>(undefined);
  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [subscription, setSubscription] = useState<BillingSubscription | null>(null);
  const [usage, setUsage] = useState<BillingUsageResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyPlanId, setBusyPlanId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadBilling = useCallback(async () => {
    if (!tenantId) return;
    setLoading(true);
    setError(null);
    try {
      const [plansRes, subscriptionRes, usageRes] = await Promise.all([
        api.billing.listPlans(tenantId),
        api.billing.getSubscription(tenantId),
        api.billing.getUsage(tenantId),
      ]);
      setPlans(plansRes.plans ?? []);
      setSubscription(subscriptionRes.subscription ?? null);
      setUsage(usageRes);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  useEffect(() => {
    (async () => {
      const ctx = await getAuthContext();
      if (!ctx) return;
      api.setAccessToken(ctx.accessToken);
      setTenantId(ctx.tenantId);
      setUserId(ctx.userId);
    })();
  }, []);

  useEffect(() => {
    if (tenantId) loadBilling();
  }, [tenantId, loadBilling]);

  async function handleSelectPlan(planId: string) {
    if (!tenantId) return;
    setBusyPlanId(planId);
    setError(null);
    try {
      await api.billing.createOrUpdateSubscription(tenantId, userId, planId);
      await loadBilling();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyPlanId(null);
    }
  }

  async function handleCancel() {
    if (!tenantId) return;
    setError(null);
    try {
      await api.billing.cancelSubscription(tenantId, userId);
      await loadBilling();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="min-h-screen bg-va-midnight">
      <Nav />
      <main className="mx-auto max-w-5xl px-4 py-8">
        <div className="mb-6">
          <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
            Billing & Subscription
          </h1>
          <p className="mt-1 text-sm text-va-text2">
            Manage plan selection, usage, and billing lifecycle.
          </p>
        </div>

        {error && (
          <div
            className="mb-4 rounded-va-xs border border-va-danger/50 bg-va-danger/10 px-3 py-2 text-sm text-va-danger"
            role="alert"
          >
            {error}
          </div>
        )}

        {loading ? (
          <p className="text-va-text2">Loading billing…</p>
        ) : (
          <div className="space-y-8">
            <section className="grid gap-4 md:grid-cols-3">
              {plans.map((plan) => {
                const active = subscription?.plan_id === plan.plan_id;
                return (
                  <VACard key={plan.plan_id} className="p-5">
                    <div className="flex items-center justify-between">
                      <h2 className="text-lg font-medium text-va-text">
                        {plan.label}
                      </h2>
                      <span className="rounded-full bg-va-border px-2 py-0.5 text-xs text-va-text2">
                        Tier {plan.tier}
                      </span>
                    </div>
                    <p className="mt-2 text-sm text-va-text2">
                      {plan.features
                        ? Object.keys(plan.features).length
                        : 0}{" "}
                      features
                    </p>
                    <div className="mt-4">
                      {active ? (
                        <div className="text-sm font-medium text-va-success">
                          Current plan
                        </div>
                      ) : (
                        <VAButton
                          variant="secondary"
                          type="button"
                          disabled={busyPlanId === plan.plan_id}
                          onClick={() => handleSelectPlan(plan.plan_id)}
                        >
                          {busyPlanId === plan.plan_id
                            ? "Updating…"
                            : "Select plan"}
                        </VAButton>
                      )}
                    </div>
                  </VACard>
                );
              })}
            </section>

            <section className="grid gap-4 md:grid-cols-2">
              <VACard className="p-5">
                <h2 className="text-lg font-medium text-va-text">
                  Usage meters
                </h2>
                <div className="mt-4 space-y-4">
                  <UsageMeter
                    label="LLM tokens"
                    used={usage?.usage?.usage?.llm_tokens_total ?? 0}
                    limit={usage?.limits?.llm_tokens_monthly ?? null}
                  />
                  <UsageMeter
                    label="Monte Carlo runs"
                    used={usage?.usage?.usage?.mc_runs ?? 0}
                    limit={null}
                  />
                  <UsageMeter
                    label="Sync events"
                    used={usage?.usage?.usage?.sync_events ?? 0}
                    limit={null}
                  />
                </div>
              </VACard>

              <VACard className="p-5">
                <h2 className="text-lg font-medium text-va-text">
                  Subscription details
                </h2>
                {subscription ? (
                  <div className="mt-3 space-y-2 text-sm text-va-text2">
                    <div>
                      Plan:{" "}
                      <span className="font-medium text-va-text">
                        {subscription.plan_id}
                      </span>
                    </div>
                    <div>Status: {subscription.status}</div>
                    <div>
                      Current period:{" "}
                      {subscription.current_period_start
                        ? new Date(
                            subscription.current_period_start
                          ).toLocaleDateString()
                        : "—"}{" "}
                      →{" "}
                      {subscription.current_period_end
                        ? new Date(
                            subscription.current_period_end
                          ).toLocaleDateString()
                        : "—"}
                    </div>
                    <VAButton
                      variant="danger"
                      className="mt-3"
                      onClick={handleCancel}
                    >
                      Cancel subscription
                    </VAButton>
                  </div>
                ) : (
                  <p className="mt-3 text-sm text-va-text2">
                    No active subscription found.
                  </p>
                )}
              </VACard>
            </section>
          </div>
        )}
      </main>
    </div>
  );
}
