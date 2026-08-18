import { useEffect, useState } from "react";
import { api } from "../api";

export default function PublishHistory() {
  const [rows, setRows] = useState<any[]>([]);

  useEffect(() => {
    api.publishHistory().then(setRows);
  }, []);

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">Publish history</h2>
      <table className="w-full text-sm">
        <thead className="text-left text-slate-400">
          <tr>
            <th className="py-2">Topic</th>
            <th>Platforms</th>
            <th>Published</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className="border-t border-slate-800">
              <td className="py-2">{r.topic}</td>
              <td className="space-x-2">
                {Object.entries(r.platform_ids || {}).map(([platform, id]) => (
                  <span key={platform} className="rounded bg-slate-800 px-2 py-1 text-xs">
                    {platform}: {String(id)}
                  </span>
                ))}
              </td>
              <td className="text-slate-500">{new Date(r.created_at).toLocaleString()}</td>
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td colSpan={3} className="py-6 text-center text-slate-500">
                Nothing published yet.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
