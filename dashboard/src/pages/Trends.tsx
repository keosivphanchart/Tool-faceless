import { useEffect, useState } from "react";
import { api, Trend } from "../api";

export default function Trends() {
  const [trends, setTrends] = useState<Trend[]>([]);

  useEffect(() => {
    api.listTrends().then(setTrends);
  }, []);

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">Trend candidates</h2>
      <table className="w-full text-sm">
        <thead className="text-left text-slate-400">
          <tr>
            <th className="py-2">Topic</th>
            <th>Source</th>
            <th>Score</th>
            <th>Used</th>
          </tr>
        </thead>
        <tbody>
          {trends.map((t) => (
            <tr key={t.id} className="border-t border-slate-800">
              <td className="py-2">{t.topic}</td>
              <td className="text-slate-400">{t.source}</td>
              <td>{t.score.toFixed(1)}</td>
              <td>{t.used ? "yes" : "-"}</td>
            </tr>
          ))}
          {trends.length === 0 && (
            <tr>
              <td colSpan={4} className="py-6 text-center text-slate-500">
                No trends yet — run the trend finder from Pipeline status.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
