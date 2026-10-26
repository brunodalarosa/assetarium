import { FolderOpen, Monitor, Moon, Search, Sun } from "lucide-react";
import { motion } from "motion/react";
import { type CSSProperties, type FormEvent, useEffect, useState } from "react";
import { Checkbox } from "@/components/beui/checkbox";
import { Switch } from "@/components/beui/switch";
import { Tabs, TabsList, TabsTrigger } from "@/components/beui/tabs";
import { SPRING_LAYOUT } from "@/lib/ease";
import { cn } from "@/lib/utils";
import type { Json } from "../app/api";
import { BATCH_HELP, BUDGET_HELP, DESCRIPTIONS_OFF, formatLabel, operationActive, SEARCH_HELP, setupRecordText, sourceMessage } from "../app/format";
import {
  chooseSourceDirectory, confirmRemoveSource, navigate, openAgentSetupFromSettings, openProcessing, openSetup, saveGeneralSettings, setAppearance, type SettingsTab, sourceAction, sourceFolders, useApp,
} from "../app/store";
import { EngineFields, SearchDeviceField } from "../ui/EngineFields";
import { Skeleton, SkeletonLines } from "../ui/Loading";
import { Banner, Button, Card, RadioCards, SelectField, TextField } from "../ui/primitives";

const FORMATS: [string, string][] = [["fbx", "FBX"], ["gltf", "glTF / GLB"], ["obj", "OBJ"]];
const APPEARANCES = [
  { value: "system", label: "Match Windows", icon: Monitor },
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
];

function AppearancePicker() {
  const appearance = useApp((s) => s.appearance);
  return (
    <div role="radiogroup" aria-label="Appearance" className="inline-flex w-fit gap-1 rounded-full bg-surface-2 p-1">
      {APPEARANCES.map(({ value, label, icon: Icon }) => {
        const active = appearance === value;
        return (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={active}
            id={`appearance-${value}`}
            onClick={() => void setAppearance(value)}
            onKeyDown={(event) => {
              const index = APPEARANCES.findIndex((a) => a.value === value);
              const next = event.key === "ArrowRight" || event.key === "ArrowDown" ? 1 : event.key === "ArrowLeft" || event.key === "ArrowUp" ? -1 : 0;
              if (!next) return;
              event.preventDefault();
              const target = APPEARANCES[(index + next + APPEARANCES.length) % APPEARANCES.length];
              void setAppearance(target.value);
              document.getElementById(`appearance-${target.value}`)?.focus();
            }}
            tabIndex={active ? 0 : -1}
            className={cn("relative inline-flex h-9 items-center gap-2 rounded-full px-4 text-[12.5px] font-medium transition-colors", active ? "text-foreground" : "text-muted-foreground hover:text-foreground")}
          >
            {active && <motion.span layoutId="appearance-pill" transition={SPRING_LAYOUT} className="absolute inset-0 rounded-full bg-surface shadow-[0_1px_3px_rgb(0_0_0/0.1)]" />}
            <Icon className="relative size-4" aria-hidden />
            <span className="relative">{label}</span>
          </button>
        );
      })}
    </div>
  );
}

function SetupCard() {
  const info = useApp((s) => s.setup.info);
  const configured = info?.blender?.configured;
  return (
    <Card id="setup-card" title="Setup" help="Walks through Blender, formats, storage and descriptions again with your current values filled in, or lets your AI agent do it. Nothing is saved until you (or your agent, within the access you open) save it.">
      <div className="grid gap-1 text-[13px]">
        <p id="setup-record">{setupRecordText(info?.record)}</p>
        <p className="break-words text-[12.5px] text-muted-foreground">Blender: {configured ? `${configured} (${info.blender.config_file})` : "found automatically when processing (not set in the configuration)"}</p>
      </div>
      <div className="flex flex-wrap gap-3">
        <Button variant="secondary" id="run-setup" onClick={() => void openSetup()}>Run setup</Button>
        <Button variant="secondary" id="run-agent-setup" onClick={() => void openAgentSetupFromSettings()}>Run setup with my agent</Button>
      </div>
    </Card>
  );
}

