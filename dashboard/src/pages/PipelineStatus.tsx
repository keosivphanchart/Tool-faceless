import { useEffect, useState } from "react";
import { api } from "../api";

export default function PipelineStatus() {
  const [stages, setStages] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);

  const load = () => api.pipelineStatus().then((r) => setStages(r.stages));

  useEffect(() => {
    load();
  }, []);

  async function runTrendFinder() {
    setBusy(true);
    try {
      await api.triggerTrends();
      setTimeout(load, 1500);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Pipeline status</h2>
        <button
          disabled={busy}
          onClick={runTrendFinder}
          className="rounded bg-indigo-600 px-3 py-2 text-sm hover:bg-indigo-500 disabled:opacity-50"
        >
          Run trend finder now
        </button>
      </div>

      <table className="w-full text-sm">
        <thead className="text-left text-slate-400">
          <tr>
            <th className="py-2">Stage</th>
            <th>Status</th>
            <th>Detail</th>
            <th>Last run</th>
          </tr>
        </thead>
        <tbody>
          {stages.map((s) => (
            <tr key={s.stage} className="border-t border-slate-800">
              <td className="py-2">{s.stage}</td>
              <td className={s.status === "error" ? "text-red-400" : "text-emerald-400"}>{s.status}</td>
              <td className="text-slate-400">{s.detail}</td>
              <td className="text-slate-500">{new Date(s.at).toLocaleString()}</td>
            </tr>
          ))}
          {stages.length === 0 && (
            <tr>
              <td colSpan={4} className="py-6 text-center text-slate-500">
                No pipeline runs recorded yet. Trigger a stage above or via cron.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
