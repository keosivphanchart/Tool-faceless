import { useEffect, useState } from "react";
import { api } from "../api";

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
      <p className="text-xs text-slate-500">Refreshed weekly by Module 8's analytics pull job.</p>

      <div className="grid grid-cols-2 gap-6">
        <div>
          <h3 className="text-sm font-medium text-slate-400 mb-2">Best-performing hook style</h3>
          <table className="w-full text-sm">
            <tbody>
              {best.by_style.map((r) => (
                <tr key={r.style} className="border-t border-slate-800">
                  <td className="py-1">{r.style}</td>
                  <td>{Math.round(r.views)} avg views</td>
                </tr>
              ))}
              {best.by_style.length === 0 && (
                <tr>
                  <td className="py-2 text-slate-500">No performance data yet.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div>
          <h3 className="text-sm font-medium text-slate-400 mb-2">Best-performing topics</h3>
          <table className="w-full text-sm">
            <tbody>
              {best.by_topic.map((r) => (
                <tr key={r.topic} className="border-t border-slate-800">
                  <td className="py-1">{r.topic}</td>
                  <td>{Math.round(r.views)} avg views</td>
                </tr>
              ))}
              {best.by_topic.length === 0 && (
                <tr>
                  <td className="py-2 text-slate-500">No performance data yet.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div>
        <h3 className="text-sm font-medium text-slate-400 mb-2">Raw performance pulls</h3>
        <table className="w-full text-sm">
          <thead className="text-left text-slate-400">
            <tr>
              <th className="py-2">Video</th>
              <th>Platform</th>
              <th>Views</th>
              <th>Retention</th>
              <th>Pulled</th>
            </tr>
          </thead>
          <tbody>
            {performance.map((p) => (
              <tr key={p.id} className="border-t border-slate-800">
                <td className="py-1">#{p.video_id}</td>
                <td>{p.platform}</td>
                <td>{p.views}</td>
                <td>{p.retention_pct.toFixed(1)}%</td>
                <td className="text-slate-500">{new Date(p.pulled_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
