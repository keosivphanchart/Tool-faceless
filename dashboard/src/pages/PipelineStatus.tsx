import { useEffect, useState } from "react";
import { api } from "../api";
import { NeuButton, NeuCard } from "../components/Neu";
import { useToast } from "../components/Toasts";

export default function PipelineStatus() {
  const [stages, setStages] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const { notify } = useToast();

  const load = () => api.pipelineStatus().then((r) => setStages(r.stages));

  useEffect(() => {
    load();
  }, []);

  async function runTrendFinder() {
    setBusy(true);
    try {
      await api.triggerTrends();
      notify("success", "Trend finder started", "Running in the background — this table refreshes automatically.");
      setTimeout(load, 1500);
    } catch (err) {
      notify("error", "Could not start trend finder", err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Pipeline status</h2>
        <NeuButton variant="primary" loading={busy} onClick={runTrendFinder}>
          {busy ? "Starting..." : "Run trend finder now"}
        </NeuButton>
      </div>

      <NeuCard>
        <table className="w-full text-sm">
          <thead className="text-left text-neu-muted">
            <tr>
              <th className="pb-3 font-medium">Stage</th>
              <th className="pb-3 font-medium">Status</th>
              <th className="pb-3 font-medium">Detail</th>
              <th className="pb-3 font-medium">Last run</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neu-shadowDark/60">
            {stages.map((s) => (
              <tr key={s.stage}>
                <td className="py-3">{s.stage}</td>
                <td className={s.status === "error" ? "text-neu-danger" : "text-neu-success"}>{s.status}</td>
                <td className="text-neu-muted">{s.detail}</td>
                <td className="text-neu-muted">{new Date(s.at).toLocaleString()}</td>
              </tr>
            ))}
            {stages.length === 0 && (
              <tr>
                <td colSpan={4} className="py-6 text-center text-neu-muted">
                  No pipeline runs recorded yet. Trigger a stage above or via cron.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </NeuCard>
    </div>
  );
}