function General() {
  const general = useApp((s) => s.general);
  const engines = useApp((s) => s.setup.info?.engines) || [];
  const devices = useApp((s) => s.setup.info?.search_devices) || [];
  const [budget, setBudget] = useState("");
  const [formats, setFormats] = useState<string[]>([]);
  const [batch, setBatch] = useState("8");
  const [enabled, setEnabled] = useState(true);
  const [engine, setEngine] = useState("builtin");
  const [url, setUrl] = useState("");
  const [model, setModel] = useState("");
  const [device, setDevice] = useState("cuda");
  useEffect(() => {
    if (!general.values) return;
    setBudget(String(general.values.storage_budget_gib));
    setFormats(general.values.processing_formats);
    setBatch(String(general.values.caption_batch_size));
    setEnabled(general.values.descriptions_enabled);
    setEngine(general.values.description_engine);
    setUrl(general.values.description_server.url);
    setModel(general.values.description_server.model);
    setDevice(general.values.search_device);
  }, [general.values]);
  const disabled = general.loading || general.busy || !general.values;
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!event.currentTarget.reportValidity()) return;
    void saveGeneralSettings(budget, formats, batch, { enabled, engine, server: { url, model } }, device);
  };
  return (
    <div className="grid gap-5">
      <Card title="Appearance" help="Match Windows follows your system light or dark setting.">
        <AppearancePicker />
      </Card>
      <SetupCard />
      <form id="general-settings-form" onSubmit={submit} className="grid gap-5">
        <Card title="Storage budget" help={BUDGET_HELP}>
          <TextField id="storage-budget" label="Storage budget (GiB)" type="number" min={1} max={1048576} step={1} required value={budget} disabled={disabled} onChange={(e) => setBudget(e.target.value)} className="w-48" />
        </Card>
        <Card title="Formats to process" help="Scanning counts every supported format. New processing batches use only selected formats. Existing results are kept. Uncheck all to pause processing.">
          <fieldset id="processing-formats" disabled={disabled} className="flex flex-wrap gap-x-8 gap-y-3">
            <legend className="sr">Formats to process</legend>
            {FORMATS.map(([value, label]) => (
              <Checkbox
                key={value}
                id={`processing-format-${value}`}
                label={label}
                disabled={disabled}
                checked={formats.includes(value)}
                onCheckedChange={(checked) => setFormats((current) => (checked ? FORMATS.map(([f]) => f).filter((f) => f === value || current.includes(f)) : current.filter((f) => f !== value)))}
              />
            ))}
          </fieldset>
        </Card>
        <Card id="descriptions-card" title="Descriptions" help="Short texts an AI model on this computer writes for each asset from its previews. They are optional: names, filters, keyword search and image matching work without them.">
          <div className="flex h-10 items-center">
            <Switch checked={enabled} disabled={disabled} onCheckedChange={setEnabled} label="Generate descriptions" ariaLabel="Generate descriptions" />
          </div>
          {enabled ? (
            <EngineFields engine={engine} onEngine={setEngine} url={url} onUrl={setUrl} model={model} onModel={setModel} disabled={disabled} engines={engines} idPrefix="settings" />
          ) : (
            <p id="descriptions-off-help" className="hint text-[12.5px] leading-relaxed text-muted-foreground">{DESCRIPTIONS_OFF}</p>
          )}
        </Card>
        {enabled && engine === "builtin" && (
          <Card title="Description batch size" help={BATCH_HELP}>
            <SelectField id="caption-batch-size" label="Assets per model call" value={batch} onChange={setBatch} disabled={disabled} options={[["1", "1"], ["2", "2"], ["4", "4"], ["8", "8 (default)"]]} className="w-48" />
          </Card>
        )}
        <Card id="search-card" title="Search" help={SEARCH_HELP}>
          <SearchDeviceField value={device} onChange={setDevice} devices={devices} disabled={disabled} idPrefix="settings" />
        </Card>
        <div className="flex flex-wrap items-center gap-4">
          <Button type="submit" id="save-general-settings" disabled={disabled}>Save</Button>
          <p id="general-settings-message" role="status" aria-live="polite" className="text-[12.5px] leading-relaxed text-muted-foreground">{general.message}</p>
        </div>
      </form>
    </div>
  );
}

