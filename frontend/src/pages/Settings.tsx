import { FolderOpen, Monitor, Moon, Search, Sun } from "lucide-react";
import { motion } from "motion/react";
import { type CSSProperties, type FormEvent, useEffect, useState } from "react";
import { Checkbox } from "@/components/beui/checkbox";
import { Switch } from "@/components/beui/switch";
import { Tabs, TabsList, TabsTrigger } from "@/components/beui/tabs";
import { SPRING_LAYOUT } from "@/lib/ease";
import { cn } from "@/lib/utils";
import type { Json } from "../app/api";
import { BATCH_HELP, BUDGET_HELP, DESCRIPTIONS_OFF, formatLabel, operationActive, setupRecordText, sourceMessage } from "../app/format";
import {
  chooseSourceDirectory, confirmRemoveSource, navigate, openAgentSetupFromSettings, openProcessing, openSetup, saveGeneralSettings, setAppearance, type SettingsTab, sourceAction, useApp,
} from "../app/store";
import { EngineFields } from "../ui/EngineFields";
import { Skeleton, SkeletonLines } from "../ui/Loading";
import { Banner, Button, Card, SelectField, TextField } from "../ui/primitives";

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
  const [budget, setBudget] = useState("");
  const [formats, setFormats] = useState<string[]>([]);
  const [batch, setBatch] = useState("8");
  const [enabled, setEnabled] = useState(true);
  const [engine, setEngine] = useState("builtin");
  const [url, setUrl] = useState("");
  const [model, setModel] = useState("");
  useEffect(() => {
    if (!general.values) return;
    setBudget(String(general.values.storage_budget_gib));
    setFormats(general.values.processing_formats);
    setBatch(String(general.values.caption_batch_size));
    setEnabled(general.values.descriptions_enabled);
    setEngine(general.values.description_engine);
    setUrl(general.values.description_server.url);
    setModel(general.values.description_server.model);
  }, [general.values]);
  const disabled = general.loading || general.busy || !general.values;
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!event.currentTarget.reportValidity()) return;
    void saveGeneralSettings(budget, formats, batch, { enabled, engine, server: { url, model } });
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
        <div className="flex flex-wrap items-center gap-4">
          <Button type="submit" id="save-general-settings" disabled={disabled}>Save</Button>
          <p id="general-settings-message" role="status" aria-live="polite" className="text-[12.5px] leading-relaxed text-muted-foreground">{general.message}</p>
        </div>
      </form>
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
