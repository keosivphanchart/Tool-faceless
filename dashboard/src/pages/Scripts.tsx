import { useEffect, useState } from "react";
import { api, ScriptRecord } from "../api";

export default function Scripts() {
  const [scripts, setScripts] = useState<ScriptRecord[]>([]);
  const [search, setSearch] = useState("");
  const [topic, setTopic] = useState("");
  const [style, setStyle] = useState("explainer");
  const [busy, setBusy] = useState(false);

  const load = (q?: string) => api.listScripts(q).then(setScripts);

  useEffect(() => {
    load();
  }, []);

  async function generate() {
    if (!topic.trim()) return;
    setBusy(true);
    try {
      await api.triggerScript(topic, style);
      setTopic("");
      setTimeout(() => load(), 1500);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Script library</h2>

      <div className="flex gap-2">
        <input
          className="flex-1 rounded bg-slate-900 border border-slate-800 px-3 py-2 text-sm"
          placeholder="Generate script for topic..."
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
        />
        <select
          className="rounded bg-slate-900 border border-slate-800 px-3 py-2 text-sm"
          value={style}
          onChange={(e) => setStyle(e.target.value)}
        >
          <option value="explainer">explainer</option>
          <option value="listicle">listicle</option>
          <option value="story">story</option>
          <option value="hot_take">hot take</option>
        </select>
        <button
          disabled={busy}
          onClick={generate}
          className="rounded bg-indigo-600 px-3 py-2 text-sm hover:bg-indigo-500 disabled:opacity-50"
        >
          Generate
        </button>
      </div>

      <input
        className="w-full rounded bg-slate-900 border border-slate-800 px-3 py-2 text-sm"
        placeholder="Search past scripts by topic..."
        value={search}
        onChange={(e) => {
          setSearch(e.target.value);
          load(e.target.value);
        }}
      />

      <div className="space-y-3">
        {scripts.map((s) => (
          <div key={s.id} className="rounded border border-slate-800 p-3">
            <div className="flex justify-between text-sm text-slate-400">
              <span>{s.topic}</span>
              <span>
                {s.style} · {s.length_variant} · {s.status}
              </span>
            </div>
            <p className="mt-2 text-sm font-medium">{s.script.hook}</p>
            <p className="text-sm text-slate-400">{s.script.body}</p>
          </div>
        ))}
        {scripts.length === 0 && <p className="text-slate-500 text-sm">No scripts yet.</p>}
      </div>
    </div>
  );
}
