import { useId, useState } from "react";

export interface TrendPoint {
  x: string; // ISO datetime
  y: number;
}

export interface TrendSeries {
  key: string;
  label: string;
  color: string;
  points: TrendPoint[];
}

const WIDTH = 640;
const HEIGHT = 220;
const PAD = { top: 12, right: 56, bottom: 24, left: 44 };

function niceMax(value: number): number {
  if (value <= 0) return 10;
  const magnitude = Math.pow(10, Math.floor(Math.log10(value)));
  const normalized = value / magnitude;
  const step = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10;
  return step * magnitude;
}

function formatCompact(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return `${Math.round(value)}`;
}

/** A small multi-series line chart in plain SVG, matching this app's
 * neumorphic look rather than pulling in a charting library for what's
 * a handful of weekly data points per series. Mark specs (2px lines,
 * round caps, >=4px end-dots with a surface ring, hairline gridlines)
 * and the hover crosshair+tooltip follow the house dataviz method:
 * fixed marks, color only on the data, a legend for 2+ series. */
export function TrendChart({ series, emptyLabel = "No data yet." }: { series: TrendSeries[]; emptyLabel?: string }) {
  const clipId = useId();
  const [hover, setHover] = useState<{ x: number; y: number; date: string; entries: { label: string; color: string; y: number }[] } | null>(
    null
  );

  const allPoints = series.flatMap((s) => s.points);
  if (allPoints.length === 0) {
    return <p className="text-sm text-neu-muted">{emptyLabel}</p>;
  }

  const xValues = allPoints.map((p) => new Date(p.x).getTime());
  const xMin = Math.min(...xValues);
  const xMax = Math.max(...xValues);
  // A single distinct x (one data point, or several series all pulled at
  // the same instant) would otherwise divide by a zero span and pin
  // every point to the left edge - center it in the plot area instead.
  const singleX = xMin === xMax;

  const yMax = niceMax(Math.max(...allPoints.map((p) => p.y), 1));
  const plotW = WIDTH - PAD.left - PAD.right;
  const plotH = HEIGHT - PAD.top - PAD.bottom;

  const scaleX = (t: number) => (singleX ? PAD.left + plotW / 2 : PAD.left + ((t - xMin) / (xMax - xMin)) * plotW);
  const scaleY = (v: number) => PAD.top + plotH - (v / yMax) * plotH;

  const gridSteps = [0, 0.25, 0.5, 0.75, 1];
  // All distinct x positions across every series, for the hover hit targets
  // - one crosshair position can carry a value from each series at once.
  const distinctTimes = Array.from(new Set(allPoints.map((p) => new Date(p.x).getTime()))).sort((a, b) => a - b);

  function showTooltip(t: number) {
    const entries = series
      .map((s) => {
        const point = s.points.find((p) => new Date(p.x).getTime() === t);
        return point ? { label: s.label, color: s.color, y: point.y } : null;
      })
      .filter((e): e is { label: string; color: string; y: number } => e !== null);
    if (entries.length === 0) return;
    setHover({ x: scaleX(t), y: PAD.top, date: new Date(t).toLocaleDateString(), entries });
  }

  return (
    <div className="w-full overflow-x-auto">
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="w-full" style={{ minWidth: 480 }} role="img">
        <defs>
          <clipPath id={`${clipId}-clip`}>
            <rect x={PAD.left} y={PAD.top} width={plotW} height={plotH} />
          </clipPath>
        </defs>

        {/* gridlines + y-axis ticks */}
        {gridSteps.map((step) => {
          const y = PAD.top + plotH * (1 - step);
          return (
            <g key={step}>
              <line x1={PAD.left} y1={y} x2={WIDTH - PAD.right} y2={y} className="stroke-neu-shadowDark" strokeWidth={1} />
              <text x={PAD.left - 8} y={y + 3} textAnchor="end" className="fill-neu-muted" fontSize={9}>
                {formatCompact(yMax * step)}
              </text>
            </g>
          );
        })}

        <g clipPath={`url(#${clipId}-clip)`}>
          {series.map((s) => {
            const sorted = [...s.points].sort((a, b) => new Date(a.x).getTime() - new Date(b.x).getTime());
            const path = sorted.map((p, i) => `${i === 0 ? "M" : "L"} ${scaleX(new Date(p.x).getTime())} ${scaleY(p.y)}`).join(" ");
            return (
              <g key={s.key}>
                <path d={path} fill="none" stroke={s.color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
                {sorted.map((p, i) => (
                  <circle
                    key={i}
                    cx={scaleX(new Date(p.x).getTime())}
                    cy={scaleY(p.y)}
                    r={4}
                    fill={s.color}
                    className="stroke-neu-bg"
                    strokeWidth={2}
                  />
                ))}
              </g>
            );
          })}
        </g>

        {/* direct end-labels live in the PAD.right gutter, outside the
            plot-area clip - last value per series, in text ink not the
            series color (identity comes from the line/dot beside it) */}
        {series.map((s) => {
          const sorted = [...s.points].sort((a, b) => new Date(a.x).getTime() - new Date(b.x).getTime());
          const last = sorted[sorted.length - 1];
          return (
            <text
              key={s.key}
              x={scaleX(new Date(last.x).getTime()) + 8}
              y={scaleY(last.y) + 3}
              className="fill-neu-text"
              fontSize={10}
            >
              {formatCompact(last.y)}
            </text>
          );
        })}

        {/* hover hit targets - wider than the marks, one per distinct x.
            pointerEvents="all" is required here: a "transparent" fill
            isn't "painted" under SVG's default pointer-events value, so
            without it these rects are invisible to the mouse entirely. */}
        {distinctTimes.map((t) => (
          <rect
            key={t}
            x={scaleX(t) - plotW / Math.max(distinctTimes.length, 1) / 2}
            y={PAD.top}
            width={plotW / Math.max(distinctTimes.length, 1)}
            height={plotH}
            fill="transparent"
            pointerEvents="all"
            onMouseEnter={() => showTooltip(t)}
            onMouseLeave={() => setHover(null)}
          />
        ))}

        {hover && (
          <g>
            <line x1={hover.x} y1={PAD.top} x2={hover.x} y2={PAD.top + plotH} className="stroke-neu-muted" strokeWidth={1} />
            {(() => {
              const boxW = 110;
              const boxH = 16 + hover.entries.length * 14;
              const boxX = Math.min(Math.max(hover.x - boxW / 2, PAD.left), WIDTH - PAD.right - boxW);
              return (
                <g transform={`translate(${boxX}, ${hover.y})`}>
                  <rect width={boxW} height={boxH} rx={6} className="fill-neu-raised stroke-neu-shadowDark" strokeWidth={1} />
                  <text x={8} y={14} className="fill-neu-muted" fontSize={9}>
                    {hover.date}
                  </text>
                  {hover.entries.map((e, i) => (
                    <g key={e.label} transform={`translate(8, ${28 + i * 14})`}>
                      <circle cx={3} cy={-3} r={3} fill={e.color} />
                      <text x={10} y={0} className="fill-neu-text" fontSize={10}>
                        {e.label}: {formatCompact(e.y)}
                      </text>
                    </g>
                  ))}
                </g>
              );
            })()}
          </g>
        )}
      </svg>

      {series.length >= 2 && (
        <div className="flex flex-wrap gap-3 mt-2 px-1">
          {series.map((s) => (
            <div key={s.key} className="flex items-center gap-1.5 text-xs text-neu-muted">
              <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ backgroundColor: s.color }} />
              {s.label}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
