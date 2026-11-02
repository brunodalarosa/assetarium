import { Bot, Check, CircleCheck, CircleDashed, Copy, Folder, FolderOpen, Minimize2, Package, TriangleAlert, X } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, useId, useState } from "react";
import { SPRING_LAYOUT, SPRING_PANEL } from "@/lib/ease";
import { cn } from "@/lib/utils";
import type { Json } from "../app/api";
import { plural } from "../app/format";
import {
  closeAddFolder, copyAgentPrompt, finishAddFolder, makePreviews, minimizeAddFolder, openSources, useApp,
} from "../app/store";
import { ProposalReview } from "./ProposalReview";
import { Banner, Button, IconButton, Spinner } from "./primitives";

const STEPS = [["look", "Quick look"], ["found", "What we found"], ["agent", "Finish"]] as const;
const IDLE_MS = 120_000;
const MARKER: Record<string, string> = { license: "license", readme: "readme", preview: "preview image", shortcut: "web link", versioned_name: "version in name" };

function Steps({ step }: { step: string }) {
  const index = step === "done" ? 3 : STEPS.findIndex(([id]) => id === step);
  return (
    <ol className="flex items-center gap-2 text-[12px]" aria-label="Steps">
      {STEPS.map(([id, label], i) => (
        <li key={id} className={cn("flex items-center gap-1.5", i <= index ? "text-foreground" : "text-subtle")} aria-current={i === index ? "step" : undefined}>
          <span className={cn("grid size-5 place-items-center rounded-full border text-[10.5px] tabular-nums", i < index ? "border-primary bg-primary text-primary-foreground" : i === index ? "border-primary text-primary" : "border-border")}>
            {i < index ? <Check className="size-3" aria-hidden /> : i + 1}
          </span>
          <span className="hidden sm:inline">{label}</span>
          {i < STEPS.length - 1 && <span aria-hidden className="mx-1 h-px w-5 bg-border" />}
        </li>
      ))}
    </ol>
  );
}

/** The tree filling in as names are read: one row per top folder, a pack badge when it carries pack markers. */
function Look({ look }: { look: Json | null }) {
  const reduce = useReducedMotion();
  const top: Json[] = look?.top || [];
  return (
    <div className="grid gap-4">
      <ul id="quick-look-tree" className="grid max-h-[46vh] gap-1 overflow-y-auto pr-1 scroll-thin" aria-live="polite">
        <AnimatePresence initial={false}>
          {top.map((entry) => {
            const pack = entry.markers.length > 0;
            const Icon = pack ? Package : Folder;
            return (
              <motion.li key={entry.name} layout initial={reduce ? false : { opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={SPRING_LAYOUT}
                className="flex items-center gap-2.5 rounded-xl px-3 py-2 text-[13px] odd:bg-surface-2/50">
                <Icon className={cn("size-4 shrink-0", pack ? "text-primary" : "text-muted-foreground")} aria-hidden />
                <span className="min-w-0 flex-1 truncate">{entry.name}</span>
                {pack && <span className="rounded-full bg-accent-soft px-2 py-0.5 text-[11px] text-accent-soft-foreground">pack · {MARKER[entry.markers[0]] || entry.markers[0]}</span>}
                <span className="shrink-0 text-[11.5px] text-muted-foreground tabular-nums">{plural(entry.files, "file", "files")}</span>
              </motion.li>
            );
          })}
        </AnimatePresence>
        {!top.length && <li className="px-3 py-6 text-center text-[13px] text-muted-foreground">Reading folder names…</li>}
      </ul>
      <p id="quick-look-progress" role="status" className="flex items-center gap-2 text-[12.5px] text-muted-foreground tabular-nums">
        <Spinner className="size-3.5" />{plural(look?.folders || 0, "folder", "folders")} · {plural(look?.files || 0, "file", "files")} read · {Math.round(look?.seconds || 0)} s
        {look?.more_top ? ` · ${look.more_top} more folders` : ""}
      </p>
    </div>
  );
}

const TILE = {
  fine: { icon: CircleCheck, label: "look fine", tone: "text-success" },
  suggestions: { icon: CircleDashed, label: "have suggestions", tone: "text-primary" },
  needs_structure: { icon: TriangleAlert, label: "need a structure", tone: "text-warning" },
} as const;

function Found({ look }: { look: Json }) {
  const result = look.result, busy = useApp((s) => s.addFolder.busy), error = useApp((s) => s.addFolder.error);
  const needs: Json[] = result.packs.filter((p: Json) => p.status !== "fine");
  return (
    <div className="grid gap-5">
      <p className="text-[13px] text-muted-foreground">{plural(result.packs.length, "pack", "packs")} · {plural(result.models, "model", "models")} · {plural(result.images, "image", "images")} in {plural(look.files, "file", "files")}, read {look.seconds < 1 ? "in under a second" : `in ${Math.round(look.seconds)} s`}</p>
      <div id="found-counts" className="grid grid-cols-3 gap-3">
        {(Object.keys(TILE) as (keyof typeof TILE)[]).map((status) => {
          const { icon: Icon, label, tone } = TILE[status];
          return (
            <div key={status} data-status={status} className="grid justify-items-start gap-1 rounded-2xl border border-border bg-surface-2/50 p-3.5">
              <Icon className={cn("size-4.5", tone)} aria-hidden />
              <span className="text-[22px] leading-none font-semibold tabular-nums">{result.counts[status]}</span>
              <span className="text-[12px] text-muted-foreground">{label}</span>
            </div>
          );
        })}
      </div>
      {needs.length > 0 && (
        <ul id="found-needs" className="grid gap-1.5 text-[12.5px]">
          {needs.slice(0, 6).map((p) => <li key={p.pack}><span className="font-medium">{p.name}</span><span className="text-muted-foreground"> · {[...p.needs, ...p.suggestions].join(" · ")}</span></li>)}
          {needs.length > 6 && <li className="text-muted-foreground">and {needs.length - 6} more</li>}
        </ul>
      )}
      {result.why.length > 0 && (
        <details id="found-why" className="rounded-2xl bg-surface-2/60 p-3.5 text-[12.5px]" open>
          <summary className="cursor-pointer font-medium">How did we decide?</summary>
          <ul className="mt-2 grid gap-1.5 text-muted-foreground">{result.why.map((line: string) => <li key={line}>{line}</li>)}</ul>
          <p className="mt-2 text-[11.5px] text-subtle">Only folder and file names were read. Assetarium never writes into the folder.</p>
        </details>
      )}
      {error && <Banner><span>{error}</span></Banner>}
      <div className="grid gap-2">
        <div className="flex flex-wrap gap-2">
          <Button id="add-folder-agent" disabled={busy} onClick={() => void finishAddFolder("agent")}><Bot className="size-4" aria-hidden />Let my agent finish</Button>
          <Button id="add-folder-myself" variant="secondary" disabled={busy} onClick={() => void finishAddFolder("myself")}>Review myself</Button>
          <Button id="add-folder-later" variant="quiet" disabled={busy} onClick={() => void finishAddFolder("later")}>Later</Button>
        </div>
        <p className="text-[11.5px] text-subtle">Each choice adds the folder and scans it (reading every file once); nothing is rendered or described until you ask.</p>
      </div>
    </div>
  );
}

function useNow(ms: number) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), ms);
    return () => clearInterval(timer);
  }, [ms]);
  return now;
}

