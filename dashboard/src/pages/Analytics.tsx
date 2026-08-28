import { useEffect, useMemo, useState } from "react";
import { api, PerformanceRow, SpendSummary } from "../api";
import { NeuCard, NeuProgress, NeuSelect } from "../components/Neu";
import { TrendChart, TrendSeries } from "../components/TrendChart";

// Fixed categorical order (blue/orange/aqua) - never reassigned per
// filter, so a platform keeps its color whichever video is selected.
const PLATFORM_COLORS: Record<string, string> = { youtube: "#2a78d6", tiktok: "#eb6834", instagram: "#1baf7a" };
const PLATFORM_LABEL: Record<string, string> = { youtube: "YouTube", tiktok: "TikTok", instagram: "Instagram" };

function VideoTrendCard({ performance }: { performance: PerformanceRow[] }) {
  const videoOptions = useMemo(() => {
    const seen = new Map<number, string>();
    performance.forEach((p) => {
      if (!seen.has(p.video_id)) seen.set(p.video_id, p.topic);
    });
    return Array.from(seen.entries()).map(([id, topic]) => ({ id, topic }));
  }, [performance]);

  const [selectedId, setSelectedId] = useState<number | null>(null);

  useEffect(() => {
    if (selectedId === null && videoOptions.length > 0) setSelectedId(videoOptions[0].id);
  }, [videoOptions, selectedId]);

  const series: TrendSeries[] = useMemo(() => {
    if (selectedId === null) return [];
    const byPlatform = new Map<string, PerformanceRow[]>();
    performance
      .filter((p) => p.video_id === selectedId)
      .forEach((p) => {
        if (!byPlatform.has(p.platform)) byPlatform.set(p.platform, []);
        byPlatform.get(p.platform)!.push(p);
      });
    return Array.from(byPlatform.entries()).map(([platform, rows]) => ({
      key: platform,
      label: PLATFORM_LABEL[platform] ?? platform,
      color: PLATFORM_COLORS[platform] ?? "#888",
      points: rows.map((r) => ({ x: r.pulled_at, y: r.views })),
    }));
  }, [performance, selectedId]);

  return (
    <NeuCard>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-neu-muted">Views over time</h3>
        {videoOptions.length > 0 && (
          <NeuSelect
            className="text-xs"
            value={selectedId ?? ""}
            onChange={(e) => setSelectedId(Number(e.target.value))}
          >
            {videoOptions.map((v) => (
              <option key={v.id} value={v.id}>
                #{v.id} {v.topic}
              </option>
            ))}
          </NeuSelect>
        )}
      </div>
      <TrendChart series={series} emptyLabel="No performance data yet." />
    </NeuCard>
  );
}

function SpendCard({ spend }: { spend: SpendSummary | null }) {
  if (!spend) return null;

  const dailyPct = spend.daily_budget_usd > 0 ? (spend.daily_spend_usd / spend.daily_budget_usd) * 100 : 0;
  const monthlyPct = spend.monthly_budget_usd > 0 ? (spend.monthly_spend_usd / spend.monthly_budget_usd) * 100 : 0;
  const trendSeries: TrendSeries[] =
    spend.by_day.length > 0
      ? [{ key: "spend", label: "Spend", color: "#2a78d6", points: spend.by_day.map((d) => ({ x: d.date, y: d.cost_usd })) }]
      : [];

  return (
    <NeuCard>
      <h3 className="text-sm font-medium text-neu-muted mb-3">LLM spend</h3>
      <p className="text-xs text-neu-muted mb-4">
        Estimated from token counts, tracked in-memory since the last restart — not a precise bill.{" "}
        {spend.total_calls} generation{spend.total_calls === 1 ? "" : "s"} counted.
      </p>

      <div className="grid grid-cols-2 gap-4 mb-4">
        <div>
          <p className="text-xs text-neu-muted mb-1">
            Today: ${spend.daily_spend_usd.toFixed(4)}
            {spend.daily_budget_usd > 0 && ` / $${spend.daily_budget_usd.toFixed(2)}`}
          </p>
          {spend.daily_budget_usd > 0 ? <NeuProgress value={Math.min(dailyPct, 100)} /> : <p className="text-xs text-neu-muted">unlimited</p>}
        </div>
        <div>
          <p className="text-xs text-neu-muted mb-1">
            This month: ${spend.monthly_spend_usd.toFixed(4)}
            {spend.monthly_budget_usd > 0 && ` / $${spend.monthly_budget_usd.toFixed(2)}`}
          </p>
          {spend.monthly_budget_usd > 0 ? (
            <NeuProgress value={Math.min(monthlyPct, 100)} />
          ) : (
            <p className="text-xs text-neu-muted">unlimited</p>
          )}
        </div>
      </div>

      <TrendChart series={trendSeries} emptyLabel="No LLM calls recorded yet." />

      {spend.by_provider.length > 0 && (
        <div className="flex flex-wrap gap-2 mt-3">
          {spend.by_provider.map((p) => (
            <span key={p.provider} className="text-xs text-neu-muted rounded-full px-3 py-1 shadow-neu-raised-xs">
              {p.provider}: ${p.cost_usd.toFixed(4)}
            </span>
          ))}
        </div>
      )}
    </NeuCard>
  );
}

export default function Analytics() {
  const [best, setBest] = useState<{ by_style: any[]; by_topic: any[] }>({ by_style: [], by_topic: [] });
  const [performance, setPerformance] = useState<PerformanceRow[]>([]);
  const [spend, setSpend] = useState<SpendSummary | null>(null);

  useEffect(() => {
    api.bestPerformers().then(setBest);
    api.performance().then(setPerformance);
    api.spendSummary().then(setSpend);
  }, []);

  return (
    <div className="space-y-8">
      <h2 className="text-xl font-semibold">Analytics</h2>
      <p className="text-xs text-neu-muted">Refreshed weekly by Module 8's analytics pull job.</p>

      <VideoTrendCard performance={performance} />

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

      <SpendCard spend={spend} />

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
                <td className="w-40">
                  <div className="flex items-center gap-2">
                    <NeuProgress value={p.retention_pct} />
                    <span className="shrink-0 text-xs text-neu-muted">{p.retention_pct.toFixed(1)}%</span>
                  </div>
                </td>
                <td className="text-neu-muted">{new Date(p.pulled_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </NeuCard>
    </div>
  );
}
