import { useEffect, useState } from "react";
import { api, Trend } from "../api";
import { NeuBadge, NeuCard } from "../components/Neu";

export default function Trends() {
  const [trends, setTrends] = useState<Trend[]>([]);

  useEffect(() => {
    api.listTrends().then(setTrends);
  }, []);

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">Trend candidates</h2>
      <NeuCard>
        <table className="w-full text-sm">
          <thead className="text-left text-neu-muted">
            <tr>
              <th className="pb-3 font-medium">Topic</th>
              <th className="pb-3 font-medium">Source</th>
              <th className="pb-3 font-medium">Score</th>
              <th className="pb-3 font-medium">Used</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neu-shadowDark/60">
            {trends.map((t) => (
              <tr key={t.id}>
                <td className="py-3">{t.topic}</td>
                <td>
                  <NeuBadge>{t.source}</NeuBadge>
                </td>
                <td>{t.score.toFixed(1)}</td>
                <td className="text-neu-muted">{t.used ? "yes" : "-"}</td>
              </tr>
            ))}
            {trends.length === 0 && (
              <tr>
                <td colSpan={4} className="py-6 text-center text-neu-muted">
                  No trends yet — run the trend finder from Pipeline status.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </NeuCard>
    </div>
  );
}
