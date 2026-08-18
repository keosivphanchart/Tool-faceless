import { useEffect, useState } from "react";
import { api } from "../api";

export default function Settings() {
  const [status, setStatus] = useState<Awaited<ReturnType<typeof api.settingsStatus>> | null>(null);

  useEffect(() => {
    api.settingsStatus().then(setStatus);
  }, []);

  if (!status) return <p className="text-slate-500 text-sm">Loading...</p>;

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-xl font-semibold">Settings</h2>
        <p className="text-sm text-slate-500 mt-1">
          Credentials live in <code className="text-slate-300">.env</code> only and are never sent to this
          dashboard — this page shows configuration status, not values. Edit <code>.env</code> and restart the
          backend to change them.
        </p>
      </div>

      <div>
        <h3 className="text-sm font-medium text-slate-400 mb-2">Niche keywords (TREND_SEED_KEYWORDS)</h3>
        <div className="flex flex-wrap gap-2">
          {status.trend_seed_keywords.map((k) => (
            <span key={k} className="rounded bg-slate-800 px-2 py-1 text-xs">
              {k}
            </span>
          ))}
        </div>
      </div>

      <div>
        <h3 className="text-sm font-medium text-slate-400 mb-2">Reddit subreddits (REDDIT_SUBREDDITS)</h3>
        <div className="flex flex-wrap gap-2">
          {status.reddit_subreddits.map((k) => (
            <span key={k} className="rounded bg-slate-800 px-2 py-1 text-xs">
              r/{k}
            </span>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <span className="text-slate-500">Voice profile (KOKORO_VOICE): </span>
          {status.voice_profile}
        </div>
        <div>
          <span className="text-slate-500">Script model (SCRIPT_MODEL): </span>
          {status.script_model}
        </div>
      </div>

      <div>
        <h3 className="text-sm font-medium text-slate-400 mb-2">API keys / credentials</h3>
        <table className="w-full text-sm">
          <tbody>
            {Object.entries(status.credentials_configured).map(([key, configured]) => (
              <tr key={key} className="border-t border-slate-800">
                <td className="py-1">{key}</td>
                <td className={configured ? "text-emerald-400" : "text-red-400"}>
                  {configured ? "configured" : "missing"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
