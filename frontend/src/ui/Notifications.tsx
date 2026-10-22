import { CircleCheck, Info, TriangleAlert, X } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { type ReactNode, useEffect, useRef } from "react";
import { SPRING_PANEL } from "@/lib/ease";
import { cn } from "@/lib/utils";
import type { Json } from "../app/api";
import { ago, describeActive, notificationContent, plural, type Tone } from "../app/format";
import {
  dismissToast, notificationAction, openProcessing, saveNotification, setNotificationsOpen, setState, sourceAction, type Toast, useApp,
} from "../app/store";
import { Button, IconButton, Progress, Spinner } from "./primitives";

export function ToneIcon({ tone, className }: { tone: Tone; className?: string }) {
  const Icon = tone === "success" ? CircleCheck : tone === "info" ? Info : TriangleAlert;
  const color = { success: "text-success", info: "text-info", warning: "text-warning", fault: "text-warning" }[tone];
  return <Icon className={cn("size-[18px] shrink-0", color, className)} strokeWidth={1.75} aria-hidden />;
}

function Card({ tone, title, meta, children, unread, className, onDismiss, dismissLabel, ...rest }: {
  tone: Tone; title: string; meta?: string; children?: ReactNode; unread?: boolean; className?: string; onDismiss?: () => void; dismissLabel?: string;
} & Record<string, unknown>) {
  return (
    <div className={cn("notification grid gap-2 rounded-2xl bg-surface-2 p-4", `tone-${tone}`, unread && "unread ring-1 ring-primary/25", className)} {...rest}>
      <div className="notification-head flex items-start gap-2.5">
        <ToneIcon tone={tone} className="mt-px" />
        <h3 className="flex-1 text-[13.5px] leading-snug font-medium text-foreground">{unread && <span className="sr">Unread: </span>}{title}</h3>
        {onDismiss && (
          <button type="button" onClick={onDismiss} aria-label={dismissLabel || "Dismiss"} className="notification-dismiss -mt-1 -mr-1 grid size-7 place-items-center rounded-lg text-muted-foreground hover:bg-surface hover:text-foreground">
            <X className="size-3.5" />
          </button>
        )}
      </div>
      {meta && <p className="notification-meta text-[11.5px] text-muted-foreground">{meta}</p>}
      {children}
    </div>
  );
}

/** The same actions in the panel and in toasts; each one can change the state it reports. */
function NotificationActions({ item, onAct }: { item: Json; onAct?: () => void }) {
  const exists = useApp((s) => s.sources.some((source) => source.key === item.source_key));
  if (!exists) return null;
  const action = (label: string, name: string, variant: "primary" | "secondary" | "quiet") => (
    <Button key={name} variant={variant} className="h-9 px-4 text-[12.5px]" data-notification={item.id} data-action={name} onClick={() => { onAct?.(); void notificationAction(name, item); }}>
      {label}
    </Button>
  );
  const buttons: ReactNode[] = [];
  if (item.kind === "descriptions_ready") buttons.push(action("Generate descriptions", "generate", "primary"), action("Not now", "dismiss", "quiet"));
  else {
    if (item.remaining && ["cancelled", "stopped", "interrupted"].includes(item.outcome)) buttons.push(action("Continue", "generate", "primary"));
    buttons.push(["stopped", "interrupted", "complete_with_failures"].includes(item.outcome) ? action("View report", "report", "secondary") : action("View in Asset processing", "view", "secondary"));
  }
  return <div className="notification-actions mt-1 flex flex-wrap gap-2">{buttons}</div>;
}

function NotificationItem({ item }: { item: Json }) {  const content = notificationContent(item);
  const actions = <NotificationActions item={item} />;
  return (
    <li>
      <Card
        tone={content.tone}
        title={content.title}
        meta={[item.source_name, ago(item.created_utc)].filter(Boolean).join(" · ")}
        unread={!item.read}
        onDismiss={item.kind === "descriptions_report" ? () => void notificationAction("dismiss", item) : undefined}
        dismissLabel={`Dismiss: ${content.title}, ${item.source_name}`}
      >
        <p className="notification-body text-[12.5px] leading-relaxed text-muted-foreground">{content.body}</p>
        {actions}
      </Card>
    </li>
  );
}

