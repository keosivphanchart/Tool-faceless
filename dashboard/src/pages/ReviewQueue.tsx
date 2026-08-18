import { useEffect, useState } from "react";
import { api, ReviewVideo } from "../api";
import { NeuButton, NeuCard, NeuTextarea, StoryboardStrip } from "../components/Neu";
import { useToast } from "../components/Toasts";

type Action = "approve" | "reject" | "regenerate-script" | "regenerate-video";

export default function ReviewQueue() {
  const [videos, setVideos] = useState<ReviewVideo[]>([]);
  const [note, setNote] = useState<Record<number, string>>({});
  const [regenerating, setRegenerating] = useState<Set<number>>(new Set());
  const [actionBusy, setActionBusy] = useState<Record<number, Action | undefined>>({});
  const { notify } = useToast();

  const load = () => api.listPendingVideos().then(setVideos);

  useEffect(() => {
    load();
  }, []);

  function setBusy(id: number, action: Action | undefined) {
    setActionBusy((prev) => ({ ...prev, [id]: action }));
  }

  function errorMessage(err: unknown): string {
    return err instanceof Error ? err.message : String(err);
  }

  async function approve(id: number) {
    setBusy(id, "approve");
    try {
      await api.approveVideo(id);
      notify("success", "Video approved", "Publishing in the background — check Publish history for the result.");
      load();
    } catch (err) {
      notify("error", "Approve failed", errorMessage(err));
    } finally {
      setBusy(id, undefined);
    }
  }

  async function reject(id: number) {
    if (!window.confirm("Reject this video? It will be removed from the review queue.")) return;

    setBusy(id, "reject");
    try {
      await api.rejectVideo(id, note[id] || "");
      notify("success", "Video rejected");
      load();
    } catch (err) {
      notify("error", "Reject failed", errorMessage(err));
    } finally {
      setBusy(id, undefined);
    }
  }

  async function regenerate(id: number, target: "script" | "video") {
    if (!note[id]) {
      notify("error", "Feedback note required", "Add a note before regenerating so the rewrite knows what to fix.");
      return;
    }

    setBusy(id, target === "script" ? "regenerate-script" : "regenerate-video");
    try {
      // The rewrite (LLM) and/or reassembly (TTS + ffmpeg) run as a
      // background job on the server, so the response comes back before
      // the new script/video exists. Drop the rejected item immediately,
      // then poll for a bit so the replacement shows up once it's ready
      // instead of requiring a manual refresh.
      await api.regenerateVideo(id, target, note[id]);
      notify("success", "Regeneration started", "Running in the background — this can take a while.");
      setRegenerating((prev) => new Set(prev).add(id));
      load();

      const previousIds = new Set(videos.map((v) => v.id));
      let attempts = 0;
      const poll = async () => {
        attempts += 1;
        const fresh = await api.listPendingVideos();
        setVideos(fresh);
        const hasNewItem = fresh.some((v) => !previousIds.has(v.id));
        if (hasNewItem || attempts >= 10) {
          setRegenerating((prev) => {
            const next = new Set(prev);
            next.delete(id);
            return next;
          });
          return;
        }
        setTimeout(poll, 3000);
      };
      setTimeout(poll, 3000);
    } catch (err) {
      notify("error", "Could not start regeneration", errorMessage(err));
    } finally {
      setBusy(id, undefined);
    }
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Review queue ({videos.length} pending)</h2>
      {regenerating.size > 0 && (
        <p className="text-xs text-neu-muted">
          Regenerating {regenerating.size} item{regenerating.size > 1 ? "s" : ""} in the background — the
          rewrite/reassembly can take a while, this will refresh automatically.
        </p>
      )}

      {videos.map((v) => {
        const busy = actionBusy[v.id];
        return (
          <NeuCard key={v.id} className="space-y-4">
            <div className="flex gap-4">
              {v.file_path ? (
                <video
                  controls
                  className="w-48 rounded-neu-sm shadow-neu-pressed-sm"
                  src={`/media?path=${encodeURIComponent(v.file_path)}`}
                />
              ) : v.thumbnail_path ? (
                <img
                  className="w-48 rounded-neu-sm shadow-neu-pressed-sm"
                  src={`/media?path=${encodeURIComponent(v.thumbnail_path)}`}
                />
              ) : (
                <div className="w-48 h-32 rounded-neu-sm shadow-neu-pressed-sm flex items-center justify-center text-neu-muted text-xs">
                  no preview rendered
                </div>
              )}

              <div className="flex-1 space-y-1 text-sm">
                <p className="font-medium">{v.script.topic}</p>
                <p>
                  <span className="text-neu-muted">Hook: </span>
                  {v.script.text.hook}
                </p>
                <p>
                  <span className="text-neu-muted">Body: </span>
                  {v.script.text.body}
                </p>
                <p>
                  <span className="text-neu-muted">CTA: </span>
                  {v.script.text.cta}
                </p>
              </div>
            </div>

            {v.script.text.storyboard && <StoryboardStrip shots={v.script.text.storyboard} />}

            <NeuTextarea
              className="w-full"
              placeholder="Feedback note (required for regenerate)"
              value={note[v.id] || ""}
              onChange={(e) => setNote({ ...note, [v.id]: e.target.value })}
            />

            <div className="flex gap-2">
              <NeuButton variant="success" disabled={!!busy} loading={busy === "approve"} onClick={() => approve(v.id)}>
                {busy === "approve" ? "Approving..." : "Approve"}
              </NeuButton>
              <NeuButton variant="danger" disabled={!!busy} loading={busy === "reject"} onClick={() => reject(v.id)}>
                {busy === "reject" ? "Rejecting..." : "Reject"}
              </NeuButton>
              <NeuButton
                disabled={!!busy}
                loading={busy === "regenerate-script"}
                onClick={() => regenerate(v.id, "script")}
              >
                {busy === "regenerate-script" ? "Starting..." : "Regenerate script"}
              </NeuButton>
              <NeuButton
                disabled={!!busy}
                loading={busy === "regenerate-video"}
                onClick={() => regenerate(v.id, "video")}
              >
                {busy === "regenerate-video" ? "Starting..." : "Regenerate video"}
              </NeuButton>
            </div>
          </NeuCard>
        );
      })}

      {videos.length === 0 && <p className="text-neu-muted text-sm">Nothing pending review.</p>}
    </div>
  );
}
