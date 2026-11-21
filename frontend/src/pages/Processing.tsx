import { ArrowDown, ArrowUp, Bot, ChevronRight, Copy, FileText, FolderOpen, Pause, Play, RotateCcw, Settings2, Undo2, X } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import type { Json } from "../app/api";
import { operationActive, plural } from "../app/format";
import { copyText, dismissAttention, loadQueue, navigate, openSources, queueControl, recheckFailures, restoreAttention, setAgentOpen, setAgentsPaused, showLog, sourceAction, useApp } from "../app/store";
import { Skeleton } from "../ui/Loading";
import { Reason } from "../ui/CommandBlock";
import { Badge, Banner, Button, Disclosure, Hint, Pressable } from "../ui/primitives";
import { OperationProgress } from "../ui/OperationProgress";
import { SearchCheckButton } from "../ui/Readiness";

const ACTION = { previews: "Make previews", descriptions: "Generate descriptions" } as Record<string, string>;
const OUTCOME: Record<string, [string, "success" | "warning" | "fault" | "neutral"]> = {
  complete: ["Done", "success"], complete_with_faults: ["Done · failures recorded", "warning"], cancelled: ["Cancelled", "neutral"],
  faulty: ["Stopped", "fault"], interrupted: ["Interrupted", "warning"], nothing_to_do: ["Nothing to do", "neutral"],
  stopped: ["Stopped · app closed", "fault"],
};

/** Who started a job, when an agent did (design principle P6), with the Bot sign (P2). */
function ByAgent({ item, held }: { item: Json; held?: boolean }) {
  if (item.by !== "agent") return null;
  return (
    <Hint content={held ? "Agents are paused: this waits until you turn them back on" : "Started by an agent"} focusable>
      <span className="agent-job inline-flex shrink-0 items-center gap-1 rounded-full bg-accent-soft px-2 py-0.5 text-[11px] text-accent-soft-foreground">
        <Bot className="size-3" aria-hidden />{item.agent || "Agent"}{held ? " · held" : ""}
      </span>
    </Hint>
  );
}

function Section({ id, title, count, actions, children, hint }: { id: string; title: string; count?: number; actions?: ReactNode; children: ReactNode; hint?: ReactNode }) {
  return (
    <section aria-labelledby={id + "-title"} id={id} className="grid gap-3 rounded-[22px] border border-border bg-surface p-6">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <h2 id={id + "-title"} className="text-[16px] font-semibold">{title}</h2>
        {count !== undefined && <span className="text-[12.5px] text-muted-foreground tabular-nums">{count.toLocaleString()}</span>}
        <div className="ml-auto flex flex-wrap items-center gap-2">{actions}</div>
      </div>
      {hint && <p className="text-[12px] leading-relaxed text-muted-foreground">{hint}</p>}
      {children}
    </section>
  );
}

function since(utc?: string) {
  if (!utc) return "";
  const seconds = Math.max(0, (Date.now() - Date.parse(utc)) / 1000);
  return seconds < 90 ? `${Math.round(seconds)} s` : seconds < 5400 ? `${Math.round(seconds / 60)} min` : `${(seconds / 3600).toFixed(1)} h`;
}
const ago = (utc?: string) => (utc ? since(utc) + " ago" : "");

/** One step of the Now and next timeline: a filled dot for what runs, a hollow one for what waits. */
function Step({ running, children, className, ...props }: { running?: boolean; children: ReactNode; className?: string } & Record<string, unknown>) {
  return (
    <div className={cn("timeline-step relative grid gap-2 pl-8", className)} {...props}>
      <span aria-hidden className={cn("absolute top-[3px] left-0 size-[15px] rounded-full ring-4 ring-surface",
        running ? "timeline-pulse bg-primary" : "border-2 border-border-strong bg-surface")} />
      {children}
    </div>
  );
}

