import { useEffect, useState } from "react";
import { api, ScriptRecord } from "../api";
import { NeuBadge, NeuButton, NeuCard, NeuInput, NeuSelect, StoryboardStrip } from "../components/Neu";
import { useToast } from "../components/Toasts";

export default function Scripts() {
  const [scripts, setScripts] = useState<ScriptRecord[]>([]);
  const [search, setSearch] = useState("");
  const [topic, setTopic] = useState("");
  const [style, setStyle] = useState("explainer");
  const [busy, setBusy] = useState(false);
  const { notify } = useToast();

  const load = (q?: string) => api.listScripts(q).then(setScripts);

  useEffect(() => {
    load();
  }, []);

  async function generate() {
    if (!topic.trim()) return;
    const generatingTopic = topic.trim();
    setBusy(true);
    try {
      await api.triggerScript(generatingTopic, style);
      setTopic("");
      notify(
        "success",
        "Script generation started",
        `"${generatingTopic}" — video assembly follows automatically once it's done.`
      );
      setTimeout(() => load(), 1500);
    } catch (err) {
      notify("error", "Could not start script generation", err instanceof Error ? err.message : String(err));
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
        <NeuButton variant="primary" loading={busy} onClick={generate}>
          {busy ? "Starting..." : "Generate"}
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
            {s.script.storyboard && (
              <div className="mt-3">
                <StoryboardStrip shots={s.script.storyboard} />
              </div>
            )}
          </NeuCard>
        ))}
        {scripts.length === 0 && <p className="text-neu-muted text-sm">No scripts yet.</p>}
      </div>
    </div>
  );
}
