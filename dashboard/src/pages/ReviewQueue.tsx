import { useEffect, useState } from "react";
import { api, ReviewVideo } from "../api";

export default function ReviewQueue() {
  const [videos, setVideos] = useState<ReviewVideo[]>([]);
  const [note, setNote] = useState<Record<number, string>>({});

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
    await api.regenerateVideo(id, target, note[id]);
    load();
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Review queue ({videos.length} pending)</h2>

      {videos.map((v) => (
        <div key={v.id} className="rounded border border-slate-800 p-4 space-y-3">
          <div className="flex gap-4">
            {v.file_path ? (
              <video controls className="w-48 rounded bg-black" src={`/media?path=${encodeURIComponent(v.file_path)}`} />
            ) : v.thumbnail_path ? (
              <img className="w-48 rounded" src={`/media?path=${encodeURIComponent(v.thumbnail_path)}`} />
            ) : (
              <div className="w-48 h-32 rounded bg-slate-900 flex items-center justify-center text-slate-600 text-xs">
                no preview rendered
              </div>
            )}

            <div className="flex-1 space-y-1 text-sm">
              <p className="font-medium">{v.script.topic}</p>
              <p>
                <span className="text-slate-500">Hook: </span>
                {v.script.text.hook}
              </p>
              <p>
                <span className="text-slate-500">Body: </span>
                {v.script.text.body}
              </p>
              <p>
                <span className="text-slate-500">CTA: </span>
                {v.script.text.cta}
              </p>
            </div>
          </div>

          <textarea
            className="w-full rounded bg-slate-900 border border-slate-800 px-3 py-2 text-sm"
            placeholder="Feedback note (required for regenerate)"
            value={note[v.id] || ""}
            onChange={(e) => setNote({ ...note, [v.id]: e.target.value })}
          />

          <div className="flex gap-2">
            <button onClick={() => approve(v.id)} className="rounded bg-emerald-600 px-3 py-2 text-sm hover:bg-emerald-500">
              Approve
            </button>
            <button onClick={() => reject(v.id)} className="rounded bg-red-600 px-3 py-2 text-sm hover:bg-red-500">
              Reject
            </button>
            <button
              onClick={() => regenerate(v.id, "script")}
              className="rounded bg-slate-700 px-3 py-2 text-sm hover:bg-slate-600"
            >
              Regenerate script
            </button>
            <button
              onClick={() => regenerate(v.id, "video")}
              className="rounded bg-slate-700 px-3 py-2 text-sm hover:bg-slate-600"
            >
              Regenerate video
            </button>
          </div>
        </div>
      ))}

      {videos.length === 0 && <p className="text-slate-500 text-sm">Nothing pending review.</p>}
    </div>
  );
}