function Pending() {
  const pending = useApp((s) => s.pending);
  const counts = [pending?.previews && plural(pending.previews, "asset has no previews yet", "assets have no previews yet"),
    pending?.descriptions && plural(pending.descriptions, "asset has no description yet", "assets have no description yet")].filter(Boolean);
  return (
    <div id="nothing-running" className="grid justify-items-start gap-2 text-[13px] text-muted-foreground">
      <p>Nothing is running or waiting.{counts.length ? ` ${counts.join(" and ")}.` : ""}</p>
      <Button variant="secondary" className="h-8 px-3" tooltip="Opens Asset sources, where Make previews and Generate descriptions start work here" onClick={() => openSources()}>
        <FolderOpen className="size-3.5" aria-hidden />Asset sources
      </Button>
    </div>
  );
}

function RunningItem({ item }: { item: Json }) {
  const operation = item.operation || {};
  return (
    <Step running id="running-item">
      <div className="flex flex-wrap items-center gap-2">
        <p className="mr-auto text-[13.5px] font-medium">{item.title || ACTION[item.action]} · {item.label}{item.resolved ? ` · ${plural(item.resolved, "asset", "assets")}` : ""}</p>
        <ByAgent item={item} />
        <span className="text-[12px] text-muted-foreground">{since(item.started_utc)}</span>
        <Button variant="secondary" className="h-8 px-3" disabled={item.status === "cancelling"} disabledReason="Already stopping" tooltip="Stops this work. Assets already finished keep their results" onClick={() => void queueControl("remove", item.id)}>
          <X className="size-3.5" aria-hidden />{item.status === "cancelling" ? "Stopping…" : "Cancel"}
        </Button>
      </div>
      <OperationProgress operation={operation} label={(item.title || ACTION[item.action]) + " for " + item.label} />
      <Reason text={operation.reason || operation.phase || "Starting"} className="text-[12px] text-muted-foreground" />
      {(item.log || []).length > 0 && (
        <Disclosure title="Live log">
          <ul id="running-log" className="grid max-h-64 gap-0.5 overflow-y-auto rounded-xl bg-surface-2 p-2 font-mono text-[11.5px] scroll-thin">
            {item.log.map((line: Json, index: number) => (
              <li key={index} className={cn("flex items-start gap-2 rounded px-1.5 py-1", line.level === "error" ? "text-fault" : line.level === "warning" ? "text-warning" : "text-muted-foreground")}>
                <span className="min-w-0 flex-1 break-all select-text">{line.text}</span>
                {line.level !== "info" && (
                  <Pressable aria-label="Copy this line" tooltip="Copies this log line" className="shrink-0 rounded p-0.5 hover:bg-surface" onClick={() => void copyText(line.text, "The log line is on the clipboard.")}><Copy className="size-3.5" /></Pressable>
                )}
              </li>
            ))}
          </ul>
        </Disclosure>
      )}
    </Step>
  );
}