const where = (anchor: string) => (anchor ? `In ${anchor}` : "At the top of this source");

/** Models that could not find their textures: choose a folder by exact file name (decision 0021). */
function TextureChoice({ source, busy }: { source: Json; busy: boolean }) {
  const found: Json | null = source.texture_suggestion || null;
  const chosen: Json | null = source.texture_folder || null;
  const options: Json[] = found?.folders || [];
  const [folder, setFolder] = useState<string>("");
  const [single, setSingle] = useState(true);
  const [working, setWorking] = useState(false);
  const selected = folder || options[0]?.folder || "";
  const disabled = busy || working;
  const run = async (undo: boolean) => {
    setWorking(true);
    await sourceFolders(undo ? "textures-undo" : "textures", source.key, undo ? null : selected || null, single ? "single" : "");
    setWorking(false);
  };
  if (!found && !chosen) return null;
  const option = options.find((o) => o.folder === selected);
  const fixes = option ? (single ? option.fixes : option.fixes_without_single_copies) : single ? found?.single_copies_only.fixes : 0;
  const left = (found?.assets || 0) - (fixes || 0);
  return (
    <div className="texture-choice grid gap-3 rounded-2xl bg-surface-2 p-4">
      {chosen && (
        <p className="texture-chosen flex flex-wrap items-center gap-2 text-[12.5px] text-muted-foreground">
          <span>Textures from {chosen.folder || "no folder"}{chosen.single_copies ? " and single copies" : ""}. Repaired models wait for Process assets; originals are not changed.</span>
          <button type="button" className="font-medium text-primary hover:underline disabled:opacity-50" disabled={disabled} data-action="textures-undo" onClick={() => void run(true)}>Undo</button>
        </p>
      )}
      {found && (
        <>
          <p className="text-[13px] font-medium">Textures not found</p>
          <p className="text-[12.5px] leading-relaxed text-muted-foreground">
            {found.assets.toLocaleString()} {found.assets === 1 ? "model can’t" : "models can’t"} find {found.assets === 1 ? "its" : "their"} textures (for example {found.examples.slice(0, 3).join(", ")}).
            {options.length ? " Some textures exist in several folders, one per render pipeline. Choose which to use; matches are by exact file name." : ""}
          </p>
          {options.length > 0 && (
            <RadioCards id={`textures-${source.id}`} label="Use textures from" value={selected} onChange={setFolder} disabled={disabled}
              options={options.map((o) => ({ value: o.folder, title: o.folder, detail: `Fixes ${(single ? o.fixes : o.fixes_without_single_copies).toLocaleString()} of ${found.assets.toLocaleString()}` }))} />
          )}
          <Checkbox label="Also use textures that have only one version in this source" checked={single} disabled={disabled} onCheckedChange={setSingle}
            description="A file with that exact name exists once (or as identical copies), so there is no choice to make." />
          <p className="texture-total text-[12.5px] text-foreground">
            {(fixes || 0).toLocaleString()} fixed{left > 0 ? ` · ${left.toLocaleString()} ${left === 1 ? "stays" : "stay"} failed with ${left === 1 ? "its" : "their"} recorded ${left === 1 ? "reason" : "reasons"}` : " · none left unresolved"}
          </p>
          <div className="flex flex-wrap gap-2">
            <Button className="h-9 px-4" disabled={disabled || !fixes} data-action="textures-apply" onClick={() => void run(false)}>Apply</Button>
          </div>
          <p className="hint text-[11.5px] leading-relaxed text-subtle">Applying records your choice with each repaired model and scans again. Nothing is rendered until you click Process assets, and original files are never changed. Undo removes the choice.</p>
        </>
      )}
    </div>
  );
}

