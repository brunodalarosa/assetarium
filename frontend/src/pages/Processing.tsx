import { FolderOpen, RotateCcw } from "lucide-react";
import { type CSSProperties, useEffect, useRef } from "react";
import { cn } from "@/lib/utils";
import type { Json } from "../app/api";
import {
  describeActive, DESCRIBE_RESULTS, descriptionBlocked, descriptionSummary, operationActive, plural, sourceMessage,
} from "../app/format";
import { generateDescriptions, navigate, refreshContext, setState, sourceAction, useApp } from "../app/store";
import { Skeleton, SkeletonLines } from "../ui/Loading";
import { Badge, type BadgeTone, Banner, Button, Disclosure, Progress } from "../ui/primitives";

function sourceState(source: Json): [string, BadgeTone] {
  const operation = source.operation || {};
  if (operationActive(operation)) return [operation.operation === "describe" ? "Describing" : operation.status === "cancelling" ? "Cancelling" : "In progress", "info"];
  if (source.scan_fault) return ["Scan fault", "fault"];
  if (!source.enabled) return ["Disabled", "neutral"];
  if (source.processing_paused) return ["Paused", "neutral"];
  if (!source.scanned) return ["Waiting for scan", "neutral"];
  if (source.needs_processing) return ["Needs processing", "warning"];
  if (source.failed) return ["Done · failures recorded", "warning"];
  return ["Up to date", "success"];
}

function OperationProgress({ source, operation, label }: { source: Json; operation: Json; label: string }) {
  const value = Math.round((operation.progress || 0) * 100);
  const phase = `${operation.phase || operation.status || "Waiting"}${operation.total ? " · " + operation.completed + " / " + operation.total : ""}`;
  return (
    <div className="grid gap-2">
      <Progress value={value} label={`${label} for ${source.name}`} valueText={`${value}% — ${phase}`} />
      <p className="source-progress-label text-[12px] text-muted-foreground">{operation.reason || phase}</p>
    </div>
  );
}

function SourceCard({ source, focused }: { source: Json; focused: boolean }) {
  const ref = useRef<HTMLElement>(null);
  const report = useApp((s) => s.notifications.find((item) => item.kind === "descriptions_report" && item.source_key === source.key));
  useEffect(() => {
    // Scroll only the page's own scroller; scrollIntoView would also shift the fixed app shell.
    const card = ref.current, scroller = document.getElementById("processing-view");
    if (!focused || !card || !scroller) return;
    const top = card.getBoundingClientRect().top - scroller.getBoundingClientRect().top + scroller.scrollTop;
    scroller.scrollTo({ top: Math.max(0, top - (scroller.clientHeight - card.offsetHeight) / 2), behavior: "smooth" });
    card.focus({ preventScroll: true });
  }, [focused]);
  const operation = source.operation || {};
  const describing = describeActive(source);
  const importing = operationActive(operation) && !describing;
  const finished = !operationActive(operation) && operation.operation !== "describe" && ["cancelled", "complete_with_faults"].includes(operation.status);
  const [state, tone] = sourceState(source);
  const blocked = descriptionBlocked(source);
  const needsWork = (source.needs_processing || source.scan_fault) && !operationActive(operation);
  return (
    <article
      ref={ref}
      tabIndex={-1}
      data-source={source.key}
      aria-labelledby={`processing-${source.key}`}
      className={cn("source-warning grid gap-5 rounded-[22px] border bg-surface p-6 outline-none transition-shadow", focused ? "border-primary ring-2 ring-primary/30" : "border-border")}
    >
      <header className="flex flex-wrap items-start gap-3">
        <div className="min-w-0 flex-1">
          <h3 id={`processing-${source.key}`} className="text-[16px] font-semibold text-foreground">{source.name}</h3>
          <p className="source-path mt-1 truncate text-[12px] text-muted-foreground" title={source.path}>{source.path}</p>
        </div>
        <Badge tone={tone} className="h-7 px-2.5">{state}</Badge>
      </header>
      <div className="grid gap-3">
        <h4 className="text-[12px] font-medium tracking-wide text-muted-foreground uppercase">Import</h4>
        <p className="text-[13.5px] leading-relaxed text-foreground">{sourceMessage(source)}</p>
        {(importing || finished) && <OperationProgress source={source} operation={operation} label="Processing and publishing progress" />}
        <div className="source-actions flex flex-wrap items-center gap-2">
          {needsWork && (
            <Button
              data-source={source.key}
              data-action="process"
              disabled={!source.enabled || source.processing_paused}
              title={source.processing_paused ? "Select processing formats in Settings → General" : source.enabled ? undefined : "Enable this source in Settings before processing"}
              onClick={() => void sourceAction("process", source.key)}
            >
              Process assets
            </Button>
          )}
          {importing && (
            <Button variant="secondary" data-source={source.key} data-action="cancel" disabled={operation.status === "cancelling"} onClick={() => void sourceAction("cancel", source.key)}>
              {operation.status === "cancelling" ? "Cancelling…" : "Cancel"}
            </Button>
          )}
          {needsWork && !source.enabled && <p className="text-[12px] text-muted-foreground">Enable this source in Settings → Asset sources to process it.</p>}
          {needsWork && source.processing_paused && <p className="text-[12px] text-muted-foreground">Processing is paused. Select formats in Settings → General.</p>}
        </div>
      </div>
      <div className="source-descriptions grid gap-3 border-t border-border pt-5">
        <h4 className="text-[12px] font-medium tracking-wide text-muted-foreground uppercase">Descriptions <span className="font-normal normal-case tracking-normal">· optional</span></h4>
        <p className="source-descriptions-summary text-[13.5px] text-foreground tabular-nums"><strong className="sr">Descriptions </strong>{descriptionSummary(source)}</p>
        {describing ? (
          <>
            <OperationProgress source={source} operation={operation} label="Description progress" />
            <div>
              <Button variant="secondary" data-source={source.key} data-action="cancel-describe" disabled={operation.status === "cancelling"} onClick={() => void sourceAction("cancel", source.key)}>
                {operation.status === "cancelling" ? "Cancelling…" : "Cancel"}
              </Button>
            </div>
          </>
        ) : source.descriptions_enabled === false ? (
          <div className="grid gap-2">
            <p className="source-descriptions-off text-[12.5px] leading-relaxed text-muted-foreground">Descriptions are turned off. Existing descriptions stay stored and searchable.</p>
            <div className="flex flex-wrap items-center gap-3">
              <Button variant="secondary" data-source={source.key} data-action="description-settings" onClick={() => navigate({ page: "settings", tab: "general" })}>Open Settings → General</Button>
              {report && <Button variant="quiet" onClick={() => setState({ runReport: report })}>View last run report</Button>}
            </div>
          </div>
        ) : (
          <div className="flex flex-wrap items-center gap-3">
            <Button variant={blocked ? "secondary" : "primary"} data-source={source.key} data-action="describe" disabled={Boolean(blocked)} aria-describedby={`describe-help-${source.key}`} onClick={() => void generateDescriptions(source.key)}>
              Generate descriptions
            </Button>
            {report && (
              <Button variant="quiet" onClick={() => setState({ runReport: report })}>View last run report</Button>
            )}
          </div>
        )}
        {!describing && source.descriptions_enabled !== false && <p id={`describe-help-${source.key}`} className="hint text-[12px] leading-relaxed text-muted-foreground">{blocked || "Runs in the background with the engine chosen in Settings → General. Assets stay searchable by name and image meanwhile."}</p>}
        {!describing && operation.operation === "describe" && DESCRIBE_RESULTS[operation.status] && (
          <p className={cn("text-[12px] leading-relaxed", operation.reason ? "source-describe-reason text-fault" : "text-muted-foreground")}>{DESCRIBE_RESULTS[operation.status]}{operation.reason ? " " + operation.reason : ""}</p>
        )}
      </div>
    </article>
  );
}

