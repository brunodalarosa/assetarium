import { ArrowDown, ArrowUp, Bot, Copy, FileText, FolderOpen, Pause, Play, RotateCcw, X } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { type ReactNode, useEffect } from "react";
import { cn } from "@/lib/utils";
import type { Json } from "../app/api";
import { operationActive, plural } from "../app/format";
import { copyText, loadQueue, navigate, openSources, queueControl, recheckFailures, refreshContext, setAgentOpen, setAgentsPaused, showLog, sourceAction, useApp } from "../app/store";
import { Skeleton } from "../ui/Loading";
import { Reason } from "../ui/CommandBlock";
import { Badge, Banner, Button, Disclosure, Hint, Pressable } from "../ui/primitives";
import { OperationProgress } from "../ui/OperationProgress";

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

function Section({ id, title, count, children, hint }: { id: string; title: string; count?: number; children: ReactNode; hint?: ReactNode }) {
  return (
    <section aria-labelledby={id + "-title"} id={id} className="grid gap-3 rounded-[22px] border border-border bg-surface p-6">
      <div className="flex items-baseline gap-2">
        <h2 id={id + "-title"} className="text-[16px] font-semibold">{title}</h2>
        {count !== undefined && <span className="text-[12.5px] text-muted-foreground tabular-nums">{count.toLocaleString()}</span>}
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

function Running() {
  const queue = useApp((s) => s.queue);
  const sources = useApp((s) => s.sources);
  const globalScan = useApp((s) => s.globalScan);
  const item = queue?.running;
  const scans = sources.filter((s: Json) => operationActive(s.operation) && s.operation?.token !== item?.token);
  if (operationActive(globalScan)) scans.unshift({ key: "", name: "All library folders", operation: globalScan });
  if (!item && !scans.length) return <p id="nothing-running" className="text-[13px] text-muted-foreground">Nothing is running. Make previews or Generate descriptions on the Asset sources tab; they start here.</p>;
  const operation = item?.operation || {};
  const phase = operation.phase || "Starting";
  return (
    <div className="grid gap-4">
      {item && (
        <div id="running-item" className="grid gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <p className="mr-auto text-[13.5px] font-medium">{item.title || ACTION[item.action]} · {item.label}{item.resolved ? ` · ${plural(item.resolved, "asset", "assets")}` : ""}</p>
            <ByAgent item={item} />
            <span className="text-[12px] text-muted-foreground">{since(item.started_utc)}</span>
            <Button variant="secondary" className="h-8 px-3" disabled={item.status === "cancelling"} tooltip="Stops this work. Assets already finished keep their results" onClick={() => void queueControl("remove", item.id)}>
              <X className="size-3.5" aria-hidden />{item.status === "cancelling" ? "Stopping…" : "Cancel"}
            </Button>
          </div>
          <OperationProgress operation={operation} label={(item.title || ACTION[item.action]) + " for " + item.label} />
          <Reason text={operation.reason || phase} className="text-[12px] text-muted-foreground" />
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
        </div>
      )}
      {scans.map((s: Json) => (
        <div key={s.key} className="grid gap-1.5">
          <p className="text-[13px]">{s.operation.operation === "scan" ? "Scanning" : "Working on"} {s.name}</p>
          <OperationProgress operation={s.operation} label={"Scanning " + s.name} />
          <div className="flex items-center gap-2">
            <p className="mr-auto text-[12px] text-muted-foreground">{s.operation.phase}</p>
            <Button variant="quiet" className="h-7 px-2" tooltip="Stops this scan; what it found so far is kept" onClick={() => void sourceAction("cancel", s.key)}>Cancel</Button>
          </div>
        </div>
      ))}
    </div>
  );
}

function UpNext() {
  const queue = useApp((s) => s.queue);
  const reduce = useReducedMotion();
  const items: Json[] = queue?.up_next || [];
  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-center gap-4">
        {queue?.paused ? (
          <Button id="resume-queue" className="h-8 px-3" tooltip="Starts the waiting work again, in this order" onClick={() => void queueControl("resume")}><Play className="size-3.5" aria-hidden />{queue.stopped_on_close ? "Continue" : "Resume"}</Button>
        ) : items.length > 0 && (
          <Button variant="quiet" className="h-8 px-3" tooltip="Nothing waiting starts until you resume; what is running now carries on" onClick={() => void queueControl("pause")}><Pause className="size-3.5" aria-hidden />Pause</Button>
        )}
      </div>
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
      {!items.length ? <p className="text-[13px] text-muted-foreground">Nothing waiting. Previews always run before descriptions.</p> : (
        <ol id="up-next" className="grid gap-1.5">
          <AnimatePresence initial={false}>
            {items.map((item, index) => (
              <motion.li key={item.id} layout={!reduce} initial={reduce ? false : { opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                className="flex items-center gap-2 rounded-xl bg-surface-2 px-3 py-2 text-[13px]" data-action={item.action}>
                <span className="mr-auto min-w-0 truncate">{item.title || ACTION[item.action]} · {item.label}</span>
                <ByAgent item={item} held={!!queue?.agents_paused} />
                {item.estimate?.seconds && <span className="text-[11.5px] text-muted-foreground tabular-nums">~{Math.round(item.estimate.seconds[1] / 60)} min</span>}
                <Pressable aria-label="Move up" tooltip="Runs this one step earlier" disabled={index === 0} className="rounded p-1 hover:bg-surface disabled:opacity-30" onClick={() => void queueControl("move", item.id, Math.max(0, index - 1))}><ArrowUp className="size-3.5" /></Pressable>
                <Pressable aria-label="Move down" tooltip="Runs this one step later" disabled={index === items.length - 1} className="rounded p-1 hover:bg-surface disabled:opacity-30" onClick={() => void queueControl("move", item.id, index + 1)}><ArrowDown className="size-3.5" /></Pressable>
                <Pressable aria-label={"Remove " + item.label} tooltip="Takes this out of the queue before it starts" className="rounded p-1 hover:bg-surface" onClick={() => void queueControl("remove", item.id)}><X className="size-3.5" /></Pressable>
              </motion.li>
            ))}
          </AnimatePresence>
        </ol>
      )}
    </div>
  );
}

function Blocked() {
  const blocked: Json[] = useApp((s) => s.queue?.blocked) || [];
  if (!blocked.length) return <p className="text-[13px] text-muted-foreground">Nothing is blocked.</p>;
  return (
    <ul id="blocked-groups" className="grid gap-2">
      {blocked.map((b) => (
        <li key={b.reason} className="grid gap-1 rounded-xl bg-warning-bg px-4 py-3 text-[13px] text-warning">
          <span className="font-medium">{b.reason}{b.assets ? ` · fixing it unblocks ${plural(b.assets, "asset", "assets")}` : ""}</span>
          <span className="flex flex-wrap items-center gap-2 text-[12.5px]">
            <Reason text={b.fix} className="flex-1" />
            {b.reason.startsWith("Blender") && <Button variant="quiet" className="h-7 px-2" tooltip="Opens Settings, where you choose the Blender to use" onClick={() => navigate({ page: "settings" })}>Open Settings</Button>}
          </span>
        </li>
      ))}
    </ul>
  );
}

function Failures() {
  const groups: Json[] = useApp((s) => s.queue?.failures) || [];
  if (!groups.length) return <p id="failures-empty" className="text-[13px] text-muted-foreground">No recorded failures.</p>;
  return (
    <ul id="failure-groups" className="grid gap-2">
      {groups.map((g) => (
        <li key={g.key + g.stage + g.reason} className="grid gap-2 rounded-xl bg-surface-2 px-4 py-3">
          <div className="flex flex-wrap items-center gap-2 text-[13px]">
            <Hint content="The step that failed"><span className="inline-flex"><Badge tone="fault">{g.stage}</Badge></span></Hint>
            <Reason text={g.reason} className="mr-auto" />
            <span className="text-[12px] text-muted-foreground">{plural(g.assets.length, "asset", "assets")} · {g.folder}</span>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="quiet" className="h-7 px-2" tooltip="Copies the failure and the paths of its files" onClick={() => void copyText(`${g.stage}: ${g.reason}\n` + g.assets.map((a: Json) => a.path || a.name).join("\n"), "The failure and its files are on the clipboard.")}><Copy className="size-3.5" aria-hidden />Copy</Button>
            <Button variant="quiet" className="h-7 px-2" tooltip="Checks which of these failures came from a file problem that is fixed now, and asks before retrying them" onClick={() => void recheckFailures({ key: g.key })}><RotateCcw className="size-3.5" aria-hidden />Recheck…</Button>
            <Button variant="quiet" className="h-7 px-2" tooltip="Opens the Library at the first failed asset" onClick={() => openSources(g.key, "", g.assets[0]?.asset_id)}><FolderOpen className="size-3.5" aria-hidden />Show in Library</Button>
          </div>
        </li>
      ))}
    </ul>
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

function Recent() {
  const recent: Json[] = useApp((s) => s.queue?.recent) || [];
  if (!recent.length) return <p className="text-[13px] text-muted-foreground">Finished work appears here.</p>;
  return (
    <ul id="recent-items" className="grid gap-1.5">
      {grouped(recent).map(({ item, count }) => {
        const [label, tone] = OUTCOME[item.status] || [item.status, "neutral"];
        const seconds = item.started_utc && item.finished_utc ? (Date.parse(item.finished_utc) - Date.parse(item.started_utc)) / 1000 : null;
        return (
          <li key={item.id + item.finished_utc} className="flex flex-wrap items-center gap-2 rounded-xl px-3 py-2 text-[13px] hover:bg-surface-2">
            <Badge tone={tone}>{label}</Badge>
            <span className="mr-auto min-w-0 truncate">{item.title || ACTION[item.action]} · {item.label}{item.resolved ? ` · ${plural(item.resolved, "asset", "assets")}` : ""}</span>
            {count > 1 && <Hint content="The same work ended the same way several times in a row" focusable><span className="recent-repeat text-[11.5px] text-muted-foreground tabular-nums">× {count}</span></Hint>}
            {seconds !== null && <span className="text-[11.5px] text-muted-foreground tabular-nums">{seconds < 90 ? Math.round(seconds) + " s" : Math.round(seconds / 60) + " min"}</span>}
            {item.log && <Button variant="quiet" className="h-7 px-2" tooltip="Opens the full log this work wrote" onClick={() => void showLog(item.log)}><FileText className="size-3.5" aria-hidden />Show log</Button>}
            {item.reason && <Reason text={item.reason} className="w-full text-[12px] text-muted-foreground" />}
          </li>
        );
      })}
    </ul>
  );
}

export function Processing({ focus: _focus }: { focus?: string }) {
  const queue = useApp((s) => s.queue);
  const coverage = useApp((s) => s.coverage);
  const context = useApp((s) => s.context);
  useEffect(() => {
    void loadQueue();
    const timer = setInterval(() => void loadQueue(), 2500);
    return () => clearInterval(timer);
  }, []);
  const failures = (queue?.failures || []).reduce((n: number, g: Json) => n + g.assets.length, 0);
  return (
    <div id="processing-view" className="h-full overflow-y-auto overscroll-contain px-8 pb-12 scroll-thin">
      <div className="mx-auto grid max-w-[1120px] gap-6">
        <div className="flex flex-wrap items-end gap-4">
          <div className="mr-auto">
            <h1 className="text-[26px] font-semibold text-foreground">Asset processing</h1>
            <p className="mt-2 max-w-[640px] text-[13.5px] leading-relaxed text-muted-foreground">What is running, what waits, what can’t run yet and what has been recorded. Nothing starts until you ask; scans never run models.</p>
          </div>
          <div className="grid gap-1 text-right">
            <p id="coverage" className="text-[12.5px] text-muted-foreground">{coverage || <Skeleton className="h-3.5 w-48" />}</p>
            {context?.versions && <p id="version" className="font-mono text-[11px] text-subtle">Catalog {String(context.versions.catalog).slice(0, 10)} · index {String(context.versions.index).slice(0, 10)}</p>}
            <Button variant="quiet" className="h-7 justify-self-end px-2 text-[12px]" tooltip="Reloads the catalog and search index versions agents see now" onClick={() => void refreshContext(true)}><RotateCcw className="size-3.5" aria-hidden />Refresh published view</Button>
          </div>
        </div>
        {!queue ? <Skeleton className="h-40 w-full rounded-[22px]" /> : (
          <>
            <Section id="running" title="Running"><Running /></Section>
            <Section id="up-next-section" title="Up next" count={(queue.up_next || []).length}><UpNext /></Section>
            <Section id="blocked" title="Blocked" hint="Work whose next step can’t run on this computer yet. It is never offered as something to process; each fix says what it unblocks."><Blocked /></Section>
            <Section id="failures" title="Recorded failures" count={failures} hint="Recorded evidence, kept apart from pending work and never retried automatically. Other assets in the same folder stay usable."><Failures /></Section>
            <Section id="recent" title="Recent"><Recent /></Section>
          </>
        )}
      </div>
    </div>
  );
}