/** Duplicate export folder suggestions, saved answers and excluded folders for one source (decision 0019). */
function SourceFolders({ source, busy }: { source: Json; busy: boolean }) {
  const [pattern, setPattern] = useState("");
  const [working, setWorking] = useState(false);
  const exclusions: string[] = source.exclusions || [];
  const excluded: Json[] = source.excluded_folders || [];
  const suggestions: Json[] = source.export_suggestions || [];
  const answers: Json[] = source.export_decisions || [];
  const disabled = busy || working;
  const run = async (change: "exclusions" | "export" | "undo", value: string[] | string, decision = "") => {
    setWorking(true);
    const result = await sourceFolders(change, source.key, value, decision);
    if (change === "exclusions" && result.status !== "faulty") setPattern("");
    setWorking(false);
  };
  const files = excluded.reduce((total, item) => total + (item.files || 0), 0);
  return (
    <div className="source-folders mt-2 grid gap-3">
      <TextureChoice source={source} busy={busy} />
      {suggestions.map((s) => (
        <div key={s.id} className="export-suggestion grid gap-2 rounded-2xl bg-surface-2 p-4" data-suggestion={s.id}>
          <p className="text-[13px] font-medium">Possible duplicate exports</p>
          <p className="text-[12.5px] leading-relaxed text-muted-foreground">
            {where(s.anchor)}, {s.folders.join(", ")} have the same {s.names.toLocaleString()} model names (for example {s.sample_names.slice(0, 3).join(", ")}).
            {s.grouped_folders.length > 1 ? ` ${s.grouped_folders.join(" and ")} are already grouped.` : ""}
          </p>
          <p className="hint text-[11.5px] leading-relaxed text-subtle">
            Grouping makes one asset per model with every folder’s file attached; only the preferred file is rendered. Previews and descriptions are kept and search data is rebuilt. Excluding stops scanning the extra folders ({s.folders.filter((f: string) => f !== s.reference && !s.grouped_folders.includes(f)).join(", ")}). Nothing on disk changes either way.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button className="h-9 px-4" disabled={disabled} data-action="group" onClick={() => void run("export", s.id, "group")}>Group as alternate files</Button>
            <Button variant="secondary" className="h-9 px-4" disabled={disabled} data-action="exclude" onClick={() => void run("export", s.id, "exclude")}>Exclude extra folders</Button>
            <Button variant="quiet" className="h-9 px-4" disabled={disabled} data-action="separate" onClick={() => void run("export", s.id, "separate")}>Keep separate</Button>
          </div>
        </div>
      ))}
      {answers.length > 0 && (
        <ul className="export-answers grid gap-1 text-[12px] text-muted-foreground" aria-label="Saved answers about duplicate exports">
          {answers.map((d) => (
            <li key={d.id} className="flex flex-wrap items-center gap-2">
              <span>{d.decision === "group" ? "Grouped" : "Kept separate"}: {d.anchor ? d.anchor + " / " : ""}{d.folders.join(", ")}</span>
              <button type="button" className="font-medium text-primary hover:underline disabled:opacity-50" disabled={disabled} data-action="undo" onClick={() => void run("undo", d.id)}>Undo</button>
            </li>
          ))}
        </ul>
      )}
      <div className="grid gap-2">
        <p className="text-[13px] font-medium">Excluded folders</p>
        {exclusions.length > 0 && (
          <ul className="flex flex-wrap gap-2" aria-label="Excluded folder patterns">
            {exclusions.map((item) => (
              <li key={item} className="flex items-center gap-1.5 rounded-full bg-surface-2 py-1 pl-3 pr-1.5 text-[12px]">
                <span className="font-mono">{item}</span>
                <button type="button" aria-label={"Stop excluding " + item} disabled={disabled} className="grid size-5 place-items-center rounded-full text-muted-foreground hover:bg-surface hover:text-foreground disabled:opacity-50"
                  onClick={() => void run("exclusions", exclusions.filter((p) => p !== item))}>×</button>
              </li>
            ))}
          </ul>
        )}
        <form className="flex flex-wrap items-end gap-2" onSubmit={(event) => { event.preventDefault(); if (pattern.trim()) void run("exclusions", [...exclusions, pattern.trim()]); }}>
          <TextField id={`exclude-${source.id}`} label="Folder name or path" value={pattern} disabled={disabled} spellCheck={false} placeholder="Unity*  or  Models/Unity FBX" onChange={(e) => setPattern(e.target.value)} className="min-w-[220px] flex-1" />
          <Button type="submit" variant="secondary" className="h-10 px-4" disabled={disabled || !pattern.trim()}>Exclude</Button>
        </form>
        <p className="hint text-[11.5px] leading-relaxed text-subtle">
          {exclusions.length ? `${files.toLocaleString()} files in ${excluded.length} excluded ${excluded.length === 1 ? "folder" : "folders"} are not scanned. ` : ""}
          A name matches any folder with that name (* is a wildcard); a path with / matches one folder inside the source. Files in excluded folders can’t be used as textures either. Changing this scans the source again; nothing on disk is deleted.
        </p>
      </div>
    </div>
  );
}

