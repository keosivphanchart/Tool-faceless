import { useEffect, useState } from "react";
import { api } from "../api";
import { NeuBadge, NeuCard } from "../components/Neu";

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
            {status.script_provider === "ollama" ? "Ollama model (OLLAMA_MODEL): " : "Script model (SCRIPT_MODEL): "}
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
                <td className={configured ? "text-neu-success" : "text-neu-danger"}>
                  {configured ? "configured" : "missing"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </NeuCard>
    </div>
  );
}
