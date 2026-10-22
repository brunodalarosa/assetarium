import { ChevronRight } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { type ComponentProps, type ReactNode, useId, useState } from "react";
import { Button as BeButton, type ButtonProps } from "@/components/beui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/beui/select";
import { Tooltip } from "@/components/beui/tooltip";
import { EASE_OUT } from "@/lib/ease";
import { cn } from "@/lib/utils";

/** beUI's spring-pressed button with Assetarium sizes: primary, secondary (outlined) and quiet. */
export function Button({ variant = "primary", className, ...props }: Omit<ButtonProps, "variant"> & { variant?: "primary" | "secondary" | "quiet" | "danger" }) {
  const tone = {
    primary: "bg-primary text-primary-foreground hover:bg-primary-hover",
    secondary: "border border-border bg-surface text-foreground hover:bg-surface-2",
    quiet: "bg-transparent text-foreground hover:bg-surface-2",
    danger: "border border-border bg-surface text-fault hover:bg-fault-bg",
  }[variant];
  return <BeButton variant="ghost" size="md" pressScale={0.96} className={cn("h-10 gap-2 px-5 text-[13px] font-medium", tone, className)} {...props} />;
}

/** Icon-only action with a required accessible label that also shows as its focus/hover tooltip. */
export function IconButton({ label, active, className, children, side = "bottom", ...props }: ComponentProps<"button"> & { label: string; active?: boolean; side?: "top" | "bottom" | "left" | "right" }) {
  return (
    <Tooltip content={label} side={side} delay={350}>
      <button
        type="button"
        aria-label={label}
        className={cn(
          "relative grid size-10 place-items-center rounded-xl text-foreground transition-colors hover:bg-surface-2 disabled:pointer-events-none disabled:text-subtle",
          active && "bg-accent-soft text-accent-soft-foreground hover:bg-accent-soft",
          className,
        )}
        {...props}
      >
        {children}
      </button>
    </Tooltip>
  );
}

export type BadgeTone = "neutral" | "warning" | "fault" | "success" | "info";
export function Badge({ tone = "neutral", className, children }: { tone?: BadgeTone; className?: string; children: ReactNode }) {
  const toneClass = {
    neutral: "bg-surface-2 text-muted-foreground",
    warning: "bg-warning-bg text-warning",
    fault: "bg-fault-bg text-fault",
    success: "bg-success-bg text-success",
    info: "bg-accent-soft text-accent-soft-foreground",
  }[tone];
  return <span className={cn("inline-flex h-6 items-center whitespace-nowrap rounded-md px-2 text-[11px] font-medium", toneClass, className)}>{children}</span>;
}

const ANY = "__any";
export function SelectField({ label, value, onChange, options, disabled, id, className }: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: [string, string][];
  disabled?: boolean;
  id?: string;
  className?: string;
}) {
  const labelId = useId();
  return (
    <div className={cn("grid min-w-0 gap-1.5", className)} id={id} data-value={value}>
      <span id={labelId} className="text-xs text-muted-foreground">{label}</span>
      <Select className="min-w-0" value={value === "" ? ANY : value} onValueChange={(next) => onChange(next === ANY ? "" : next)} disabled={disabled}>
        <SelectTrigger labelledBy={labelId} className="h-11 min-w-0 rounded-xl border-border bg-surface px-3 text-[13px] hover:border-border-strong">
          <SelectValue className="min-w-0 truncate text-left" />
        </SelectTrigger>
        <SelectContent className="max-h-72 overflow-y-auto rounded-xl border-border bg-surface shadow-panel scroll-thin">
          {options.map(([optionValue, optionLabel]) => (
            <SelectItem key={optionValue || ANY} value={optionValue === "" ? ANY : optionValue}>{optionLabel}</SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

export function TextField({ label, className, inputClassName, id, ...props }: ComponentProps<"input"> & { label: string; inputClassName?: string }) {
  const auto = useId();
  const inputId = id ?? auto;
  return (
    <div className={cn("grid min-w-0 gap-1.5", className)}>
      <label htmlFor={inputId} className="text-xs text-muted-foreground">{label}</label>
      <input
        id={inputId}
        className={cn(
          "h-11 w-full min-w-0 rounded-xl border border-border bg-surface px-3 text-[13px] text-foreground outline-none transition-colors hover:border-border-strong focus-visible:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/25 disabled:opacity-50",
          inputClassName,
        )}
        {...props}
      />
    </div>
  );
}

/** Evidence disclosure: chevron row that springs its content open. */
export function Disclosure({ title, children, defaultOpen = false, className }: { title: ReactNode; children: ReactNode; defaultOpen?: boolean; className?: string }) {
  const [open, setOpen] = useState(defaultOpen);
  const reduce = useReducedMotion();
  const contentId = useId();
  return (
    <div className={cn("min-w-0", className)}>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={contentId}
        onClick={() => setOpen(!open)}
        className="-mx-1 flex min-h-8 items-center gap-2 rounded-md px-1 text-left text-[12px] font-medium text-foreground hover:bg-surface-2"
      >
        <motion.span animate={{ rotate: open ? 90 : 0 }} transition={reduce ? { duration: 0 } : { type: "spring", duration: 0.35, bounce: 0.25 }} className="grid place-items-center text-muted-foreground">
          <ChevronRight className="size-3.5" aria-hidden />
        </motion.span>
        {title}
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            id={contentId}
            key="content"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={reduce ? { duration: 0 } : { height: { type: "spring", duration: 0.4, bounce: 0.18 }, opacity: { duration: 0.16, ease: EASE_OUT } }}
            className="overflow-hidden"
          >
            <div className="pt-2">{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/** Raw recorded evidence, kept verbatim and selectable. */
export function EvidenceBlock({ title, value }: { title: string; value: unknown }) {
  const text = value === null || value === undefined ? "Unknown" : typeof value === "object" ? JSON.stringify(value, null, 2) : String(value);
  return (
    <Disclosure title={title}>
      <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-words rounded-xl bg-surface-2 p-3 font-mono text-[11px] leading-relaxed text-muted-foreground select-text scroll-thin">{text}</pre>
    </Disclosure>
  );
}

export function Spinner({ className }: { className?: string }) {
  return <span className={cn("search-spinner", className)} aria-hidden />;
}

export function Progress({ value, label, valueText }: { value: number; label: string; valueText: string }) {
  return (
    <div role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(value)} aria-valuetext={valueText} className="h-2 w-full overflow-hidden rounded-full bg-surface-2">
      <motion.div className="h-full rounded-full bg-primary" initial={false} animate={{ width: `${Math.max(2, Math.min(100, value))}%` }} transition={{ type: "spring", stiffness: 160, damping: 26 }} />
    </div>
  );
}

export function Banner({ tone = "fault", children, className, role = "alert" }: { tone?: "fault" | "warning" | "info"; children: ReactNode; className?: string; role?: string }) {
  const toneClass = { fault: "bg-fault-bg text-fault", warning: "bg-warning-bg text-warning", info: "bg-accent-soft text-accent-soft-foreground" }[tone];
  return <div role={role} className={cn("whitespace-pre-wrap break-words rounded-xl px-4 py-3 text-[13px] leading-relaxed", toneClass, className)}>{children}</div>;
}
