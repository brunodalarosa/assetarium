import { Check, ChevronRight } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useMemo, useRef, useState } from "react";
import { useDismiss } from "@/lib/hooks/use-dismiss";
import { SPRING_LAYOUT, SPRING_PANEL, SPRING_SWAP } from "@/lib/ease";
import { cn } from "@/lib/utils";
import { type Activity, activities, navigate, useApp } from "../app/store";
import { useShownWhile } from "./Loading";

/** An orbiting comet around a breathing core; static under reduced motion. */
function ActivityMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" aria-hidden className={cn("size-[18px] shrink-0 text-primary", className)}>
      <defs>
        <linearGradient id="activity-tail" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="currentColor" stopOpacity="0" />
          <stop offset="1" stopColor="currentColor" />
        </linearGradient>
      </defs>
      <circle cx="10" cy="10" r="7.5" fill="none" stroke="currentColor" strokeOpacity="0.15" strokeWidth="2" />
      <g className="activity-orbit">
        <path d="M10 2.5a7.5 7.5 0 0 1 7.5 7.5" fill="none" stroke="url(#activity-tail)" strokeWidth="2" strokeLinecap="round" />
        <circle cx="17.5" cy="10" r="1.6" fill="currentColor" />
      </g>
      <circle className="activity-core" cx="10" cy="10" r="2.6" fill="currentColor" />
    </svg>
  );
}

const amount = (item: Activity, previews: number) =>
  item.progress !== undefined ? `${Math.round(item.progress * 100)}%` : item.id === "previews" ? previews.toLocaleString() : "";

function ActivityRow({ item, previews, done, onOpen }: { item: Activity; previews: number; done: boolean; onOpen: (source: string) => void }) {
  const body = (
    <>
      <span className="flex items-baseline gap-2">
        <span className="min-w-0 flex-1 truncate text-[13px] font-medium text-foreground">{item.detail}</span>
        <span className="shrink-0 text-[11.5px] text-muted-foreground tabular-nums">{done ? "Done" : amount(item, previews)}</span>
        {item.source && <ChevronRight className="size-3.5 shrink-0 self-center text-subtle transition-transform group-hover:translate-x-0.5" aria-hidden />}
      </span>
      <span className="relative mt-2 block h-1 overflow-hidden rounded-full bg-surface-2">
        {done ? (
          <motion.span className="absolute inset-y-0 left-0 rounded-full bg-success" initial={{ width: item.progress !== undefined ? `${item.progress * 100}%` : "30%" }} animate={{ width: "100%" }} transition={{ type: "spring", stiffness: 160, damping: 26 }} />
        ) : item.progress !== undefined ? (
          <motion.span className="absolute inset-y-0 left-0 rounded-full bg-primary" initial={false} animate={{ width: `${Math.max(3, item.progress * 100)}%` }} transition={{ type: "spring", stiffness: 160, damping: 26 }} />
        ) : (
          <span className="activity-sweep absolute inset-y-0 w-1/3 rounded-full bg-primary/70" />
        )}
      </span>
    </>
  );
  return item.source ? (
    <li>
      <button type="button" data-activity={item.id} onClick={() => onOpen(item.source!)} className="group block w-full rounded-xl px-3 py-2.5 text-left outline-none hover:bg-surface-2 focus-visible:bg-surface-2">
        {body}
      </button>
    </li>
  ) : (
    <li data-activity={item.id} className="px-3 py-2.5">{body}</li>
  );
}

/**
 * The top bar's quiet signal that something runs in the background: it appears only while work
 * runs, names the main task, and opens a short list; source work leads to Asset processing.
 */
