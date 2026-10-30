import { Monitor, Moon, Sun } from "lucide-react";
import { motion } from "motion/react";
import { type FormEvent, useEffect, useState } from "react";
import { Checkbox } from "@/components/beui/checkbox";
import { Switch } from "@/components/beui/switch";
import { SPRING_LAYOUT } from "@/lib/ease";
import { cn } from "@/lib/utils";
import type { Json } from "../app/api";
import {
  BATCH_HELP, BUDGET_HELP, DESCRIPTIONS_OFF, operationActive, RENDER_HELP, renderNowText, renderTestLine, SEARCH_HELP, SEARCH_THREADS_HELP,
  searchTestText, searchThreadsText, setupRecordText, SPEED_TEST_HELP,
} from "../app/format";
import {
  cancelBlenderCheck, checkBlenderInstallation, checkSearchReadiness, chooseBlenderInstallation, openAgentSetupFromSettings, openSetup, renderTest, saveBlenderInstallation, saveGeneralSettings, saveRenderSettings, setAppearance, type SettingsTab,
  updateBlenderInstallation, useApp,
} from "../app/store";
import { EngineFields, SearchDeviceField } from "../ui/EngineFields";
import { SkeletonLines } from "../ui/Loading";
import { ReadinessList } from "../ui/Readiness";
import { BlenderChecks, BlenderPicker } from "../ui/BlenderPicker";
import { Badge, Banner, Button, Card, SelectField, Spinner, TextField } from "../ui/primitives";

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
  return (
    <Card id="setup-card" title="Setup" help="Walks through Blender, formats, storage and descriptions again with your current values filled in, or lets your AI agent do it. Nothing is saved until you (or your agent, within the access you open) save it.">
      <div className="grid gap-1 text-[13px]">
        <p id="setup-record">{setupRecordText(info?.record)}</p>
      </div>
      <div className="flex flex-wrap gap-3">
        <Button variant="secondary" id="run-setup" onClick={() => void openSetup()}>Run setup</Button>
        <Button variant="secondary" id="run-agent-setup" onClick={() => void openAgentSetupFromSettings()}>Run setup with my agent</Button>
      </div>
    </Card>
  );
}

interface RenderDraft {
  device: string;
  processes: string;
  memory: string;
}

/** Device, renders at a time and memory (decision 0022); saved with the form, the speed test starts here. */
function Rendering({ draft, onDraft, disabled }: { draft: RenderDraft; onDraft: (draft: RenderDraft) => void; disabled: boolean }) {
  const render = useApp((s) => s.render);
  const values = render.values;
  if (!values) return <Card id="rendering-card" title="Rendering" help={RENDER_HELP}><SkeletonLines lines={2} /></Card>;
  const plan = values.plan;
  const test = values.test;
  const running = operationActive(values.operation);
  const selected = draft.device === "auto" ? test?.chosen || "cpu" : draft.device;
  const best = test?.results.find((r: Json) => r.key === selected)?.best?.processes ?? plan.best;
  const counts = Array.from({ length: Math.max(best, Number(draft.processes) || 0) }, (_, i) => String(i + 1));
  return (
    <Card id="rendering-card" title="Rendering" help={RENDER_HELP}>
      <p id="render-now" className="text-[13px] leading-relaxed">{renderNowText(plan)}</p>
      <div className="flex flex-wrap gap-4">
        <SelectField id="render-device" label="Render device" value={draft.device} disabled={disabled} className="w-72"
          onChange={(device) => onDraft({ ...draft, device })}
          options={[["auto", "Automatic (fastest in the speed test)"], ...values.devices.map((d: Json): [string, string] => [d.key, d.label])]} />
        <SelectField id="render-processes" label="Renders at a time" value={draft.processes} disabled={disabled} className="w-56"
          onChange={(processes) => onDraft({ ...draft, processes })}
          options={[["auto", `Automatic (${best})`], ...counts.map((n): [string, string] => [n, n])]} />
        <TextField id="render-memory" label="Memory for rendering (GiB)" type="number" min={1} max={4096} step={1} value={draft.memory}
          disabled={disabled} className="w-56" placeholder={plan.allowance_gib == null ? "Automatic" : `Automatic (${plan.allowance_gib} GiB now)`}
          onChange={(e) => onDraft({ ...draft, memory: e.target.value })} />
      </div>
      <p className="hint text-[12.5px] leading-relaxed text-muted-foreground">
        Leave memory empty for automatic: 70% of the memory free when processing starts.
        {plan.available_gib != null && ` ${plan.available_gib} GiB is free now; each render uses about ${plan.process_gib} GiB.`}
      </p>
      <SpeedTestLink running={running} />
    </Card>
  );
}

const CHECK_STATUS: Record<string, string> = { passed: "Ready.", warning: "Works, with a warning.", failed: "This executable can’t be used.", cancelled: "Check cancelled." };

