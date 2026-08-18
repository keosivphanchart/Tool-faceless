import { useEffect, useState } from "react";
import { api, ScriptRecord } from "../api";
import { NeuBadge, NeuButton, NeuCard, NeuInput, NeuSelect } from "../components/Neu";

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

      <NeuCard className="flex gap-3">
        <NeuInput
          className="flex-1"
          placeholder="Generate script for topic..."
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
        />
        <NeuSelect value={style} onChange={(e) => setStyle(e.target.value)}>
          <option value="explainer">explainer</option>
          <option value="listicle">listicle</option>
          <option value="story">story</option>
          <option value="hot_take">hot take</option>
        </NeuSelect>
        <NeuButton variant="primary" disabled={busy} onClick={generate}>
          Generate
        </NeuButton>
      </NeuCard>

      <NeuInput
        className="w-full"
        placeholder="Search past scripts by topic..."
        value={search}
        onChange={(e) => {
          setSearch(e.target.value);
          load(e.target.value);
        }}
      />

      <div className="space-y-3">
        {scripts.map((s) => (
          <NeuCard key={s.id}>
            <div className="flex justify-between items-center text-sm text-neu-muted">
              <span className="text-neu-text">{s.topic}</span>
              <div className="flex gap-2">
                <NeuBadge>{s.style}</NeuBadge>
                <NeuBadge>{s.length_variant}</NeuBadge>
                <NeuBadge>{s.status}</NeuBadge>
              </div>
            </div>
            <p className="mt-3 text-sm font-medium">{s.script.hook}</p>
            <p className="text-sm text-neu-muted mt-1">{s.script.body}</p>
          </NeuCard>
        ))}
        {scripts.length === 0 && <p className="text-neu-muted text-sm">No scripts yet.</p>}
      </div>
    </div>
  );
}
