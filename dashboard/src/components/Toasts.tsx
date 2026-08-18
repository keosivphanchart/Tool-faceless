import { createContext, ReactNode, useCallback, useContext, useEffect, useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, X } from "lucide-react";
import { api } from "../api";

type ToastKind = "success" | "error";

interface Toast {
  id: number;
  kind: ToastKind;
  title: string;
  detail?: string;
}

interface ToastContextValue {
  notify: (kind: ToastKind, title: string, detail?: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const POLL_INTERVAL_MS = 8000;
let nextLocalId = -1; // negative range so local toast ids never collide with polled event ids

/** Every user-triggered action (Approve, Reject, Generate, Regenerate,
 * Run trend finder) used to just silently reload the page's data on
 * success and do nothing visible on failure short of an unhandled
 * promise rejection in the console — no spinner while it's running, no
 * confirmation it worked, no visible error if it didn't. useToast()'s
 * notify() gives every page a one-line way to surface both.
 *
 * This also subsumes the old FailureToasts: background jobs (publish,
 * regenerate) run detached from any request and can fail well after the
 * triggering click's toast already faded, so this still separately polls
 * /pipeline/events for error-status events and surfaces those the same
 * way, on the same stack, so there's one visual system instead of two. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const lastSeenEventId = useRef<number | null>(null);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const notify = useCallback(
    (kind: ToastKind, title: string, detail?: string) => {
      const id = nextLocalId--;
      setToasts((prev) => [...prev, { id, kind, title, detail }]);
      if (kind === "success") {
        setTimeout(() => dismiss(id), 5000);
      }
    },
    [dismiss]
  );

  useEffect(() => {
    let cancelled = false;
    let baselined = false;

    async function poll() {
      try {
        const { events } = await api.pipelineEvents(lastSeenEventId.current ?? 0);
        if (cancelled) return;

        // The first poll after mount only establishes the high-water
        // mark — don't retroactively toast errors that happened before
        // this dashboard session opened. Marked regardless of whether
        // any events came back: if the first poll sees zero events (the
        // common case), a real failure landing before the *second* poll
        // must still be toasted, not mistaken for pre-existing history.
        const isBaselinePoll = !baselined;
        baselined = true;

        if (events.length === 0) return;
        lastSeenEventId.current = Math.max(...events.map((e) => e.id));
        if (isBaselinePoll) return;

        const failures = events.filter((e) => e.status === "error");
        if (failures.length > 0) {
          setToasts((prev) => [
            ...prev,
            ...failures.map((e) => ({ id: e.id, kind: "error" as const, title: `${e.stage} failed`, detail: e.detail })),
          ]);
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

  return (
    <ToastContext.Provider value={{ notify }}>
      {children}
      {toasts.length > 0 && (
        <div className="fixed bottom-6 right-6 z-50 flex w-80 flex-col gap-3">
          {toasts.map((toast) => (
            <div
              key={toast.id}
              className="flex items-start gap-3 rounded-neu-sm bg-gradient-to-br from-neu-raised to-neu-bg p-4 shadow-neu-raised"
            >
              {toast.kind === "error" ? (
                <AlertTriangle size={18} className="mt-0.5 shrink-0 text-neu-danger" aria-hidden="true" />
              ) : (
                <CheckCircle2 size={18} className="mt-0.5 shrink-0 text-neu-success" aria-hidden="true" />
              )}
              <div className="min-w-0 flex-1">
                <p
                  className={`text-xs font-semibold uppercase tracking-wide ${
                    toast.kind === "error" ? "text-neu-danger" : "text-neu-success"
                  }`}
                >
                  {toast.title}
                </p>
                {toast.detail && <p className="mt-1 break-words text-xs text-neu-muted">{toast.detail}</p>}
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
      )}
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast() must be used within <ToastProvider>");
  return ctx;
}
