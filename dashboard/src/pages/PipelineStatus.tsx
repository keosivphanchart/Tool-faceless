import { useEffect, useState } from "react";
import { api, ReviewVideo } from "../api";
import { NeuButton, NeuCard } from "../components/Neu";
import { useToast } from "../components/Toasts";

function minutesOverdue(scheduledFor: string): number {
  return Math.round((Date.now() - new Date(scheduledFor).getTime()) / 60000);
}

function NeedsAttentionCard({ videos, reload }: { videos: ReviewVideo[]; reload: () => void }) {
  const { notify } = useToast();
  const [busyId, setBusyId] = useState<number | null>(null);

  if (videos.length === 0) return null;

  async function retry(id: number) {
    setBusyId(id);
    try {
      await api.approveVideo(id);
      notify("success", "Retrying now", "Publishing in the background — check Publish history for the result.");
      reload();
    } catch (err) {
      notify("error", "Retry failed", err instanceof Error ? err.message : String(err));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <NeuCard>
      <h3 className="text-sm font-medium text-neu-danger mb-1">Needs attention ({videos.length})</h3>
      <p className="text-xs text-neu-muted mb-3">
        Approved and scheduled, but still hasn't published well past its time — usually a repeated publish failure
        (bad token, quota, network). Check Settings for the account's connection status, then retry.
      </p>
      <table className="w-full text-sm">
        <tbody className="divide-y divide-neu-shadowDark/60">
          {videos.map((v) => (
            <tr key={v.id}>
              <td className="py-2">{v.script.topic}</td>
              <td className="py-2 text-neu-danger">
                {minutesOverdue(v.scheduled_for!) >= 120
                  ? `${Math.round(minutesOverdue(v.scheduled_for!) / 60)}h overdue`
                  : `${minutesOverdue(v.scheduled_for!)}m overdue`}
              </td>
              <td className="py-2 text-right">
                <NeuButton loading={busyId === v.id} disabled={busyId !== null && busyId !== v.id} onClick={() => retry(v.id)}>
                  Retry now
                </NeuButton>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </NeuCard>
  );
}

export default function PipelineStatus() {
  const [stages, setStages] = useState<any[]>([]);
  const [needsAttention, setNeedsAttention] = useState<ReviewVideo[]>([]);
  const [busy, setBusy] = useState(false);
  const { notify } = useToast();

  const load = () => api.pipelineStatus().then((r) => setStages(r.stages));
  const loadNeedsAttention = () => api.needsAttention().then(setNeedsAttention);

  useEffect(() => {
    load();
    loadNeedsAttention();
    const interval = setInterval(loadNeedsAttention, 60000);
    return () => clearInterval(interval);
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

      <NeedsAttentionCard videos={needsAttention} reload={loadNeedsAttention} />

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