export function ActivityIndicator() {
  const ready = useApp((s) => s.ready);
  const sources = useApp((s) => s.sources);
  const worker = useApp((s) => s.worker);
  const previews = useApp((s) => s.previews);
  const list = useMemo(() => activities(ready, sources, worker, previews), [ready, sources, worker, previews]);
  // Short bursts (a few thumbnails) stay silent; once shown, the mark lingers long enough to read.
  const shown = useShownWhile(list.length > 0, 450, 1200);
  const last = useRef<Activity[]>(list);
  if (list.length) last.current = list;
  const items = list.length ? list : last.current;
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();
  useDismiss(open && shown, () => setOpen(false), root);
  const primary = items[0];
  const done = !list.length;
  const summary = done ? "Background work finished" : list.map((item) => item.detail).join(" · ");
  return (
    <div ref={root} className="relative">
      <AnimatePresence>
        {shown && primary && (
          <motion.button
            key="activity"
            type="button"
            id="activity"
            layout
            aria-haspopup="dialog"
            aria-expanded={open}
            aria-controls="activity-panel"
            aria-label={`Background activity: ${summary}`}
            onClick={() => setOpen(!open)}
            initial={reduce ? { opacity: 0 } : { opacity: 0, scale: 0.85, filter: "blur(4px)" }}
            animate={{ opacity: 1, scale: 1, filter: "blur(0px)" }}
            exit={reduce ? { opacity: 0 } : { opacity: 0, scale: 0.85, filter: "blur(4px)", transition: { duration: 0.2 } }}
            transition={SPRING_LAYOUT}
            className={cn(
              "flex h-9 items-center gap-2 overflow-hidden rounded-full border pr-3.5 pl-2 text-[12.5px] whitespace-nowrap transition-colors",
              open ? "border-primary/30 bg-accent-soft text-accent-soft-foreground" : "border-border bg-surface/70 text-muted-foreground hover:bg-surface hover:text-foreground",
            )}
          >
            <motion.span layout="position" className="grid size-[18px] place-items-center">
              <AnimatePresence mode="popLayout" initial={false}>
                {done ? (
                  <motion.span key="done" initial={{ scale: 0.4, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ type: "spring", stiffness: 520, damping: 22 }} className="grid size-[18px] place-items-center rounded-full bg-success text-white dark:text-background">
                    <Check className="size-3" strokeWidth={3} />
                  </motion.span>
                ) : (
                  <motion.span key="busy" exit={{ scale: 0.4, opacity: 0 }}><ActivityMark /></motion.span>
                )}
              </AnimatePresence>
            </motion.span>
            <motion.span layout="position" className="relative grid">
              <AnimatePresence mode="popLayout" initial={false}>
                <motion.span
                  key={primary.label}
                  initial={reduce ? { opacity: 0 } : { opacity: 0, y: 10, filter: "blur(3px)" }}
                  animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
                  exit={reduce ? { opacity: 0 } : { opacity: 0, y: -10, filter: "blur(3px)" }}
                  transition={SPRING_SWAP}
                  className="font-medium"
                >
                  {primary.label}
                </motion.span>
              </AnimatePresence>
            </motion.span>
            {!done && amount(primary, previews) && <motion.span layout="position" className="tabular-nums text-subtle">{amount(primary, previews)}</motion.span>}
            {items.length > 1 && (
              <motion.span layout="position" className="rounded-full bg-primary/12 px-1.5 text-[11px] leading-[18px] font-semibold text-primary tabular-nums">+{items.length - 1}</motion.span>
            )}
          </motion.button>
        )}
      </AnimatePresence>
      <AnimatePresence>
        {open && shown && (
          <motion.section
            id="activity-panel"
            role="dialog"
            aria-labelledby="activity-title"
            initial={reduce ? { opacity: 0 } : { opacity: 0, y: -8, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={reduce ? { opacity: 0 } : { opacity: 0, y: -6, scale: 0.97, transition: { duration: 0.14 } }}
            transition={SPRING_PANEL}
            style={{ transformOrigin: "top right" }}
            className="absolute top-full right-0 z-40 mt-2 w-[min(340px,calc(100vw-32px))] rounded-[20px] border border-border bg-surface p-2 shadow-panel"
          >
            <h2 id="activity-title" className="px-3 pt-2 pb-1 text-[12px] font-medium tracking-wide text-muted-foreground uppercase">{done ? "Finished" : "Running now"}</h2>
            <ul aria-live="polite" className="grid grid-cols-[minmax(0,1fr)]">
              {items.map((item) => (
                <ActivityRow key={item.id} item={item} previews={previews} done={done} onOpen={(source) => { setOpen(false); navigate({ page: "processing", focus: source }); }} />
              ))}
            </ul>
          </motion.section>
        )}
      </AnimatePresence>
    </div>
  );
}
