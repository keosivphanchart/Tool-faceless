import { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, TextareaHTMLAttributes } from "react";

function cx(...classes: (string | false | undefined)[]) {
  return classes.filter(Boolean).join(" ");
}

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
    <div className={cx("rounded-neu bg-neu-bg shadow-neu-raised", padded && "p-6", className)}>{children}</div>
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
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: keyof typeof BUTTON_VARIANTS }) {
  return (
    <button
      className={cx(
        "rounded-neu-sm bg-neu-bg px-4 py-2 text-sm font-medium shadow-neu-raised-sm transition-all",
        "hover:shadow-neu-raised active:shadow-neu-pressed-sm active:scale-[0.98]",
        "disabled:opacity-40 disabled:pointer-events-none",
        BUTTON_VARIANTS[variant],
        className
      )}
      {...props}
    >
      {children}
    </button>
  );
}

export function NeuInput({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cx(
        "rounded-neu-sm bg-neu-bg px-4 py-2 text-sm text-neu-text shadow-neu-pressed-sm outline-none",
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
        "rounded-neu-sm bg-neu-bg px-4 py-2 text-sm text-neu-text shadow-neu-pressed-sm outline-none",
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
      className={cx(
        "rounded-neu-sm bg-neu-bg px-4 py-2 text-sm text-neu-text shadow-neu-pressed-sm outline-none",
        className
      )}
      {...props}
    />
  );
}

export function NeuBadge({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span
      className={cx(
        "inline-block rounded-full bg-neu-bg px-3 py-1 text-xs font-medium text-neu-muted shadow-neu-raised-xs",
        className
      )}
    >
      {children}
    </span>
  );
}
