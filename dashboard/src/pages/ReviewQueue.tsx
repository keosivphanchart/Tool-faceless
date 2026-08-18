import { useEffect, useState } from "react";
import { api, ReviewVideo } from "../api";
import { NeuButton, NeuCard, NeuTextarea } from "../components/Neu";

export default function ReviewQueue() {
  const [videos, setVideos] = useState<ReviewVideo[]>([]);
  const [note, setNote] = useState<Record<number, string>>({});
  const [regenerating, setRegenerating] = useState<Set<number>>(new Set());

  const load = () => api.listPendingVideos().then(setVideos);

  useEffect(() => {
    load();
  }, []);

  async function approve(id: number) {
    await api.approveVideo(id);
    load();
  }

  async function reject(id: number) {
    await api.rejectVideo(id, note[id] || "");
    load();
  }

  async function regenerate(id: number, target: "script" | "video") {
    if (!note[id]) {
      alert("Add a feedback note before regenerating.");
      return;
    }
    // The rewrite (Claude) and/or reassembly (TTS + ffmpeg) run as a
    // background job on the server, so the response comes back before the
    // new script/video exists. Drop the rejected item immediately, then
    // poll for a bit so the replacement shows up once it's ready instead
    // of requiring a manual refresh.
    await api.regenerateVideo(id, target, note[id]);
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

      {videos.map((v) => (
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

          <NeuTextarea
            className="w-full"
            placeholder="Feedback note (required for regenerate)"
            value={note[v.id] || ""}
            onChange={(e) => setNote({ ...note, [v.id]: e.target.value })}
          />

          <div className="flex gap-2">
            <NeuButton variant="success" onClick={() => approve(v.id)}>
              Approve
            </NeuButton>
            <NeuButton variant="danger" onClick={() => reject(v.id)}>
              Reject
            </NeuButton>
            <NeuButton onClick={() => regenerate(v.id, "script")}>Regenerate script</NeuButton>
            <NeuButton onClick={() => regenerate(v.id, "video")}>Regenerate video</NeuButton>
          </div>
        </NeuCard>
      ))}

      {videos.length === 0 && <p className="text-neu-muted text-sm">Nothing pending review.</p>}
    </div>
  );
}