function RunningItem({ source }: { source: Json }) {
  const operation = source.operation;
  const value = Math.round((operation.progress || 0) * 100);
  const phase = `${operation.phase || "Working"}${operation.total ? " · " + operation.completed + " / " + operation.total : ""}`;
  return (
    <div className="notification running grid gap-2 rounded-2xl bg-surface-2 p-4">
      <div className="notification-head flex items-center gap-2.5">
        <Spinner className="size-4 text-primary" />
        <h3 className="flex-1 text-[13.5px] font-medium">Generating descriptions</h3>
      </div>
      <p className="notification-meta text-[11.5px] text-muted-foreground">{source.name}</p>
      <Progress value={value} label={"Description progress for " + source.name} valueText={`${value}% — ${phase}`} />
      <p className="notification-body text-[12px] text-muted-foreground">{phase}</p>
      <div className="notification-actions flex gap-2">
        <Button variant="secondary" className="h-9 px-4 text-[12.5px]" data-notification={"running-" + source.key} data-action="cancel" disabled={operation.status === "cancelling"} onClick={() => void sourceAction("cancel", source.key)}>
          {operation.status === "cancelling" ? "Cancelling…" : "Cancel"}
        </Button>
        <Button variant="quiet" className="h-9 px-4 text-[12.5px]" onClick={() => void openProcessing(source.key)}>Open Asset processing</Button>
      </div>
    </div>
  );
}

