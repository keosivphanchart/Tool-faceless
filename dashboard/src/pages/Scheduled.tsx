import { useEffect, useState } from "react";
import { api, ReviewVideo } from "../api";
import { NeuBadge, NeuButton, NeuCard } from "../components/Neu";
import { useToast } from "../components/Toasts";

/** Approved videos waiting on a future publish time. A scheduled video
 * leaves the pending Review queue the moment it's scheduled, and won't
 * show up in Publish history until it actually goes out — without this
 * page there'd be no way to see what's queued and for when, or to change
 * your mind before it fires. */
export default function Scheduled() {
  const [videos, setVideos] = useState<ReviewVideo[]>([]);
  const [busyId, setBusyId] = useState<number | null>(null);
  const { notify } = useToast();

  const load = () => api.listScheduled().then(setVideos);

  useEffect(() => {
    load();
  }, []);

  async function unschedule(id: number) {
    if (!window.confirm("Cancel this scheduled publish? The video stays approved, just not on a schedule.")) return;

    setBusyId(id);
    try {
      await api.unscheduleVideo(id);
      notify("success", "Schedule cancelled");
      load();
    } catch (err) {
      notify("error", "Could not cancel", err instanceof Error ? err.message : String(err));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Scheduled ({videos.length} upcoming)</h2>
      <p className="text-xs text-neu-muted">
        Published automatically at the time shown — checked every minute in the background, no need to keep this
        page open.
      </p>

      <NeuCard>
        <table className="w-full text-sm">
          <thead className="text-left text-neu-muted">
            <tr>
              <th className="pb-3 font-medium">Topic</th>
              <th className="pb-3 font-medium">Publishes at</th>
              <th className="pb-3 font-medium"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neu-shadowDark/60">
            {videos.map((v) => (
              <tr key={v.id}>
                <td className="py-3">{v.script.topic}</td>
                <td>
                  <NeuBadge>{v.scheduled_for ? new Date(v.scheduled_for).toLocaleString() : "—"}</NeuBadge>
                </td>
                <td className="text-right">
                  <NeuButton
                    variant="danger"
                    loading={busyId === v.id}
                    disabled={busyId !== null && busyId !== v.id}
                    onClick={() => unschedule(v.id)}
                  >
                    {busyId === v.id ? "Cancelling..." : "Cancel"}
                  </NeuButton>
                </td>
              </tr>
            ))}
            {videos.length === 0 && (
              <tr>
                <td colSpan={3} className="py-6 text-center text-neu-muted">
                  Nothing scheduled. Schedule a video from the Review queue.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </NeuCard>
    </div>
  );
}
