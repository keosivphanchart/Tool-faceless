import { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, TextareaHTMLAttributes } from "react";
import { Loader2 } from "lucide-react";

function cx(...classes: (string | false | undefined)[]) {
  return classes.filter(Boolean).join(" ");
}

// Convex ("popping out") vs. concave ("pressed in") background gradients —
// this is what actually reads as physical/tactile rather than flat. A
// box-shadow pair alone gives depth at the edges; the gradient across the
// face is what sells the curvature skeuomorphism is going for. Raised
// elements go light (top-left) to base (bottom-right); pressed/embossed
// elements go the other way, base to light, like light is falling into a
// carved recess instead of bouncing off a bump.
const CONVEX = "bg-gradient-to-br from-neu-raised to-neu-bg";
const CONCAVE = "bg-gradient-to-br from-neu-bg to-neu-raised";

export function NeuCard({
  children,
  className,
  padded = true,
}: {
  children: ReactNode;
  className?: string;
  padded?: boolean;
}) {
  return (
    <div className={cx("rounded-neu shadow-neu-raised", CONVEX, padded && "p-6", className)}>{children}</div>
  );
}

const BUTTON_VARIANTS = {
  primary: "text-neu-accent",
  success: "text-neu-success",
  danger: "text-neu-danger",
  neutral: "text-neu-text",
} as const;

export function NeuButton({
  variant = "neutral",
  className,
  children,
  loading = false,
  disabled,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: keyof typeof BUTTON_VARIANTS; loading?: boolean }) {
  return (
    <button
      className={cx(
        "rounded-neu-sm px-4 py-2 text-sm font-medium shadow-neu-raised-sm transition-all",
        "inline-flex items-center gap-2",
        CONVEX,
        "hover:shadow-neu-raised",
        "active:shadow-neu-pressed-sm active:from-neu-bg active:to-neu-raised active:scale-[0.98]",
        "disabled:opacity-40 disabled:pointer-events-none",
        BUTTON_VARIANTS[variant],
        className
      )}
      disabled={disabled || loading}
      aria-busy={loading}
      {...props}
    >
      {loading && <Loader2 size={14} className="animate-spin" aria-hidden="true" />}
      {children}
    </button>
  );
}

export function NeuInput({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cx(
        "rounded-neu-sm px-4 py-2 text-sm text-neu-text shadow-neu-pressed-sm outline-none",
        CONCAVE,
        "placeholder:text-neu-muted focus:shadow-neu-pressed",
        className
      )}
      {...props}
    />
  );
}

export function NeuTextarea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={cx(
        "rounded-neu-sm px-4 py-2 text-sm text-neu-text shadow-neu-pressed-sm outline-none",
        CONCAVE,
        "placeholder:text-neu-muted focus:shadow-neu-pressed",
        className
      )}
      {...props}
    />
  );
}

export function NeuSelect({ className, ...props }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={cx("rounded-neu-sm px-4 py-2 text-sm text-neu-text shadow-neu-pressed-sm outline-none", CONCAVE, className)}
      {...props}
    />
  );
}

export function NeuBadge({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span
      className={cx(
        "inline-block rounded-full px-3 py-1 text-xs font-medium text-neu-muted shadow-neu-raised-xs",
        CONVEX,
        className
      )}
    >
      {children}
    </span>
  );
}

/** A small raised, circular icon chip — glyph sitting on a convex disc
 * with its own shadow, the "raised icon" half of the neumorphic pattern
 * (buttons/cards handle the other half). Used for nav items and anywhere
 * else a glyph needs to look like a physical token rather than flat text. */
export function NeuIcon({
  children,
  active = false,
  className,
}: {
  children: ReactNode;
  active?: boolean;
  className?: string;
}) {
  return (
    <span
      className={cx(
        "inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-base",
        active ? cx(CONCAVE, "shadow-neu-pressed-sm") : cx(CONVEX, "shadow-neu-raised-xs"),
        className
      )}
    >
      {children}
    </span>
  );
}

/** A pillowy, read-only on/off indicator — concave track, convex thumb
 * that slides to whichever side is "on". Read-only because every boolean
 * this dashboard shows (credentials configured, flags from .env) is
 * server-driven, not something the dashboard itself can flip. */
export function NeuToggle({ on, label }: { on: boolean; label?: string }) {
  return (
    <span className="inline-flex items-center gap-2">
      <span
        className={cx(
          "relative inline-block h-6 w-11 rounded-full shadow-neu-pressed-sm transition-colors",
          on ? "bg-gradient-to-br from-neu-success/70 to-neu-success/30" : CONCAVE
        )}
      >
        <span
          className={cx(
            "absolute top-0.5 h-5 w-5 rounded-full shadow-neu-raised-xs transition-all",
            CONVEX,
            on ? "left-[1.375rem] shadow-[0_0_0_2px_theme(colors.neu.success)]" : "left-0.5"
          )}
        />
      </span>
      {label && <span className="text-xs text-neu-muted">{label}</span>}
    </span>
  );
}

/** A pillowy progress bar — concave track, convex fill — for the
 * tactile "sliders/progress bars" half of the neumorphic pattern.
 * Read-only (percentages from analytics data), so it renders as a
 * meter, not an interactive <input type="range">. */
export function NeuProgress({ value, max = 100, className }: { value: number; max?: number; className?: string }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div className={cx("h-3 w-full rounded-full shadow-neu-pressed-sm", CONCAVE, className)}>
      <div
        className="h-full rounded-full bg-gradient-to-br from-neu-accentMuted to-neu-accent shadow-neu-raised-xs transition-all"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

export interface StoryboardShot {
  beat: string;
  visual: string;
  keywords: string[];
}

/** Per-beat visual plan (hook/promise/body/payoff/cta), each shot shown
 * as its own small pressed panel — the reviewer's shot-by-shot view of
 * what's on screen before approving, not just the spoken text. */
export function StoryboardStrip({ shots }: { shots: StoryboardShot[] | undefined }) {
  if (!shots || shots.length === 0) return null;

  return (
    <div className="grid grid-cols-5 gap-2">
      {shots.map((shot) => (
        <div key={shot.beat} className={cx("rounded-neu-sm shadow-neu-pressed-sm p-2 space-y-1", CONCAVE)}>
          <p className="text-[10px] uppercase tracking-wide text-neu-accent font-semibold">{shot.beat}</p>
          <p className="text-xs text-neu-text leading-snug">{shot.visual}</p>
        </div>
      ))}
    </div>
  );
}
