import { useEffect, useRef, useState } from "react";
import { AlertTriangle, X } from "lucide-react";
import { api } from "../api";

interface Toast {
  id: number;
  stage: string;
  detail: string;
}

const POLL_INTERVAL_MS = 8000;

/** Global, page-independent failure surfacing. Background jobs (publish,
 * regenerate, script/video generation) run detached from any request and
 * used to only log exceptions server-side — nothing told a reviewer a
 * job had actually failed short of them knowing to open Pipeline Status
 * and read a table. Mounted once in App.tsx (outside <Routes>) so it
 * keeps polling /pipeline/events across page navigation and surfaces new
 * error-status events as dismissible toasts, no matter which page is
 * open when the failure happens. */
export function FailureToasts() {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const lastSeenId = useRef<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    let baselined = false;

    async function poll() {
      try {
        const { events } = await api.pipelineEvents(lastSeenId.current ?? 0);
        if (cancelled) return;

        // The very first poll after mount only establishes the
        // high-water mark — don't retroactively toast errors that
        // happened before this dashboard session opened. Marking this
        // regardless of whether any events came back matters: if the
        // first poll happens to see zero events (the common case — no
        // failure has happened yet), a real failure landing before the
        // *second* poll must still be toasted, not mistaken for more
        // pre-existing history just because it's the first non-empty
        // response.
        const isBaselinePoll = !baselined;
        baselined = true;

        if (events.length === 0) return;
        lastSeenId.current = Math.max(...events.map((e) => e.id));
        if (isBaselinePoll) return;

        const failures = events.filter((e) => e.status === "error");
        if (failures.length > 0) {
          setToasts((prev) => [...prev, ...failures.map((e) => ({ id: e.id, stage: e.stage, detail: e.detail }))]);
        }
      } catch {
        // Polling is best-effort background UX, not core functionality -
        // a failed poll just tries again next interval.
      }
    }

    poll();
    const interval = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  function dismiss(id: number) {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-6 right-6 z-50 flex w-80 flex-col gap-3">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className="flex items-start gap-3 rounded-neu-sm bg-gradient-to-br from-neu-raised to-neu-bg p-4 shadow-neu-raised"
        >
          <AlertTriangle size={18} className="mt-0.5 shrink-0 text-neu-danger" aria-hidden="true" />
          <div className="min-w-0 flex-1">
            <p className="text-xs font-semibold uppercase tracking-wide text-neu-danger">{toast.stage} failed</p>
            <p className="mt-1 break-words text-xs text-neu-muted">{toast.detail}</p>
          </div>
          <button
            onClick={() => dismiss(toast.id)}
            aria-label="Dismiss"
            className="shrink-0 rounded-full p-1 text-neu-muted transition-colors hover:text-neu-text"
          >
            <X size={14} />
          </button>
        </div>
      ))}
    </div>
  );
}
