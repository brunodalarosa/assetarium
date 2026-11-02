import { Check, CircleAlert, FolderOpen, Undo2 } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";
import type { Json } from "../app/api";
import { formatLabel } from "../app/format";
import { changeSetupStep, confirmSetupReview, finishSetup, leaveAgentSetup, startAgentSetup, type SetupStep, undoSetupValue, useApp } from "../app/store";
import { CommandBlock } from "./CommandBlock";
import { Badge, Button, Card, Spinner } from "./primitives";

/** Readiness items that only processed assets can satisfy are not setup work. */
const LATER = new Set(["gpu", "search_gpu", "embedding_capability"]);

interface Row {
  step: SetupStep;
  label: string;
  keys: string[];
  value: string;
  missing: Json[];
  hint?: string;
}

function rows(info: Json, env: Json | null): Row[] {
  const s = info.settings || {};
  const hints: Json[] = info.hints || [];
  const chosen: string[] = [info.record?.engine_hint || []].flat();
  const engines = hints.filter((h) => chosen.includes(h.id)).map((h) => h.label);
  const notReady = (items: Json[] | undefined) => (items || []).filter((item) => !item.ready && !LATER.has(item.id));
  const describe = s.descriptions_enabled;
  const server = s.description_engine === "local-server";
  const list: Row[] = [
    { step: "blender", label: "Blender", keys: ["blender"], value: info.blender?.configured || "Not set",
      missing: info.blender?.configured ? [] : [{ id: "blender", label: "Blender is not set", detail: "3D assets need it. Install Blender 5.2, then choose it here." }] },
    { step: "formats", label: "Formats", keys: ["processing_formats", "engine_hint"],
      value: (s.processing_formats?.length ? s.processing_formats.map(formatLabel).join(", ") : "None (processing paused)") + (engines.length ? ` · for ${engines.join(", ")}` : ""), missing: [] },
    { step: "storage", label: "Storage budget", keys: ["storage_budget_gib"], value: `${Number(s.storage_budget_gib).toLocaleString()} GiB`, missing: [] },
    { step: "descriptions", label: "Descriptions", keys: ["descriptions_enabled", "description_engine", "description_server"],
      value: !describe ? "Off · you can turn them on later in Settings" : server ? `Local model server · ${s.description_server?.model || "no model set"}` : "Built in (Qwen3-VL)",
      missing: describe ? notReady(env?.engines?.[s.description_engine]?.items) : [] },
    { step: "descriptions", label: "Search", keys: ["search_device"], value: s.search_device === "cpu" ? "On the CPU" : "On the NVIDIA GPU",
      missing: notReady(env?.search_devices?.[s.search_device]), hint: "Keyword search works without it." },
  ];
  if (describe && !server) list.push({ step: "batch", label: "Batch size", keys: ["caption_batch_size"], value: `${s.caption_batch_size} assets per call`, missing: [] });
  return list;
}

function Source({ row, info }: { row: Row; info: Json }) {
  const [busy, setBusy] = useState(false);
  const setBy = info.set_by || {};
  const key = row.keys.find((k) => setBy[k]);
  const entry = key ? setBy[key] : null;
  const undoable = row.keys.find((k) => setBy[k]?.set_by === "agent" && "previous" in setBy[k]);
  if (entry?.set_by === "agent")
    return (
      <span className="flex items-center gap-2">
        <Badge tone="info">{entry.approved_by === "user" ? "Proposed by agent · approved by you" : "Set by agent"}</Badge>
        {undoable && (
          <button type="button" className="report-undo flex items-center gap-1 text-[12px] font-medium text-muted-foreground underline-offset-2 hover:text-foreground hover:underline disabled:opacity-50"
            disabled={busy} aria-label={`Undo ${row.label}`} onClick={() => { setBusy(true); void undoSetupValue(undoable).finally(() => setBusy(false)); }}>
            <Undo2 className="size-3" aria-hidden />Undo
          </button>
        )}
      </span>
    );
  if (entry?.set_by === "user") return <Badge tone="neutral">Set by you</Badge>;
  return <Badge tone="neutral">{info.record?.by === "agent" ? "Checked by agent" : "Default"}</Badge>;
}