/** Now and next: Running and Up next as one timeline; Pause and Resume sit in its header. */
function NowAndNext() {
  const queue = useApp((s) => s.queue);
  const sources = useApp((s) => s.sources);
  const globalScan = useApp((s) => s.globalScan);
  const reduce = useReducedMotion();
  const item = queue?.running;
  const items: Json[] = queue?.up_next || [];
  const scans = sources.filter((s: Json) => operationActive(s.operation) && s.operation?.token !== item?.token);
  if (operationActive(globalScan)) scans.unshift({ key: "", name: "All library folders", operation: globalScan });
  const empty = !item && !scans.length && !items.length;
  const actions = queue?.paused ? (
    <Button id="resume-queue" className="h-8 px-3" tooltip="Starts the waiting work again, in this order" onClick={() => void queueControl("resume")}><Play className="size-3.5" aria-hidden />{queue.stopped_on_close ? "Continue" : "Resume"}</Button>
  ) : items.length > 0 && (
    <Button variant="quiet" className="h-8 px-3" tooltip="Nothing waiting starts until you resume; what is running now carries on" onClick={() => void queueControl("pause")}><Pause className="size-3.5" aria-hidden />Pause</Button>
  );
  return (
    <Section id="now-next" title="Now and next" count={items.length + (item ? 1 : 0) || undefined} actions={actions}>
      {queue?.paused && <Banner tone="info"><span id="queue-paused">{queue.stopped_on_close
        ? "Stopped when you closed Assetarium. Finished assets are kept; Continue picks up the rest."
        : "Paused. Nothing here starts until you resume."}</span></Banner>}
      {queue?.agents_paused && items.some((i) => i.by === "agent") && (
        <Banner tone="info"><span id="agent-jobs-held" className="flex flex-wrap items-center gap-2">
          <span className="mr-auto">Agents are paused, so jobs they queued wait; yours run first.</span>
          <Button variant="quiet" className="h-7 px-2" tooltip="Opens what the agent did, with Pause agents and Undo all" onClick={() => setAgentOpen(true)}>Agent activity</Button>
          <Button variant="secondary" className="h-7 px-2" tooltip="Lets agents change things again and starts the jobs they queued" onClick={() => void setAgentsPaused(false)}>Turn agents back on</Button>
        </span></Banner>
      )}
      {empty ? <Pending /> : (
        <div id="timeline" className="relative grid gap-4">
          <span aria-hidden className="absolute top-3 bottom-3 left-[7px] w-px bg-border" />
          {item && <RunningItem item={item} />}
          {scans.map((s: Json) => (
            <Step running key={s.key} className="gap-1.5">
              <p className="text-[13px]">{s.operation.operation === "scan" ? "Scanning" : "Working on"} {s.name}</p>
              <OperationProgress operation={s.operation} label={"Scanning " + s.name} />
              <div className="flex items-center gap-2">
                <p className="mr-auto text-[12px] text-muted-foreground">{s.operation.phase}</p>
                <Button variant="quiet" className="h-7 px-2" tooltip="Stops this scan; what it found so far is kept" onClick={() => void sourceAction("cancel", s.key)}>Cancel</Button>
              </div>
            </Step>
          ))}
          {items.length > 0 && (
            <ol id="up-next" className="grid gap-1.5" aria-label="Up next">
              <AnimatePresence initial={false}>
                {items.map((waiting, index) => (
                  <motion.li key={waiting.id} layout={!reduce} initial={reduce ? false : { opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} data-action={waiting.action}>
                    <Step className="gap-0">
                      <div className="-mt-1.5 -ml-3 flex items-center gap-2 rounded-xl px-3 py-1.5 text-[13px] hover:bg-surface-2">
                        <span className="mr-auto min-w-0 truncate">{waiting.title || ACTION[waiting.action]} · {waiting.label}</span>
                        <ByAgent item={waiting} held={!!queue?.agents_paused} />
                        {waiting.estimate?.seconds && <span className="text-[11.5px] text-muted-foreground tabular-nums">~{Math.round(waiting.estimate.seconds[1] / 60)} min</span>}
                        <Pressable aria-label="Move up" tooltip="Runs this one step earlier" disabled={index === 0} className="rounded p-1 hover:bg-surface disabled:opacity-30" onClick={() => void queueControl("move", waiting.id, Math.max(0, index - 1))}><ArrowUp className="size-3.5" /></Pressable>
                        <Pressable aria-label="Move down" tooltip="Runs this one step later" disabled={index === items.length - 1} className="rounded p-1 hover:bg-surface disabled:opacity-30" onClick={() => void queueControl("move", waiting.id, index + 1)}><ArrowDown className="size-3.5" /></Pressable>
                        <Pressable aria-label={"Remove " + waiting.label} tooltip="Takes this out of the queue before it starts" className="rounded p-1 hover:bg-surface" onClick={() => void queueControl("remove", waiting.id)}><X className="size-3.5" /></Pressable>
                      </div>
                    </Step>
                  </motion.li>
                ))}
              </AnimatePresence>
            </ol>
          )}
          {!items.length && <p className="pl-8 text-[12px] text-muted-foreground">Nothing waiting. Previews always run before descriptions.</p>}
        </div>
      )}
    </Section>
  );
}

const SETTINGS = <Button variant="quiet" className="h-7 px-2" tooltip="Opens Settings, where this is fixed" onClick={() => navigate({ page: "settings" })}><Settings2 className="size-3.5" aria-hidden />Open Settings</Button>;

/** What a notice says happened, where and how many (never an invented cause). */
function Headline({ card }: { card: Json }) {
  if (card.kind === "blocked") return <span className="font-medium">{card.reason}{card.count ? ` · fixing it unblocks ${plural(card.count, "asset", "assets")}` : ""}</span>;
  if (card.kind === "run") return <span className="font-medium">{card.title || ACTION[card.action]} · {card.label} stopped</span>;
  return (
    <span className="flex min-w-0 flex-wrap items-center gap-2">
      <Hint content="The step that failed"><span className="inline-flex"><Badge tone="fault">{card.stage}</Badge></span></Hint>
      {card.no_reason ? <span className="no-reason">No reason was recorded for {card.count === 1 ? "this asset" : `these ${card.count.toLocaleString()} assets`}</span> : <Reason text={card.reason} />}
    </span>
  );
}

function AttentionCard({ card }: { card: Json }) {
  const reduce = useReducedMotion();
  const has = (action: string) => card.actions.includes(action);
  return (
    <motion.li layout={!reduce} initial={reduce ? false : { opacity: 0, y: 6 }} animate={{ opacity: card.dismissed ? 0.6 : 1, y: 0 }} exit={reduce ? { opacity: 0 } : { opacity: 0, x: 24 }}
      className={cn("attention-card grid gap-2 rounded-xl px-4 py-3 text-[13px]", card.kind === "blocked" ? "bg-warning-bg" : "bg-surface-2")}
      data-kind={card.kind} data-id={card.id} data-again={card.again ? "true" : "false"} data-dismissed={card.dismissed ? "true" : "false"}>
      <div className="flex items-start gap-2">
        <div className={cn("grid min-w-0 flex-1 gap-1", card.kind === "blocked" && "text-warning")}>
          <div className="flex flex-wrap items-center gap-2">
            <Headline card={card} />
            {card.again && <Hint content="You dismissed this earlier; the same fault happened again" focusable><span className="attention-again inline-flex"><Badge tone="warning">Again</Badge></span></Hint>}
          </div>
          {card.kind === "failure" && <span className="text-[12px] text-muted-foreground">{plural(card.count, "asset", "assets")} · {card.folder}</span>}
          {card.kind === "blocked" && <Reason text={card.fix} className="text-[12.5px]" />}
          {card.kind === "run" && <Reason text={card.reason} className="text-[12px] text-muted-foreground" />}
        </div>
        {card.dismissed ? (
          <Button variant="quiet" className="attention-restore h-7 shrink-0 px-2" tooltip="Shows this notice again" onClick={() => void restoreAttention([card.id])}><Undo2 className="size-3.5" aria-hidden />Bring back</Button>
        ) : (
          <Pressable aria-label="Dismiss" tooltip="Hides this notice. Nothing is deleted; it comes back if the same fault happens again" className="attention-dismiss shrink-0 rounded p-1 text-muted-foreground hover:bg-surface hover:text-foreground" onClick={() => void dismissAttention([card.id])}><X className="size-4" /></Pressable>
        )}
      </div>
      {!card.dismissed && (
        <div className="flex flex-wrap items-center gap-2">
          {has("run_check") && <SearchCheckButton onReady={() => void loadQueue()} />}
          {has("settings") && SETTINGS}
          {has("recheck") && <Button variant="quiet" className="h-7 px-2" data-action="recheck" tooltip="Checks which of these failures came from a file problem that is fixed now, and asks before retrying them" onClick={() => void recheckFailures({ key: card.key, name: card.folder })}><RotateCcw className="size-3.5" aria-hidden />Recheck…</Button>}
          {has("library") && <Button variant="quiet" className="h-7 px-2" data-action="library" tooltip="Opens the Library at the first failed asset" onClick={() => openSources(card.key, "", card.files[0]?.asset_id)}><FolderOpen className="size-3.5" aria-hidden />Show in Library</Button>}
          {has("log") && <Button variant="quiet" className="h-7 px-2" data-action="log" tooltip="Opens the full log this work wrote" onClick={() => void showLog(card.log)}><FileText className="size-3.5" aria-hidden />Show log</Button>}
          {has("copy") && <Button variant="quiet" className="h-7 px-2" data-action="copy" tooltip="Copies the failure and the paths of its files" onClick={() => void copyText(`${card.stage}: ${card.reason}\n` + card.files.map((a: Json) => a.path || a.name).join("\n"), "The failure and its files are on the clipboard.")}><Copy className="size-3.5" aria-hidden />Copy</Button>}
        </div>
      )}
    </motion.li>
  );
}

/** Needs your attention (design principle P7): only what the owner can resolve; each notice can be dismissed. */
function Attention() {
  const cards: Json[] = useApp((s) => s.queue?.attention) || [];
  const [showDismissed, setShowDismissed] = useState(false);
  const shown = cards.filter((c) => !c.dismissed);
  const dismissed = cards.filter((c) => c.dismissed);
  useEffect(() => { if (!dismissed.length) setShowDismissed(false); }, [dismissed.length]);
  const actions = (
    <>
      {dismissed.length > 0 && (
        <Pressable id="attention-show-dismissed" aria-expanded={showDismissed} tooltip={showDismissed ? "Hides the notices you dismissed" : "Lists the notices you dismissed, each with Bring back"}
          className="text-[12px] text-muted-foreground hover:text-foreground hover:underline" onClick={() => setShowDismissed(!showDismissed)}>
          {dismissed.length.toLocaleString()} dismissed · {showDismissed ? "Hide" : "Show"}
        </Pressable>
      )}
      {shown.length > 1 && <Button id="attention-dismiss-all" variant="quiet" className="h-7 px-2" tooltip="Hides every notice here; Undo brings them back, and each returns if its fault happens again" onClick={() => void dismissAttention(shown.map((c) => c.id), true)}>Dismiss all</Button>}
    </>
  );
  const list = showDismissed ? [...shown, ...dismissed] : shown;
  return (
    <Section id="attention" title="Needs your attention" count={shown.length} actions={actions}
      hint="Work that can’t run yet and failures that were recorded, each with what resolves it. Dismissing hides a notice; the failure stays recorded and is never retried automatically.">
      {!list.length ? <p id="attention-empty" className="text-[13px] text-muted-foreground">Nothing needs your attention.</p> : (
        <ul id="attention-list" className="grid gap-2">
          <AnimatePresence initial={false}>
            {list.map((card) => <AttentionCard key={card.id} card={card} />)}
          </AnimatePresence>
        </ul>
      )}
    </Section>
  );
}

/** Design principle P1: back-to-back runs that ended the same way (same work, outcome and reason) are one line. */
function grouped(recent: Json[]) {
  const runs: { item: Json; count: number }[] = [];
  for (const item of recent) {
    const last = runs[runs.length - 1];
    if (last && ["action", "label", "status", "reason"].every((k) => last.item[k] === item[k])) last.count += 1;
    else runs.push({ item, count: 1 });
  }
  return runs;
}

/** Recent activity: history only, folded into one summary line until opened (click, Enter, or scrolling past the end). */
function RecentActivity({ open, onOpen }: { open: boolean; onOpen: (open: boolean) => void }) {
  const recent: Json[] = useApp((s) => s.queue?.recent) || [];
  const runs = grouped(recent);
  const last = runs[0]?.item;
  const [label, tone] = (last && OUTCOME[last.status]) || [last?.status || "", "neutral" as const];
  return (
    <details id="recent-activity" open={open} onToggle={(event) => onOpen((event.currentTarget as HTMLDetailsElement).open)}
      className="recent-activity group rounded-[22px] border border-border bg-surface">
      <summary data-no-tooltip="" className="flex cursor-pointer list-none flex-wrap items-center gap-x-3 gap-y-1 rounded-[22px] p-6 outline-none focus-visible:ring-2 focus-visible:ring-primary/45">
        <ChevronRight className="recent-chevron size-4 text-muted-foreground" aria-hidden />
        <h2 className="text-[16px] font-semibold">Recent activity</h2>
        {last ? (
          <span id="recent-summary" className="flex min-w-0 flex-1 flex-wrap items-center gap-2 text-[12.5px] text-muted-foreground">
            <Badge tone={tone}>{label}</Badge>
            <span className="min-w-0 truncate">{last.title || ACTION[last.action]} · {last.label}</span>
            <span>{ago(last.finished_utc)}</span>
            {runs.length > 1 && <span className="tabular-nums">· {(runs.length - 1).toLocaleString()} more</span>}
          </span>
        ) : <span id="recent-summary" className="text-[12.5px] text-muted-foreground">Finished work appears here.</span>}
      </summary>
      {runs.length > 0 && (
        <div className="recent-scroll mx-3 mb-4 max-h-[420px] overflow-y-auto overscroll-contain px-3 scroll-thin">
          <ul id="recent-items" className="grid gap-1.5 py-1">
            {runs.map(({ item, count }) => {
              const [itemLabel, itemTone] = OUTCOME[item.status] || [item.status, "neutral"];
              const seconds = item.started_utc && item.finished_utc ? (Date.parse(item.finished_utc) - Date.parse(item.started_utc)) / 1000 : null;
              return (
                <li key={item.id + item.finished_utc} className="flex flex-wrap items-center gap-2 rounded-xl px-3 py-2 text-[13px] hover:bg-surface-2">
                  <Badge tone={itemTone}>{itemLabel}</Badge>
                  <span className="mr-auto min-w-0 truncate">{item.title || ACTION[item.action]} · {item.label}{item.resolved ? ` · ${plural(item.resolved, "asset", "assets")}` : ""}</span>
                  {count > 1 && <Hint content="The same work ended the same way several times in a row" focusable><span className="recent-repeat text-[11.5px] text-muted-foreground tabular-nums">× {count}</span></Hint>}
                  {seconds !== null && <span className="text-[11.5px] text-muted-foreground tabular-nums">{seconds < 90 ? Math.round(seconds) + " s" : Math.round(seconds / 60) + " min"}</span>}
                  {item.log && <Button variant="quiet" className="h-7 px-2" tooltip="Opens the full log this work wrote" onClick={() => void showLog(item.log)}><FileText className="size-3.5" aria-hidden />Show log</Button>}
                  {item.reason && <Reason text={item.reason} className="w-full text-[12px] text-muted-foreground" />}
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </details>
  );
}

const PAST_END = new Set(["ArrowDown", "PageDown", "End", " "]);

export function Processing({ focus: _focus }: { focus?: string }) {
  const queue = useApp((s) => s.queue);
  const view = useRef<HTMLDivElement>(null);
  const [recentOpen, setRecentOpen] = useState(false);  // Closed again whenever the owner leaves the page.
  useEffect(() => {
    void loadQueue();
    const timer = setInterval(() => void loadQueue(), 2500);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    // Scrolling on past the end of the page opens Recent activity; it never closes on the way back up (content
    // would move under the cursor). A window tall enough not to scroll counts as being at the end.
    const scroller = view.current;
    if (!scroller) return;
    const atEnd = () => scroller.scrollTop + scroller.clientHeight >= scroller.scrollHeight - 2;
    const onWheel = (event: WheelEvent) => { if (event.deltaY > 0 && atEnd()) setRecentOpen(true); };
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement;
      if (PAST_END.has(event.key) && atEnd() && !target.closest("input, textarea, select, button, summary, [role=slider]")) setRecentOpen(true);
    };
    scroller.addEventListener("wheel", onWheel, { passive: true });
    scroller.addEventListener("keydown", onKey);
    return () => { scroller.removeEventListener("wheel", onWheel); scroller.removeEventListener("keydown", onKey); };
  }, []);
  return (
    <div id="processing-view" ref={view} className="h-full overflow-y-auto overscroll-contain px-8 pb-12 scroll-thin">
      <div className="grid max-w-[1120px] gap-6">
        <div>
          <h1 className="text-[26px] font-semibold text-foreground">Asset processing</h1>
          <p className="mt-2 max-w-[640px] text-[13.5px] leading-relaxed text-muted-foreground">What runs now, what waits and what needs you. Nothing starts until you ask; scans never run models.</p>
        </div>
        {!queue ? <Skeleton className="h-40 w-full rounded-[22px]" /> : (
          <>
            <NowAndNext />
            <Attention />
            <RecentActivity open={recentOpen} onOpen={setRecentOpen} />
          </>
        )}
      </div>
    </div>
  );
}