export function NotificationsPanel() {
  const open = useApp((s) => s.notificationsOpen);
  const items = useApp((s) => s.notifications);
  const sources = useApp((s) => s.sources);
  const running = sources.filter(describeActive);
  const unread = items.filter((item) => !item.read).length;
  const panelRef = useRef<HTMLElement>(null);
  const reduce = useReducedMotion();
  useEffect(() => {
    if (!open) return;
    document.getElementById("notifications-title")?.focus();
    const onPointer = (event: PointerEvent) => {
      const target = event.target as Element;
      if (!panelRef.current?.contains(target) && !target.closest("[data-notifications-anchor]") && !target.closest("#toasts")) setNotificationsOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      event.stopImmediatePropagation();
      setNotificationsOpen(false);
      document.getElementById("open-notifications")?.focus();
    };
    window.addEventListener("pointerdown", onPointer);
    window.addEventListener("keydown", onKey, true);
    return () => {
      window.removeEventListener("pointerdown", onPointer);
      window.removeEventListener("keydown", onKey, true);
    };
  }, [open]);
  return (
    <AnimatePresence>
      {open && (
        <motion.section
          ref={panelRef}
          id="notifications-panel"
          role="dialog"
          aria-labelledby="notifications-title"
          initial={reduce ? { opacity: 0 } : { opacity: 0, y: -10, scale: 0.97 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={reduce ? { opacity: 0 } : { opacity: 0, y: -8, scale: 0.97, transition: { duration: 0.14 } }}
          transition={SPRING_PANEL}
          style={{ transformOrigin: "top right" }}
          className="fixed top-[72px] right-[60px] z-40 flex max-h-[min(78vh,760px)] w-[min(420px,calc(100vw-32px))] flex-col overflow-hidden rounded-[24px] border border-border bg-surface shadow-panel"
        >
          <div className="flex items-center justify-between px-6 pt-5 pb-3">
            <h2 id="notifications-title" tabIndex={-1} className="text-[15px] font-semibold outline-none">Notifications</h2>
            <div className="flex items-center gap-1">
              <button id="notifications-read-all" type="button" disabled={!unread} onClick={() => void saveNotification("read_all")} className="h-8 rounded-lg px-2.5 text-[12px] font-medium text-primary hover:bg-surface-2 disabled:text-subtle">
                Mark all read
              </button>
              <IconButton label="Close notifications" onClick={() => setNotificationsOpen(false)} className="size-9"><X className="size-4" /></IconButton>
            </div>
          </div>
          <div className="min-h-0 overflow-y-auto overscroll-contain px-4 pb-4 scroll-thin">
            <div id="notifications-running" aria-live="polite" className="grid gap-3">{running.map((source) => <RunningItem key={source.key} source={source} />)}</div>
            <ul id="notifications-list" aria-label="Notifications" className={cn("grid gap-3", running.length > 0 && "mt-3")}>
              {items.map((item) => <NotificationItem key={item.id + item.created_utc} item={item} />)}
            </ul>
            {!items.length && !running.length && <p id="notifications-empty" className="py-12 text-center text-[13px] text-muted-foreground">You’re all caught up.</p>}
          </div>
        </motion.section>
      )}
    </AnimatePresence>
  );
}

function ToastView({ toast }: { toast: Toast }) {
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const schedule = () => {
    clearTimeout(timer.current);
    timer.current = setTimeout(() => dismissToast(toast.id), 8000);
  };
  useEffect(() => {
    schedule();
    return () => clearTimeout(timer.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const item = toast.notification;
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 12, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, x: 24, transition: { duration: 0.15 } }}
      transition={SPRING_PANEL}
      className={cn("toast pointer-events-auto flex items-start gap-1 rounded-2xl border border-border bg-surface shadow-panel", `tone-${toast.tone}`)}
      onPointerEnter={() => clearTimeout(timer.current)}
      onPointerLeave={schedule}
      onFocus={() => clearTimeout(timer.current)}
      onBlur={(event) => !event.currentTarget.contains(event.relatedTarget) && schedule()}
    >
      <Card tone={toast.tone} title={toast.title} className="flex-1 bg-transparent">
        <p className="notification-body text-[12.5px] leading-relaxed text-muted-foreground">{toast.body}</p>
        {item && <NotificationActions item={item} onAct={() => dismissToast(toast.id)} />}
      </Card>
      <button type="button" aria-label="Close" onClick={() => dismissToast(toast.id)} className="notification-dismiss mt-3 mr-3 grid size-7 shrink-0 place-items-center rounded-lg text-muted-foreground hover:bg-surface-2">
        <X className="size-3.5" />
      </button>
    </motion.div>
  );
}

export function Toasts() {
  const toasts = useApp((s) => s.toasts);
  return (
    <div id="toasts" role="region" aria-label="New notifications" aria-live="polite" className="pointer-events-none fixed right-5 bottom-5 z-50 grid w-[min(400px,calc(100vw-32px))] gap-3">
      <AnimatePresence initial={false}>{toasts.map((toast) => <ToastView key={toast.id} toast={toast} />)}</AnimatePresence>
    </div>
  );
}

/** Recorded description run report (handoff "Run report"), opened from a notification. */
export function RunReport() {
  const report = useApp((s) => s.runReport);
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (report && !dialog.current?.open) dialog.current?.showModal();
    if (!report && dialog.current?.open) dialog.current.close();
  }, [report]);
  const content = report ? notificationContent(report) : null;
  const memory = /gpu memory|out of memory|cuda/i.test(report?.reason || "");
  const close = () => setState({ runReport: null });
  return (
    <dialog
      ref={dialog}
      aria-labelledby="run-report-title"
      onCancel={(event) => { event.preventDefault(); close(); }}
      className="m-auto w-[min(640px,calc(100vw-32px))] rounded-[28px] border border-border bg-surface p-0 text-foreground shadow-panel backdrop:bg-black/30"
    >
      {report && content && (
        <div className="grid gap-4 p-7">
          <div className="flex items-start gap-3">
            <ToneIcon tone={content.tone} className="mt-1 size-5" />
            <div className="flex-1">
              <h2 id="run-report-title" className="text-[19px] font-semibold">{content.title}</h2>
              <p className="mt-1.5 text-[12px] text-muted-foreground">{report.source_name} · Recorded run report{report.created_utc ? " · " + ago(report.created_utc) : ""}</p>
            </div>
            <IconButton label="Close report" onClick={close} className="size-9"><X className="size-4" /></IconButton>
          </div>
          {report.reason && (
            <div className={cn("rounded-2xl px-5 py-4", report.outcome === "complete_with_failures" ? "bg-surface-2" : "bg-warning-bg")}>
              <p className={cn("text-[14px] font-semibold", report.outcome === "complete_with_failures" ? "text-foreground" : "text-warning")}>{report.reason}</p>
              <p className="mt-1.5 text-[13px] text-foreground">The run stopped without marking pending assets as faulty.</p>
            </div>
          )}
          <p className="text-[13.5px] leading-relaxed">
            {plural(report.written || 0, "description was", "descriptions were")} saved and published.
            {report.failed ? ` ${plural(report.failed, "description failed and is", "descriptions failed and are")} recorded, not retried.` : ""}
            {report.remaining ? ` ${plural(report.remaining, "asset stays", "assets stay")} pending.` : ""}
          </p>
          {memory && <p className="text-[13px] text-muted-foreground">Before starting another run, lower Description batch size in Settings → General.</p>}
          <div className="flex justify-end">
            <Button variant="secondary" onClick={close}>Close report</Button>
          </div>
        </div>
      )}
    </dialog>
  );
}