/** The saved Blender, its check, and the wizard's Blender step to change it (decision 0014). */
function BlenderInstallation() {
  const b = useApp((s) => s.blender);
  const report = b.report;
  const saved = !!report?.configured && report.configured_exists;
  const current = b.check && b.check.path === b.path ? b.check : null;
  const usable = !!current && ["passed", "warning"].includes(current.status);
  const writes = usable && current.change === "write";
  const canSave = writes && (!current.rerender || b.confirmRerender) && !b.saving && !b.checking;
  const status = !report ? null : saved ? { tone: "success" as const, label: "Saved", text: `${report.configured} · in ${report.config_file}` }
    : report.configured ? { tone: "fault" as const, label: "Missing", text: report.configured }
    : report.used ? { tone: "warning" as const, label: "Not saved", text: "Blender was found but isn’t saved, so the speed test can’t use it. Check it, then save it." }
    : { tone: "warning" as const, label: "Not found", text: "No Blender was found on this computer. New 3D assets can’t be processed until one is saved." };
  return (
    <Card id="blender-card" title="Blender installation" help="Assetarium runs Blender in the background, with scripts and add-ons off, to inspect 3D files, render their previews and test render speed. The chosen executable is saved in config.local.toml.">
      {!report || !status ? <SkeletonLines lines={2} /> : (
        <>
          <p id="blender-status" className="flex min-w-0 flex-wrap items-center gap-2 text-[13px]" data-status={status.label}>
            <Badge tone={status.tone}>{status.label}</Badge>
            <span className="min-w-0 break-all">{status.text}</span>
          </p>
          {b.editing ? (
            <>
              <BlenderPicker idPrefix="settings" report={report} path={b.path} check={b.check} checking={b.checking} confirmRerender={b.confirmRerender}
                saveNote="Save writes it to config.local.toml. Process assets and the speed test use it right away; no restart needed."
                onPath={(path) => updateBlenderInstallation({ path, confirmRerender: false })} onConfirm={(checked) => updateBlenderInstallation({ confirmRerender: checked })}
                onCheck={() => void checkBlenderInstallation()} onCancel={() => void cancelBlenderCheck()} onChoose={() => void chooseBlenderInstallation()} />
              {(writes || saved) && (
                <div className="flex flex-wrap items-center gap-3">
                  {writes && <Button id="save-blender" disabled={!canSave} onClick={() => void saveBlenderInstallation()}>{b.saving ? "Saving…" : "Save Blender"}</Button>}
                  {saved && <Button variant="secondary" id="keep-blender" disabled={b.saving} onClick={() => updateBlenderInstallation({ editing: false })}>Keep the saved Blender</Button>}
                </div>
              )}
            </>
          ) : (
            <>
              <div className="flex flex-wrap items-center gap-3">
                {b.checking ? (
                  <Button variant="secondary" id="settings-cancel-blender" onClick={() => void cancelBlenderCheck()}>Cancel check</Button>
                ) : (
                  <Button variant="secondary" id="settings-check-blender" onClick={() => void checkBlenderInstallation(report.configured)}>Check Blender</Button>
                )}
                <Button variant="secondary" id="change-blender" disabled={b.checking} onClick={() => updateBlenderInstallation({ editing: true })}>Change Blender…</Button>
                <p role="status" aria-live="polite" className="flex items-center gap-2 text-[12.5px] text-muted-foreground">
                  {b.checking ? <><Spinner />Checking… (up to about 2 minutes)</> : current ? CHECK_STATUS[current.status] : ""}
                </p>
              </div>
              {current && <BlenderChecks check={current} />}
            </>
          )}
          {b.message && <Banner className="blender-message">{b.message}</Banner>}
        </>
      )}
    </Card>
  );
}

/** "See the speed test" for the Rendering and Search cards, whose Automatic choices come from it. */
function SpeedTestLink({ running }: { running?: boolean }) {
  return (
    <button type="button" className="speed-test-link w-fit text-[12.5px] font-medium text-primary hover:underline"
      onClick={() => document.getElementById("speed-test-card")?.scrollIntoView({ behavior: "smooth", block: "start" })}>
      {running ? "Speed test running…" : "See the speed test"}
    </button>
  );
}