/** A source card's ghost while the first sources answer is on its way. */
function SourceCardGhost({ index }: { index: number }) {
  const wave = index * 120;
  return (
    <div aria-hidden className="ghost-enter grid gap-5 rounded-[22px] border border-border bg-surface p-6" style={{ "--enter": `${index * 60}ms` } as CSSProperties}>
      <span className="flex items-start gap-3">
        <span className="grid flex-1 gap-2">
          <Skeleton wave={wave} className="h-4 w-[34%]" />
          <Skeleton wave={wave + 40} className="h-3 w-[52%]" />
        </span>
        <Skeleton wave={wave + 80} className="h-7 w-24 rounded-md" />
      </span>
      <SkeletonLines lines={2} wave={wave + 120} />
      <Skeleton wave={wave + 200} className="h-10 w-36 rounded-full" />
    </div>
  );
}

function FailuresReport() {
  const failures = useApp((s) => s.failures);
  return (
    <section aria-labelledby="import-failures-title" className="grid gap-3 rounded-[22px] border border-border bg-surface p-6">
      <div className="flex items-center gap-3">
        <h2 id="import-failures-title" tabIndex={-1} className="flex-1 text-[16px] font-semibold outline-none">Importing failures report</h2>
      </div>
      <p id="import-failures-summary" role="status" aria-live="polite" className="text-[13px] text-muted-foreground">
        {!failures.loaded ? <><span className="sr">Loading recorded failures…</span><Skeleton className="ghost-enter h-3.5 w-64" /></> : failures.error ? "Could not load the failures report." : `${plural(failures.assets, "asset", "assets")} with recorded failures · ${plural(failures.paths.length, "path", "paths")}`}
      </p>
      {(failures.error || failures.unavailable.length > 0) && (
        <Banner><span id="import-failures-error">{failures.error || failures.unavailable.map((item: Json) => `Could not read saved failures for ${item.source}: ${item.reason}`).join("\n")}</span></Banner>
      )}
      {failures.paths.length > 0 ? (
        <Disclosure title={`Show ${plural(failures.paths.length, "path", "paths")}`}>
          <ul id="import-failures-list" aria-label="Asset paths with recorded importing failures" tabIndex={0} className="max-h-[50vh] divide-y divide-border overflow-y-auto rounded-xl bg-surface-2 font-mono text-[11.5px] scroll-thin">
            {failures.paths.map((path) => <li key={path} className="px-4 py-2.5 break-all select-text">{path}</li>)}
          </ul>
        </Disclosure>
      ) : (
        failures.loaded && !failures.error && <p id="import-failures-empty" className="text-[13px] text-muted-foreground">No importing failures recorded.</p>
      )}
      <p className="text-[11.5px] leading-relaxed text-muted-foreground">Failures are recorded evidence and are not retried automatically. Other assets from the same source stay usable.</p>
    </section>
  );
}