/** The take-over: the prompt to paste, who is connected, what the agent does here, what waits for you, progress. */
function TakeOver() {
  const add = useApp((s) => s.addFolder), agent = useApp((s) => s.agent);
  const reduce = useReducedMotion();
  const now = useNow(5000);
  const mine = agent.entries.filter((e: Json) => e.library_folder === add.key || e.kind === "say").slice(-8);
  const proposals = agent.proposals.filter((p: Json) => p.library_folder === add.key);
  const signals = add.signals;
  const total = signals?.total || 0, done = total - (signals?.needs_structure || 0);
  const last = mine.length ? Date.parse(mine[mine.length - 1].utc) : 0;
  const idle = add.copiedAt !== null && now - Math.max(last, add.copiedAt) > IDLE_MS;
  return (
    <div className="grid gap-4">
      <section className="grid gap-2 rounded-2xl border border-border bg-surface-2/50 p-4">
        <h3 className="text-[13px] font-semibold">Paste this into your agent</h3>
        <p id="agent-take-over-prompt" className="max-h-28 overflow-y-auto text-[12.5px] leading-relaxed select-text scroll-thin">{add.prompt}</p>
        <div><Button id="copy-agent-prompt" variant="secondary" className="h-8 px-3" onClick={() => copyAgentPrompt()}><Copy className="size-3.5" aria-hidden />Copy prompt</Button></div>
      </section>
      <p id="take-over-connection" role="status" className="flex items-center gap-2 text-[12.5px] text-muted-foreground">
        <span aria-hidden className={cn("size-2 rounded-full", agent.connected.length ? (agent.working ? "agent-pulse bg-primary" : "bg-success") : "bg-border-strong")} />
        {agent.connected.length ? `${agent.connected.map((c: Json) => c.name).filter(Boolean).join(", ") || "Your agent"} ${agent.working ? "is working" : "is connected"}` : "Waiting for your agent… Add Assetarium to it in Settings → General if you haven’t."}
      </p>
      {idle && (
        <Banner tone="warning">
          <span id="agent-idle" className="flex flex-wrap items-center gap-2">Your agent seems idle.
            <Button variant="quiet" className="h-7 px-2" onClick={() => copyAgentPrompt()}>Copy the prompt again</Button>
            <Button variant="quiet" className="h-7 px-2" onClick={() => { closeAddFolder(); openSources(add.key || undefined, ""); }}>Take over myself</Button>
          </span>
        </Banner>
      )}
      <ol id="take-over-feed" className="grid max-h-[24vh] gap-0.5 overflow-y-auto scroll-thin" aria-live="polite">
        {mine.map((e: Json) => (
          <motion.li key={e.utc + e.run} initial={reduce ? false : { opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={SPRING_LAYOUT}
            className={cn("rounded-lg px-2 py-1 text-[12.5px]", e.kind === "say" ? "bg-surface-2/70" : "text-muted-foreground")}>{e.text}</motion.li>
        ))}
        {!mine.length && <li className="px-2 py-3 text-[12.5px] text-subtle">What your agent reads, changes and proposes here appears as it happens.</li>}
      </ol>
      {proposals.length > 0 && <div className="grid gap-2.5"><ProposalReview proposals={proposals} /></div>}
      <div className="grid gap-1.5">
        <div className="h-2 overflow-hidden rounded-full bg-surface-2" role="progressbar" aria-valuemin={0} aria-valuemax={total} aria-valuenow={done} aria-label="Packs with a structure">
          <motion.div className="h-full rounded-full bg-primary" animate={{ width: total ? `${(done / total) * 100}%` : "0%" }} transition={SPRING_PANEL} />
        </div>
        <p id="take-over-progress" className="text-[12px] text-muted-foreground tabular-nums">
          {signals ? `${done} of ${plural(total, "pack", "packs")} structured${signals.waiting ? ` · ${plural(signals.waiting, "proposal waits", "proposals wait")} for you` : ""}${signals.scanning ? " · scanning files" : ""}` : "Reading…"}
        </p>
      </div>
    </div>
  );
}

function Done() {
  const add = useApp((s) => s.addFolder);
  return (
    <div id="add-folder-done" className="grid justify-items-start gap-4">
      <span className="grid size-11 place-items-center rounded-2xl bg-accent-soft text-accent-soft-foreground"><Check className="size-5" aria-hidden /></span>
      <p className="text-[15px] font-semibold">Every pack in {add.name} has a structure.</p>
      <p className="text-[13px] text-muted-foreground">Make previews next to render, describe and index them; it starts only when you ask.</p>
      <div className="flex flex-wrap gap-2">
        <Button onClick={() => { if (add.key) void makePreviews({ key: add.key }); closeAddFolder(); }}>Make previews</Button>
        <Button variant="secondary" onClick={() => { const key = add.key; closeAddFolder(); openSources(key || undefined, ""); }}><FolderOpen className="size-4" aria-hidden />Open the folder</Button>
      </div>
    </div>
  );
}

/** Add library folder (decision 0024): a quick look by names, what was found and why, then who finishes. */
export function AddFolderWizard() {
  const add = useApp((s) => s.addFolder);
  const titleId = useId();
  const reduce = useReducedMotion();
  useEffect(() => {
    if (!add.open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      if (add.step === "agent") minimizeAddFolder();
      else closeAddFolder();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [add.open, add.step]);
  return (
    <AnimatePresence>
      {add.open && (
        <motion.div id="add-folder-wizard" role="dialog" aria-modal="true" aria-labelledby={titleId} data-step={add.step}
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          className="fixed inset-0 z-[45] grid place-items-center bg-background/70 p-4 backdrop-blur-sm">
          <motion.section initial={reduce ? false : { y: 16, scale: 0.98 }} animate={{ y: 0, scale: 1 }} transition={SPRING_PANEL}
            className="flex max-h-[88vh] w-[min(760px,100%)] flex-col overflow-hidden rounded-[28px] border border-border bg-surface shadow-panel">
            <header className="flex items-start justify-between gap-4 px-7 pt-6 pb-4">
              <div className="grid min-w-0 gap-2">
                <h2 id={titleId} className="truncate text-[19px] font-semibold">{add.step === "look" ? "Reading" : "Adding"} {add.name}</h2>
                <Steps step={add.step} />
              </div>
              <div className="flex items-center gap-1">
                {add.step === "agent" && <IconButton label="Minimize; your agent keeps working" onClick={() => minimizeAddFolder()} className="size-9"><Minimize2 className="size-4" /></IconButton>}
                <IconButton label="Close" onClick={() => (add.step === "agent" ? minimizeAddFolder() : closeAddFolder())} className="size-9"><X className="size-4" /></IconButton>
              </div>
            </header>
            <div className="min-h-0 overflow-y-auto px-7 pb-7 scroll-thin">
              {add.error && add.step === "look" ? <Banner><span>{add.error}</span></Banner>
                : add.step === "look" ? <Look look={add.look} />
                : add.step === "found" && add.look?.result ? <Found look={add.look} />
                : add.step === "agent" ? <TakeOver />
                : add.step === "done" ? <Done /> : null}
            </div>
          </motion.section>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