/** One test for the render device, renders at a time and, on the CPU, search data threads (decision 0022). */
function SpeedTest() {
  const render = useApp((s) => s.render);
  const values = render.values;
  if (!values) return <Card id="speed-test-card" title="Speed test" help={SPEED_TEST_HELP}><SkeletonLines lines={2} /></Card>;
  const test = values.test;
  const running = operationActive(values.operation);
  const status = running ? values.operation.phase : render.message || (values.operation?.status === "complete" || values.operation?.status === "cancelled" ? values.operation.phase : "");
  return (
    <Card id="speed-test-card" title="Speed test" help={SPEED_TEST_HELP}>
      <div className="grid gap-3 text-[12.5px] leading-relaxed">
        {test && <p id="speed-test-when" className="text-muted-foreground">Last run: {new Date(test.utc).toLocaleString()}</p>}
        <div className="grid gap-1">
          <p className="font-medium">Rendering</p>
          {test ? (
            <ul id="render-test" className="grid gap-0.5">{test.results.map((r: Json) => <li key={r.key}>{renderTestLine(r, test.chosen)}</li>)}</ul>
          ) : (
            <p id="render-test" className="text-muted-foreground">{values.blender ? "Not tested yet." : "Save a Blender in Blender installation above to test render speed."}</p>
          )}
        </div>
        {values.search && (
          <div className="grid gap-1">
            <p className="font-medium">Search data</p>
            <p id="search-test">{searchTestText(values.search)}</p>
          </div>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-4">
        {running ? (
          <Button type="button" variant="secondary" id="render-test-cancel" disabled={render.busy} onClick={() => void renderTest("cancel")}>Cancel test</Button>
        ) : (
          <Button type="button" variant="secondary" id="render-test-start" disabled={render.busy || !values.blender} onClick={() => void renderTest("start")}>
            {test ? "Test again" : "Test speed"}
          </Button>
        )}
        <p id="render-test-message" role="status" aria-live="polite" className="text-[12.5px] leading-relaxed text-muted-foreground">{status}</p>
      </div>
    </Card>
  );
}

/** What the chosen search device needs installed; a missing runtime is why search cannot start. */
function SearchReadiness({ device }: { device: string }) {
  const check = useApp((s) => s.searchCheck);
  useEffect(() => {
    if (!check.devices && !check.checking && !check.error) void checkSearchReadiness();
  }, []);
  return (
    <div id="search-readiness-card" className="grid gap-3">
      <p className="font-medium text-[12.5px]">What is installed</p>
      {check.error ? <Banner tone="fault">{check.error}</Banner> : <ReadinessList id="search-readiness" items={check.checking ? undefined : check.devices?.[device]} />}
      <div className="flex flex-wrap items-center gap-4">
        <Button type="button" variant="secondary" id="search-readiness-check" disabled={check.checking} onClick={() => void checkSearchReadiness()}>Check again</Button>
        <p className="hint text-[12.5px] leading-relaxed text-muted-foreground">Run a missing command in a terminal in the Assetarium folder, then check again.</p>
      </div>
    </div>
  );
}

function General() {
  const general = useApp((s) => s.general);
  const render = useApp((s) => s.render.values);
  const [rendering, setRendering] = useState<RenderDraft>({ device: "auto", processes: "auto", memory: "" });
  useEffect(() => {
    if (render) setRendering({ device: render.device ?? "auto", processes: render.processes ? String(render.processes) : "auto", memory: render.memory_gib ? String(render.memory_gib) : "" });
  }, [render?.device, render?.processes, render?.memory_gib]);
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
  const [threads, setThreads] = useState("auto");
  const search = render?.search;
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
    setThreads(general.values.search_threads ? String(general.values.search_threads) : "auto");
  }, [general.values]);
  const disabled = general.loading || general.busy || !general.values;
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!event.currentTarget.reportValidity()) return;
    if (render && !(await saveRenderSettings(rendering.device, rendering.processes, rendering.memory))) return;
    void saveGeneralSettings(budget, formats, batch, { enabled, engine, server: { url, model } }, device, threads);
  };
  return (
    <div className="grid gap-5">
      <Card title="Appearance" help="Match Windows follows your system light or dark setting.">
        <AppearancePicker />
      </Card>
      <SetupCard />
      <BlenderInstallation />
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
          <SearchReadiness device={device} />
          {device === "cpu" && search && (
            <div id="search-threads-field" className="grid gap-2">
              <SelectField id="search-threads" label="CPU threads for search data" value={threads} onChange={setThreads} disabled={disabled} className="w-64"
                options={[["auto", `Automatic (${search.test ? search.test.chosen : search.cpu_threads})`],
                  ...Array.from({ length: Math.max(search.cpu_threads, Number(threads) || 0) }, (_, i): [string, string] => [String(i + 1), String(i + 1)])]} />
              <p className="hint max-w-[640px] text-[12.5px] leading-relaxed text-muted-foreground">{SEARCH_THREADS_HELP}</p>
              <p id="search-threads-now" className="text-[12.5px] leading-relaxed">{searchThreadsText(search)}</p>
              <SpeedTestLink running={operationActive(render?.operation)} />
            </div>
          )}
        </Card>
        <Rendering draft={rendering} onDraft={setRendering} disabled={disabled} />
        <SpeedTest />
        <div className="flex flex-wrap items-center gap-4">
          <Button type="submit" id="save-general-settings" disabled={disabled}>Save</Button>
          <p id="general-settings-message" role="status" aria-live="polite" className="text-[12.5px] leading-relaxed text-muted-foreground">{general.message}</p>
        </div>
      </form>
    </div>
  );
}

export function Settings({ tab = "general" }: { tab?: SettingsTab }) {
  return (
    <div id="settings-view" className="h-full overflow-y-auto overscroll-contain px-8 pb-12 scroll-thin">
      <div className="mx-auto grid max-w-[1120px] gap-6">
        <h1 id="settings-title" tabIndex={-1} className="text-[26px] font-semibold outline-none">Settings</h1>
        {/* General is the only section: library folders live in the Asset sources tab (decision 0023). */}
        <section id="general-panel" aria-labelledby="settings-title" data-tab={tab}><General /></section>
      </div>
    </div>
  );
}