function SourceRow({ source }: { source: Json }) {
  const busy = operationActive(source.operation);
  const counts = source.format_counts as Record<string, number> | undefined;
  const images = (source.import_types || []).includes("image");
  return (
    <article className="source-row grid gap-4 rounded-[22px] border border-border bg-surface p-6 sm:grid-cols-[minmax(0,1fr)_auto]">
      <div className="grid min-w-0 gap-1.5">
        <h3 className="text-[15px] font-semibold">
          <button type="button" className="source-browse-link group inline-flex max-w-full items-center gap-2 rounded-md text-left hover:text-primary" data-source={source.key} data-action="browse" aria-label={"Browse assets in " + source.name} title="Browse source contents" onClick={() => navigate({ page: "source", key: source.key })}>
            <span className="truncate">{source.name}</span>
            <span className="source-browse-icon grid size-7 shrink-0 place-items-center rounded-lg border border-border text-muted-foreground group-hover:border-primary group-hover:text-primary" aria-hidden><Search className="size-3.5" /></span>
          </button>
        </h3>
        <p className="truncate text-[12px] text-muted-foreground" title={source.path}>{source.path}</p>
        <p className="text-[12.5px] text-muted-foreground">
          {sourceMessage(source)}{" "}
          <button type="button" className="font-medium text-primary hover:underline" onClick={() => void openProcessing(source.key)}>View in Asset processing</button>
        </p>
        <p className="source-format-counts text-[12px] text-muted-foreground tabular-nums">{counts ? Object.entries(counts).map(([format, count]) => `${formatLabel(format)}: ${count}`).join(" · ") : "Format counts appear after scanning."}</p>
        {source.import_formats && (
          <p className="hint text-[11.5px] text-subtle">Imported formats: {source.import_formats.length ? source.import_formats.map(formatLabel).join(", ") : "none"}. Other original formats are retained and excluded from imports.</p>
        )}
        <div className="source-images mt-2">
          <Checkbox
            label="Include 2D images"
            description={images ? "Standalone PNG, JPEG, WebP, SVG and other still images are imported as 2D assets. Model textures, previews and sprite sheets are left out." : "Only 3D models are imported. Turn on to also import standalone still images; this source is scanned again."}
            checked={images}
            disabled={busy}
            onCheckedChange={(checked) => void sourceAction("images", source.key, null, checked)}
          />
        </div>
        <SourceFolders source={source} busy={busy} />
      </div>
      <div className="source-controls flex items-start gap-4">
        <div className="source-enabled flex h-10 items-center">
          <Switch checked={source.enabled} onCheckedChange={(checked) => void sourceAction("enabled", source.key, null, checked)} label="Enabled" ariaLabel={"Enable " + source.name} />
        </div>
        <Button variant="danger" data-source={source.key} data-action="remove" disabled={busy} onClick={() => confirmRemoveSource(source)}>Remove</Button>
      </div>
    </article>
  );
}

