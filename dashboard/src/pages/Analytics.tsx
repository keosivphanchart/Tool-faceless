import { useEffect, useState } from "react";
import { api } from "../api";
import { NeuCard } from "../components/Neu";

export default function Analytics() {
  const [best, setBest] = useState<{ by_style: any[]; by_topic: any[] }>({ by_style: [], by_topic: [] });
  const [performance, setPerformance] = useState<any[]>([]);

  useEffect(() => {
    api.bestPerformers().then(setBest);
    api.performance().then(setPerformance);
  }, []);

  return (
    <div className="space-y-8">
      <h2 className="text-xl font-semibold">Analytics</h2>
      <p className="text-xs text-neu-muted">Refreshed weekly by Module 8's analytics pull job.</p>

      <div className="grid grid-cols-2 gap-6">
        <NeuCard>
          <h3 className="text-sm font-medium text-neu-muted mb-3">Best-performing hook style</h3>
          <table className="w-full text-sm">
            <tbody className="divide-y divide-neu-shadowDark/60">
              {best.by_style.map((r) => (
                <tr key={r.style}>
                  <td className="py-2">{r.style}</td>
                  <td>{Math.round(r.views)} avg views</td>
                </tr>
              ))}
              {best.by_style.length === 0 && (
                <tr>
                  <td className="py-2 text-neu-muted">No performance data yet.</td>
                </tr>
              )}
            </tbody>
          </table>
        </NeuCard>

        <NeuCard>
          <h3 className="text-sm font-medium text-neu-muted mb-3">Best-performing topics</h3>
          <table className="w-full text-sm">
            <tbody className="divide-y divide-neu-shadowDark/60">
              {best.by_topic.map((r) => (
                <tr key={r.topic}>
                  <td className="py-2">{r.topic}</td>
                  <td>{Math.round(r.views)} avg views</td>
                </tr>
              ))}
              {best.by_topic.length === 0 && (
                <tr>
                  <td className="py-2 text-neu-muted">No performance data yet.</td>
                </tr>
              )}
            </tbody>
          </table>
        </NeuCard>
      </div>

      <NeuCard>
        <h3 className="text-sm font-medium text-neu-muted mb-3">Raw performance pulls</h3>
        <table className="w-full text-sm">
          <thead className="text-left text-neu-muted">
            <tr>
              <th className="pb-2 font-medium">Video</th>
              <th className="pb-2 font-medium">Platform</th>
              <th className="pb-2 font-medium">Views</th>
              <th className="pb-2 font-medium">Retention</th>
              <th className="pb-2 font-medium">Pulled</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neu-shadowDark/60">
            {performance.map((p) => (
              <tr key={p.id}>
                <td className="py-2">#{p.video_id}</td>
                <td>{p.platform}</td>
                <td>{p.views}</td>
                <td>{p.retention_pct.toFixed(1)}%</td>
                <td className="text-neu-muted">{new Date(p.pulled_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </NeuCard>
    </div>
  );
}
