import { useEffect, useState } from "react";
import { api } from "../api";
import { NeuBadge, NeuCard } from "../components/Neu";

export default function PublishHistory() {
  const [rows, setRows] = useState<any[]>([]);

  useEffect(() => {
    api.publishHistory().then(setRows);
  }, []);

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">Publish history</h2>
      <NeuCard>
        <table className="w-full text-sm">
          <thead className="text-left text-neu-muted">
            <tr>
              <th className="pb-3 font-medium">Topic</th>
              <th className="pb-3 font-medium">Platforms</th>
              <th className="pb-3 font-medium">Published</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neu-shadowDark/60">
            {rows.map((r) => (
              <tr key={r.id}>
                <td className="py-3">{r.topic}</td>
                <td className="space-x-2">
                  {Object.entries(r.platform_ids || {}).map(([platform, id]) => (
                    <NeuBadge key={platform}>
                      {platform}: {String(id)}
                    </NeuBadge>
                  ))}
                </td>
                <td className="text-neu-muted">{new Date(r.created_at).toLocaleString()}</td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={3} className="py-6 text-center text-neu-muted">
                  Nothing published yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </NeuCard>
    </div>
  );
}