function AssetSources() {
  const sources = useApp((s) => s.sources);
  const message = useApp((s) => s.sourcesMessage);
  const loaded = useApp((s) => s.sourcesLoaded);
  const [directory, setDirectory] = useState("");
  const add = () => {
    const value = directory.trim();
    if (!value) return;
    void sourceAction("add", null, value).then((result) => result?.status !== "faulty" && setDirectory(""));
  };
  return (
    <div className="grid gap-5">
      <Card title="Add an asset source" help="Enable sources to include them in searches. Removing a source keeps its files and saved metadata. Counts include all scanned formats; assets with alternate formats appear in each applicable count.">
        <div className="source-add flex flex-wrap items-end gap-3">
          <TextField id="source-directory" label="Asset directory" placeholder="Choose an asset source directory" value={directory} onChange={(e) => setDirectory(e.target.value)} className="min-w-[260px] flex-1" />
          <Button variant="secondary" id="choose-source" onClick={() => void chooseSourceDirectory().then((value) => value && setDirectory(value))}><FolderOpen className="size-4" aria-hidden />Choose folder…</Button>
          <Button id="add-source" disabled={!directory.trim()} onClick={add}>Add source</Button>
        </div>
      </Card>
      {message && <Banner tone="info" role="status"><span id="sources-message">{message}</span></Banner>}
      <div id="source-list" className="grid gap-4">{sources.map((source: Json) => <SourceRow key={source.key} source={source} />)}</div>
      {!loaded && (
        <div id="sources-loading" className="grid gap-4" role="status">
          <span className="sr">Loading sources…</span>
          {[0, 1].map((index) => (
            <div key={index} aria-hidden className="ghost-enter grid gap-3 rounded-[22px] border border-border bg-surface p-6" style={{ "--enter": `${index * 60}ms` } as CSSProperties}>
              <Skeleton wave={index * 120} className="h-4 w-[30%]" />
              <Skeleton wave={index * 120 + 40} className="h-3 w-[55%]" />
              <SkeletonLines lines={2} wave={index * 120 + 80} className="mt-1" />
            </div>
          ))}
        </div>
      )}
      {loaded && !sources.length && <p id="sources-empty" className="text-[13px] text-muted-foreground">No asset sources yet. Add a directory to get started.</p>}
    </div>
  );
}

export function Settings({ tab = "general" }: { tab?: SettingsTab }) {
  return (
    <div id="settings-view" className="h-full overflow-y-auto overscroll-contain px-8 pb-12 scroll-thin">
      <div className="mx-auto grid max-w-[1120px] gap-6">
        <h1 id="settings-title" tabIndex={-1} className="text-[26px] font-semibold outline-none">Settings</h1>
        <Tabs value={tab} onValueChange={(value) => navigate({ page: "settings", tab: value as SettingsTab })} variant="segment">
          <TabsList aria-label="Settings sections" className="rounded-full bg-surface-2 p-1 [--tabs-active-fg:var(--color-foreground)]">
            <TabsTrigger value="general" id="general-tab" aria-controls="general-panel" className="h-9 rounded-full px-5 text-[13px]" indicatorClassName="rounded-full bg-surface shadow-[0_1px_3px_rgb(0_0_0/0.1)]">General</TabsTrigger>
            <TabsTrigger value="asset-sources" id="asset-sources-tab" aria-controls="asset-sources-panel" className="h-9 rounded-full px-5 text-[13px]" indicatorClassName="rounded-full bg-surface shadow-[0_1px_3px_rgb(0_0_0/0.1)]">Asset sources</TabsTrigger>
          </TabsList>
        </Tabs>
        <section id="general-panel" role="tabpanel" aria-labelledby="general-tab" hidden={tab !== "general"}>{tab === "general" && <General />}</section>
        <section id="asset-sources-panel" role="tabpanel" aria-labelledby="asset-sources-tab" hidden={tab !== "asset-sources"}>{tab === "asset-sources" && <AssetSources />}</section>
      </div>
    </div>
  );
}
