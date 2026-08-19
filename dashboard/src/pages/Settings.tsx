import { useEffect, useState } from "react";
import { api } from "../api";
import { NeuBadge, NeuCard, NeuToggle } from "../components/Neu";

export default function Settings() {
  const [status, setStatus] = useState<Awaited<ReturnType<typeof api.settingsStatus>> | null>(null);

  useEffect(() => {
    api.settingsStatus().then(setStatus);
  }, []);

  if (!status) return <p className="text-neu-muted text-sm">Loading...</p>;

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-xl font-semibold">Settings</h2>
        <p className="text-sm text-neu-muted mt-1">
          Credentials live in <code className="text-neu-text">.env</code> only and are never sent to this
          dashboard — this page shows configuration status, not values. Edit <code>.env</code> and restart the
          backend to change them.
        </p>
      </div>

      <NeuCard>
        <h3 className="text-sm font-medium text-neu-muted mb-3">Niche keywords (TREND_SEED_KEYWORDS)</h3>
        <div className="flex flex-wrap gap-2">
          {status.trend_seed_keywords.map((k) => (
            <NeuBadge key={k}>{k}</NeuBadge>
          ))}
        </div>
      </NeuCard>

      <NeuCard>
        <h3 className="text-sm font-medium text-neu-muted mb-3">Reddit subreddits (REDDIT_SUBREDDITS)</h3>
        <div className="flex flex-wrap gap-2">
          {status.reddit_subreddits.map((k) => (
            <NeuBadge key={k}>r/{k}</NeuBadge>
          ))}
        </div>
      </NeuCard>

      <NeuCard className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <span className="text-neu-muted">Voice profile (KOKORO_VOICE): </span>
          {status.voice_profile}
        </div>
        <div>
          <span className="text-neu-muted">Script provider (SCRIPT_PROVIDER): </span>
          {status.script_provider}
        </div>
        <div>
          <span className="text-neu-muted">
            {status.script_provider.toUpperCase()}_MODEL:{" "}
          </span>
          {status.script_model}
        </div>
      </NeuCard>

      <NeuCard>
        <h3 className="text-sm font-medium text-neu-muted mb-3">API keys / credentials</h3>
        <table className="w-full text-sm">
          <tbody className="divide-y divide-neu-shadowDark/60">
            {Object.entries(status.credentials_configured).map(([key, configured]) => (
              <tr key={key}>
                <td className="py-2">{key}</td>
                <td className="py-2">
                  <NeuToggle on={configured} label={configured ? "configured" : "missing"} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </NeuCard>

      <NeuCard>
        <h3 className="text-sm font-medium text-neu-muted mb-3">
          Automation — all opt-in, set in <code className="text-neu-text">.env</code>
        </h3>
        <table className="w-full text-sm">
          <tbody className="divide-y divide-neu-shadowDark/60">
            {[
              ["AUTO_GENERATE_ENABLED", status.automation.auto_generate_enabled],
              ["AUTO_TREND_FINDER_ENABLED", status.automation.auto_trend_finder_enabled],
              ["AUTO_APPROVE_ENABLED", status.automation.auto_approve_enabled],
              ["AB_TEST_ENABLED", status.automation.ab_test_enabled],
              ["DIGEST_ENABLED", status.automation.digest_enabled],
              ["CLEANUP_ENABLED", status.automation.cleanup_enabled],
            ].map(([key, on]) => (
              <tr key={key as string}>
                <td className="py-2">{key}</td>
                <td className="py-2">
                  <NeuToggle on={on as boolean} label={on ? "on" : "off"} />
                </td>
              </tr>
            ))}
            <tr>
              <td className="py-2">Daily / monthly LLM budget</td>
              <td className="py-2 text-neu-muted">
                {status.automation.daily_cost_budget_usd > 0 ? `$${status.automation.daily_cost_budget_usd}/day` : "unlimited"}
                {" · "}
                {status.automation.monthly_cost_budget_usd > 0
                  ? `$${status.automation.monthly_cost_budget_usd}/mo`
                  : "unlimited"}
              </td>
            </tr>
          </tbody>
        </table>
      </NeuCard>
    </div>
  );
}