export function Processing({ focus }: { focus?: string }) {
  const sources = useApp((s) => s.sources);
  const coverage = useApp((s) => s.coverage);
  const context = useApp((s) => s.context);
  const message = useApp((s) => s.sourcesMessage);
  const loaded = useApp((s) => s.sourcesLoaded);
  const count = (value: number) => (loaded ? value : <Skeleton className="my-1.5 h-6 w-10" />);
  const running = sources.filter((source: Json) => operationActive(source.operation)).length;
  const attention = sources.filter((source: Json) => source.needs_processing || source.scan_fault).length;
  const ordered = [...sources].sort((a: Json, b: Json) => Number(operationActive(b.operation) || b.needs_processing || !!b.scan_fault) - Number(operationActive(a.operation) || a.needs_processing || !!a.scan_fault));
  return (
    <div id="processing-view" className="h-full overflow-y-auto overscroll-contain px-8 pb-12 scroll-thin">
      <div className="mx-auto grid max-w-[1120px] gap-6">
        <div>
          <h1 className="text-[26px] font-semibold text-foreground">Asset processing</h1>
          <p className="mt-2 max-w-[640px] text-[13.5px] leading-relaxed text-muted-foreground">What still needs work, what is running, and what has been recorded. Processing only starts when you ask; scans never run models.</p>
        </div>
        <div className="grid gap-4 md:grid-cols-[1fr_1fr_1.5fr]">
          <div className="grid content-start gap-1 rounded-[22px] border border-border bg-surface p-5">
            <span className="text-[12px] text-muted-foreground">Needs attention</span>
            <span className="text-[24px] font-semibold tabular-nums">{count(attention)}</span>
            <span className="text-[12px] text-muted-foreground">{attention === 1 ? "source to process or check" : "sources to process or check"}</span>
          </div>
          <div className="grid content-start gap-1 rounded-[22px] border border-border bg-surface p-5">
            <span className="text-[12px] text-muted-foreground">In progress</span>
            <span className="text-[24px] font-semibold tabular-nums">{count(running)}</span>
            <span className="text-[12px] text-muted-foreground">{running === 1 ? "operation running" : "operations running"}</span>
          </div>
          <div className="grid content-start gap-2 rounded-[22px] border border-border bg-surface p-5">
            <span className="text-[12px] text-muted-foreground">Published library</span>
            <p id="coverage" className="text-[13px] leading-snug">{coverage || <><span className="sr">Loading…</span><Skeleton className="my-1 h-3.5 w-[80%]" /></>}</p>
            {context?.versions && <p id="version" className="font-mono text-[11px] text-subtle" title={JSON.stringify(context.versions, null, 2)}>Catalog {String(context.versions.catalog).slice(0, 10)} · index {String(context.versions.index).slice(0, 10)}</p>}
            <div className="library-operations"><Button variant="secondary" className="h-8 px-3 text-[12px] whitespace-nowrap" onClick={() => void refreshContext(true)}><RotateCcw className="size-3.5" aria-hidden />Refresh published view</Button></div>
          </div>
        </div>
        {message && <Banner tone="info" role="status"><span id="sources-message">{message}</span></Banner>}
        <section aria-labelledby="processing-sources-title" className="grid gap-4">
          <h2 id="processing-sources-title" className="text-[16px] font-semibold">Sources</h2>
          {!loaded ? (
            <div id="source-warnings-loading" className="grid gap-4"><span className="sr" role="status">Loading sources…</span>{[0, 1].map((index) => <SourceCardGhost key={index} index={index} />)}</div>
          ) : sources.length ? (
            <div id="source-warnings" className="grid gap-4">{ordered.map((source: Json) => <SourceCard key={source.key} source={source} focused={focus === source.key} />)}</div>
          ) : (
            <div className="grid justify-items-start gap-3 rounded-[22px] border border-dashed border-border-strong p-6">
              <p className="text-[13.5px] text-muted-foreground">No asset sources yet. Add a folder of assets to start importing.</p>
              <Button variant="secondary" onClick={() => navigate({ page: "settings", tab: "asset-sources" })}><FolderOpen className="size-4" aria-hidden />Add an asset source</Button>
            </div>
          )}
        </section>
        <FailuresReport />
      </div>
    </div>
  );
}