/** The end of setup, by an agent or by hand: every value with where it came from and what still needs the user. */
export function SetupReport() {
  const info = useApp((s) => s.setup.info);
  const env = useApp((s) => s.setup.env);
  const busy = useApp((s) => s.setup.saving);
  if (!info) return null;
  const record = info.record || {};
  const review = record.state === "review";
  const list = rows(info, env);
  const needs = list.filter((row) => row.missing.length).length;
  return (
    <div id="setup-report" data-state={record.state} className="grid gap-5">
      <p className="max-w-[680px] text-[13.5px] leading-relaxed text-muted-foreground">
        {review ? "Your agent checked this computer and chose these settings with you. Look them over: undo or change anything, then confirm."
          : `Setup is complete${record.by === "agent" ? " (by your agent)" : ""}. You can change any value here or later in Settings → General.`}
        {needs > 0 && ` ${needs === 1 ? "One item needs" : `${needs} items need`} you; Assetarium works without ${needs === 1 ? "it" : "them"} meanwhile.`}
      </p>
      <Card title="What is set">
        <ul id="setup-report-rows" className="grid">
          {list.map((row, index) => (
            <li key={row.label} data-row={row.step} data-needs={row.missing.length > 0}
              className="page-enter grid gap-2 border-b border-border py-3 first:pt-0 last:border-0 last:pb-0" style={{ animationDelay: `${index * 45}ms` }}>
              <div className="grid grid-cols-[auto_minmax(0,120px)_minmax(0,1fr)_auto] items-center gap-3">
                <span className={cn("grid size-6 place-items-center rounded-full", row.missing.length ? "bg-warning-bg text-warning" : "bg-success-bg text-success")}>
                  {row.missing.length ? <CircleAlert className="size-3.5" aria-label="Needs you" /> : <Check className="size-3.5" aria-label="Ready" />}
                </span>
                <span className="text-[12.5px] text-muted-foreground">{row.label}</span>
                <span className="grid justify-items-start gap-1.5 break-words text-[13px]">{row.value}<Source row={row} info={info} /></span>
                <Button variant="quiet" className="h-8 px-3 text-[12px]" onClick={() => void changeSetupStep(row.step)} aria-label={`Change ${row.label}`}>Change</Button>
              </div>
              {row.missing.length > 0 && (
                <ul className="grid gap-2 pl-9" aria-label={`${row.label}: needs you`}>
                  {row.missing.map((item) => (
                    <li key={item.id} className="grid gap-1.5" data-item={item.id}>
                      <span className="text-[12.5px]"><span className="font-medium">{item.label}</span>{item.detail ? ` · ${item.detail}` : ""}</span>
                      {item.command && <CommandBlock command={item.command} />}
                    </li>
                  ))}
                  {row.hint && <li className="text-[12px] text-muted-foreground">{row.hint}</li>}
                </ul>
              )}
            </li>
          ))}
        </ul>
        {!env && <p className="flex items-center gap-2 text-[12.5px] text-muted-foreground" role="status"><Spinner />Checking what is installed…</p>}
      </Card>
      <section id="setup-next" className="page-enter grid gap-3 rounded-2xl border border-primary/30 bg-accent-soft/40 p-5" style={{ animationDelay: `${list.length * 45 + 60}ms` }}>
        <span className="flex items-center gap-2 text-[15px] font-semibold"><FolderOpen className="size-4.5" aria-hidden />Next: choose your asset folders</span>
        <p className="text-[13px] leading-relaxed text-muted-foreground">Add the folders with your asset library in the Library tab. Assetarium lists them right away, and makes previews and search data when you start it. Your files are never changed.</p>
        <div className="flex flex-wrap gap-3">
          {review
            ? <Button id="setup-looks-good" disabled={busy} onClick={() => void confirmSetupReview()}>{busy ? "Saving…" : "Looks good"}</Button>
            : <Button id="setup-go-sources" onClick={() => finishSetup("sources")}>Go to Library</Button>}
          {!review && <Button variant="secondary" id="setup-close" onClick={() => finishSetup("close")}>Close</Button>}
        </div>
      </section>
      <p className="text-[12.5px] text-muted-foreground">
        Start over?{" "}
        <button type="button" id="setup-report-agent" className="font-medium text-foreground underline underline-offset-2" onClick={() => void startAgentSetup()}>Set up with my agent</button>
        {" · "}
        <button type="button" id="setup-report-manual" className="font-medium text-foreground underline underline-offset-2" onClick={() => leaveAgentSetup()}>Set it up yourself</button>
      </p>
    </div>
  );
}
