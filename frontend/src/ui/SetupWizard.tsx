import { Check, CircleAlert, Copy, Cpu, FolderOpen, HardDrive, Monitor, TriangleAlert } from "lucide-react";
import { type ReactNode, useId } from "react";
import { Checkbox } from "@/components/beui/checkbox";
import { Switch } from "@/components/beui/switch";
import { cn } from "@/lib/utils";
import type { Json } from "../app/api";
import { BATCH_HELP, BUDGET_HELP, DESCRIPTIONS_OFF, formatLabel, plural } from "../app/format";
import {
  cancelBlenderCheck, checkBlender, chooseBlenderExecutable, copyText, finishSetup, goToSetupStep, measureSetupStorage,
  saveSetup, SETUP_STEPS, STEP_KEYS, type SetupStep, setupBack, setupNext, setupStepNeeded, skipSetup, stepChanged, updateSetupDraft, useApp,
} from "../app/store";
import { AgentPanel, SetByBadge, SetupPaths } from "./AgentSetup";
import { EngineFields } from "./EngineFields";
import { Badge, Banner, Button, Card, RadioCards, Spinner, TextField } from "./primitives";

const STEP_LABELS: Record<SetupStep, string> = {
  welcome: "Welcome", blender: "Blender", formats: "Formats", storage: "Storage budget",
  descriptions: "Descriptions", batch: "Batch size", review: "Review and finish",
};
const FORMAT_NOTES: [string, string, string][] = [
  ["fbx", "FBX", "Rigs and animation; common in Unity and Unreal."],
  ["gltf", "glTF / GLB", "Open format with PBR materials, rigs and animation."],
  ["obj", "OBJ", "Simple static meshes without skeletons or animation."],
];
const PRESETS = [25, 50, 100, 250];

function Paragraph({ children }: { children: ReactNode }) {
  return <p className="max-w-[680px] text-[13.5px] leading-relaxed text-muted-foreground">{children}</p>;
}

function CopyCommand({ command }: { command: string }) {
  return (
    <div className="flex min-w-0 items-center gap-2 rounded-xl bg-surface-2 py-1.5 pr-1.5 pl-3">
      <code className="min-w-0 flex-1 break-all font-mono text-[11.5px] text-foreground select-text">{command}</code>
      <Button variant="quiet" className="h-8 shrink-0 px-3 text-[12px]" onClick={() => void copyText(command, "Command copied. Run it in a terminal in the Assetarium folder.")}>
        <Copy className="size-3.5" aria-hidden />Copy
      </Button>
    </div>
  );
}

function Fact({ icon, label, children }: { icon: ReactNode; label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[auto_minmax(0,1fr)] items-start gap-3">
      <span className="mt-0.5 grid size-8 place-items-center rounded-lg bg-surface-2 text-muted-foreground" aria-hidden>{icon}</span>
      <div className="grid min-w-0 gap-0.5">
        <span className="text-[11.5px] text-muted-foreground">{label}</span>
        <span className="break-words text-[13px] text-foreground">{children}</span>
      </div>
    </div>
  );
}

function gpuText(gpu: Json) {
  if (!gpu) return "Detecting…";
  const nvidia = (gpu.nvidia || []).map((d: Json) => `${d.name}, ${d.vram_gib} GiB, driver ${d.driver}`);
  const other = (gpu.other || []).map((name: string) => `${name} (memory not detected)`);
  if (gpu.status === "faulty") return [gpu.reason, ...other].join(" · ");
  return [...nvidia, ...other].join(" · ") || "No GPU detected";
}

function Welcome() {
  const env = useApp((s) => s.setup.env);
  const blender = useApp((s) => s.setup.blender);
  const agentMode = useApp((s) => s.setup.agentMode);
  if (agentMode) return <AgentPanel />;
  return (
    <>
      <Paragraph>A few questions about this computer and how you’ll use Assetarium. Setup only records your choices, and checks Blender when you ask it to. It doesn’t download, install, process or start anything, and you can change every choice later in Settings → General.</Paragraph>
      <Card title="This computer" help="Detected without running any model. Nothing here is sent anywhere.">
        {!env ? (
          <p className="flex items-center gap-2 text-[13px] text-muted-foreground" role="status"><Spinner />Detecting this computer…</p>
        ) : (
          <div id="setup-environment" className="grid gap-4 sm:grid-cols-2">
            <Fact icon={<Monitor className="size-4" />} label="System">{env.os.name}</Fact>
            <Fact icon={<Cpu className="size-4" />} label="GPU">{gpuText(env.gpu)}</Fact>
            <Fact icon={<HardDrive className="size-4" />} label="Free space">{`${env.disk.free_gib.toLocaleString()} GiB free on ${env.disk.drive}`}</Fact>
            <Fact icon={<Check className="size-4" />} label="Blender">{blender ? `${plural(blender.candidates.length, "executable", "executables")} found` : "Checked on the next step"}</Fact>
          </div>
        )}
      </Card>
      <SetupPaths />
    </>
  );
}

function CheckList({ check }: { check: Json }) {
  return (
    <ul id="setup-blender-checks" className="grid gap-2" aria-label="Blender checks">
      {check.checks.map((item: Json) => (
        <li key={item.id} className="grid grid-cols-[auto_minmax(0,1fr)] items-start gap-2.5 text-[13px]" data-check={item.id} data-status={item.status}>
          <span className={cn("mt-0.5 grid size-5 place-items-center rounded-full", item.status === "passed" ? "bg-success-bg text-success" : item.status === "warning" ? "bg-warning-bg text-warning" : "bg-fault-bg text-fault")}>
            {item.status === "passed" ? <Check className="size-3" aria-hidden /> : item.status === "warning" ? <TriangleAlert className="size-3" aria-hidden /> : <CircleAlert className="size-3" aria-hidden />}
          </span>
          <span className="min-w-0 break-words">
            <span className="font-medium">{item.label}</span>
            <span className="sr"> — {item.status}</span>
            {item.detail && <span className="text-muted-foreground"> · {item.detail}</span>}
          </span>
        </li>
      ))}
    </ul>
  );
}

function BlenderStep() {
  const blender = useApp((s) => s.setup.blender);
  const check = useApp((s) => s.setup.check);
  const checking = useApp((s) => s.setup.checking);
  const draft = useApp((s) => s.setup.draft);
  const paths: string[] = (blender?.candidates || []).map((c: Json) => c.path);
  const options = (blender?.candidates || []).map((c: Json) => ({ value: c.path, title: c.path, detail: c.origin }));
  if (draft.blenderPath && !paths.includes(draft.blenderPath)) options.push({ value: draft.blenderPath, title: draft.blenderPath, detail: "chosen by you" });
  const current = check && check.path === draft.blenderPath ? check : null;
  const usable = current && ["passed", "warning"].includes(current.status);
  return (
    <>
      <Paragraph>Assetarium uses Blender in the background to inspect 3D files and render their previews. It starts Blender with scripts and add-ons turned off and never changes your Blender settings or your files. Without Blender you can still browse, search by name and keyword, and view previews that were already rendered; new 3D assets just can’t be processed.</Paragraph>
      <Card title="Blender executable" help={`Tested with Blender ${blender?.tested_version || "5.2"}; other versions show a warning but can be used.`}>
        {!blender ? (
          <p className="flex items-center gap-2 text-[13px] text-muted-foreground" role="status"><Spinner />Looking for Blender (nothing is run yet)…</p>
        ) : (
          <>
            {blender.configured && !blender.configured_exists && (
              <Banner tone="warning" role="status">The configured Blender ({blender.configured}, in {blender.config_file}) no longer exists. Choose one that does, then check it.</Banner>
            )}
            {options.length ? (
              <RadioCards id="setup-blender-choice" label="Blender executable" value={draft.blenderPath} onChange={(value) => updateSetupDraft({ blenderPath: value, confirmRerender: false })} options={options} />
            ) : (
              <Banner tone="info" role="status">
                No Blender was found. Install Blender {blender.tested_version} from the address below, then choose its {navigator.platform.startsWith("Win") ? "blender.exe" : "blender"} here, or skip this step.
                <span className="mt-2 block"><CopyCommand command={blender.download_url} /></span>
              </Banner>
            )}
            <div className="flex flex-wrap items-center gap-3">
              <Button variant="secondary" id="setup-choose-blender" disabled={checking} onClick={() => void chooseBlenderExecutable()}><FolderOpen className="size-4" aria-hidden />Choose executable…</Button>
              {checking ? (
                <Button variant="secondary" id="setup-cancel-blender" onClick={() => void cancelBlenderCheck()}>Cancel check</Button>
              ) : (
                <Button id="setup-check-blender" disabled={!draft.blenderPath} onClick={() => void checkBlender()}>Check Blender</Button>
              )}
              <p role="status" aria-live="polite" className="flex items-center gap-2 text-[12.5px] text-muted-foreground">
                {checking ? <><Spinner />Checking… (up to about 2 minutes)</> : current ? { passed: "Ready.", warning: "Works, with a warning.", failed: "This executable can’t be used.", cancelled: "Check cancelled." }[current.status as string] : draft.blenderPath ? "Not checked yet." : ""}
              </p>
            </div>
            {current && <CheckList check={current} />}
            {usable && current.change === "unchanged" && <p className="text-[12.5px] text-muted-foreground">This is already the Blender Assetarium uses; saving writes nothing.</p>}
            {usable && current.change === "write" && (
              <p className="text-[12.5px] text-muted-foreground">Saved to config.local.toml when you finish. Process assets uses it from its next run; no restart needed.</p>
            )}
            {usable && current.change === "write" && current.rerender > 0 && (
              <Banner tone="warning" role="status" className="grid gap-3">
                <span>Changing Blender marks {plural(current.rerender, "finished 3D inspection", "finished 3D inspections")} as needing processing again (the Blender path is part of each result’s fingerprint). Current previews stay visible until Process assets renders them again.</span>
                <Checkbox id="setup-confirm-rerender" label="I understand; render them again with this Blender" checked={draft.confirmRerender} onCheckedChange={(checked) => updateSetupDraft({ confirmRerender: checked })} />
              </Banner>
            )}
          </>
        )}
      </Card>
    </>
  );
}

function FormatsStep() {
  const info = useApp((s) => s.setup.info);
  const draft = useApp((s) => s.setup.draft);
  const hints: Json[] = info?.hints || [];
  const hint = hints.find((item) => item.id === draft.engineHint);
  return (
    <>
      <Paragraph>Processing inspects each 3D asset in Blender, renders its previews, measures geometry and builds search data. Scanning still lists every supported file, but assets that exist only in an unselected format stay unprocessed until you select it. .glb counts as glTF. 2D images are turned on per source in Settings → Asset sources. Changing formats later never deletes results or retries failures.</Paragraph>
      <Card title="Which engine do you target?" help="A suggestion only; you can change the checkboxes below.">
        <div role="radiogroup" aria-label="Target engine" id="setup-engine-hint" className="flex flex-wrap gap-2">
          {hints.map((item) => {
            const active = item.id === draft.engineHint;
            return (
              <button key={item.id} type="button" role="radio" aria-checked={active} data-value={item.id}
                onClick={() => updateSetupDraft({ engineHint: item.id, formats: [...item.formats] })}
                className={cn("h-9 rounded-full border px-4 text-[12.5px] font-medium transition-colors", active ? "border-primary bg-accent-soft text-accent-soft-foreground" : "border-border bg-surface text-foreground hover:bg-surface-2")}>
                {item.label}
              </button>
            );
          })}
        </div>
        <p id="setup-hint-reason" role="status" aria-live="polite" className="text-[12.5px] text-muted-foreground">
          {hint ? `Suggested: ${hint.formats.map(formatLabel).join(", ")} — ${hint.reason}` : "Choose one to preselect formats, or set them yourself."}
        </p>
      </Card>
      <Card title="Formats to process">
        <fieldset id="setup-formats" className="grid gap-3">
          <legend className="sr">Formats to process</legend>
          {FORMAT_NOTES.map(([value, label, note]) => (
            <Checkbox key={value} id={`setup-format-${value}`} label={label} description={note} checked={draft.formats.includes(value)}
              onCheckedChange={(checked) => updateSetupDraft({ formats: checked ? FORMAT_NOTES.map(([f]) => f).filter((f) => f === value || draft.formats.includes(f)) : draft.formats.filter((f) => f !== value) })} />
          ))}
        </fieldset>
        {!draft.formats.length && <p className="text-[12.5px] text-warning">With no format selected, processing stays paused.</p>}
      </Card>
    </>
  );
}

function StorageStep() {
  const storage = useApp((s) => s.setup.storage);
  const measuring = useApp((s) => s.setup.measuring);
  const env = useApp((s) => s.setup.env);
  const draft = useApp((s) => s.setup.draft);
  const recommended = storage?.recommended?.gib as number | undefined;
  const presets = [...new Set([...(recommended ? [recommended] : []), ...PRESETS])];
  const when = storage?.measured_utc ? new Date(storage.measured_utc).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }) : "";
  const free = storage?.free_gib ?? env?.disk.free_gib;
  return (
    <>
      <Paragraph>{BUDGET_HELP}</Paragraph>
      <Card title="Storage budget">
        <div className="grid gap-4 sm:grid-cols-2">
          <Fact icon={<HardDrive className="size-4" />} label="Free space">{free != null ? `${free.toLocaleString()} GiB on ${env?.disk.drive ?? "this drive"}` : "Measuring…"}</Fact>
          <Fact icon={<HardDrive className="size-4" />} label="Assetarium uses">
            {measuring ? "Measuring… (read only; can take a minute on a large library)" : storage?.allocated_gib != null
              ? `${storage.allocated_gib.toLocaleString()} GiB (${storage.status === "measured" ? "measured just now" : `measured ${when} before a processing run`})`
              : storage?.status === "faulty" ? storage.reason : "Not measured yet"}
          </Fact>
        </div>
        <div><Button variant="secondary" id="setup-measure-storage" disabled={measuring} onClick={() => void measureSetupStorage()}>{measuring ? "Measuring…" : "Measure now"}</Button></div>
        <div role="radiogroup" aria-label="Budget presets" id="setup-budget-presets" className="flex flex-wrap gap-2">
          {presets.map((gib) => {
            const active = draft.budget === String(gib);
            const tooBig = free != null && storage?.allocated_gib != null && gib > storage.allocated_gib + free;
            return (
              <button key={gib} type="button" role="radio" aria-checked={active} data-value={gib} disabled={tooBig}
                onClick={() => updateSetupDraft({ budget: String(gib) })}
                className={cn("h-9 rounded-full border px-4 text-[12.5px] font-medium tabular-nums transition-colors disabled:opacity-40", active ? "border-primary bg-accent-soft text-accent-soft-foreground" : "border-border bg-surface text-foreground hover:bg-surface-2")}>
                {gib === recommended ? `Recommended · ${gib} GiB` : `${gib} GiB`}
              </button>
            );
          })}
        </div>
        <TextField id="setup-budget" label="Budget (GiB, whole number)" type="number" min={1} max={1048576} step={1} value={draft.budget} onChange={(e) => updateSetupDraft({ budget: e.target.value })} className="w-56" />
        <p className="hint text-[12.5px] leading-relaxed text-muted-foreground">
          {recommended ? `Recommended: ${recommended} GiB — current use plus 20 GiB of room, rounded up${storage.recommended.limited_by_free_space ? ", limited to 80% of the free space" : ""}. ` : "Measure current use to get a recommendation. "}
          Runtimes and project-local models installed later count too (about 5 GiB of environments and 5.4 GiB of model files today).
        </p>
      </Card>
    </>
  );
}

function Readiness({ engine }: { engine: string }) {
  const env = useApp((s) => s.setup.env);
  const readiness = env?.engines?.[engine];
  if (!readiness) return <p className="flex items-center gap-2 text-[13px] text-muted-foreground" role="status"><Spinner />Checking what is installed…</p>;
  const items = [...readiness.items, ...readiness.search];
  return (
    <ul id="setup-readiness" className="grid gap-3" aria-label="Readiness">
      {items.map((item: Json) => (
        <li key={item.id} className="grid gap-1.5" data-item={item.id} data-ready={item.ready}>
          <span className="flex items-center gap-2 text-[13px]">
            <span className={cn("grid size-5 place-items-center rounded-full", item.ready ? "bg-success-bg text-success" : "bg-surface-2 text-muted-foreground")}>
              {item.ready ? <Check className="size-3" aria-hidden /> : <CircleAlert className="size-3" aria-hidden />}
            </span>
            <span className="font-medium">{item.label}</span>
            <span className="text-muted-foreground">{item.ready ? "Ready" : "Missing"}</span>
          </span>
          {!item.ready && item.detail && <span className="pl-7 text-[12px] text-muted-foreground">{item.detail}</span>}
          {item.command && <div className="pl-7"><CopyCommand command={item.command} /></div>}
        </li>
      ))}
    </ul>
  );
}

function DescriptionsStep() {
  const info = useApp((s) => s.setup.info);
  const draft = useApp((s) => s.setup.draft);
  return (
    <>
      <Paragraph>Descriptions are short texts an AI model on this computer writes for each asset from its previews: what it is, its shape, colors and style. They make text search better at finding things by appearance. They’re optional: without them you still have names, filters, keyword search and, where the search runtime is installed, image matching.</Paragraph>
      <Card title="Descriptions">
        <div className="flex h-10 items-center">
          <Switch checked={draft.descriptionsEnabled} onCheckedChange={(checked) => updateSetupDraft({ descriptionsEnabled: checked })} label="Generate descriptions" ariaLabel="Generate descriptions" />
        </div>
        {draft.descriptionsEnabled ? (
          <EngineFields engine={draft.engine} onEngine={(engine) => updateSetupDraft({ engine })} url={draft.serverUrl} onUrl={(serverUrl) => updateSetupDraft({ serverUrl })}
            model={draft.serverModel} onModel={(serverModel) => updateSetupDraft({ serverModel })} engines={info?.engines || []} idPrefix="setup" />
        ) : (
          <p id="setup-descriptions-off" className="text-[12.5px] leading-relaxed text-muted-foreground">{DESCRIPTIONS_OFF}</p>
        )}
      </Card>
      {draft.descriptionsEnabled && (
        <Card title="What is installed" help="Setup runs none of these. Copy a command and run it in a terminal in the Assetarium folder when you’re ready.">
          <Readiness engine={draft.engine} />
        </Card>
      )}
    </>
  );
}

function BatchStep() {
  const info = useApp((s) => s.setup.info);
  const env = useApp((s) => s.setup.env);
  const draft = useApp((s) => s.setup.draft);
  const recommended = env?.recommended_batch;
  return (
    <>
      <Paragraph>{BATCH_HELP}</Paragraph>
      <Card title="Assets per model call" help="Measured with the built-in engine on one RTX 5070 (12 GiB) with 20 assets; your GPU will differ.">
        <RadioCards id="setup-batch" label="Description batch size" value={draft.batch} onChange={(batch) => updateSetupDraft({ batch })}
          options={(info?.batch_benchmark || []).map((row: Json) => ({
            value: String(row.size),
            title: `${row.size}${row.size === 8 ? " (default)" : ""}`,
            detail: `About ${row.seconds_per_asset} s per asset · ${row.peak_gib} GiB peak GPU memory`,
            badge: recommended?.size === row.size ? <Badge tone="info">Recommended</Badge> : undefined,
          }))} />
        <p className="text-[12.5px] text-muted-foreground">
          {recommended ? `Recommended for your ${recommended.vram_gib} GiB GPU: ${recommended.size}.${recommended.may_not_fit ? " The model alone peaked at 4.7 GiB, so descriptions may not fit on this GPU." : ""}` : "No NVIDIA GPU was detected, so there is no recommendation."}
        </p>
      </Card>
    </>
  );
}

function summary(step: SetupStep, draft: Json, info: Json): string {
  if (draft.skipped.includes(step)) return "Skipped — keeps the current value";
  switch (step) {
    case "blender": return draft.blenderPath || "Not set (found automatically when processing)";
    case "formats": return draft.formats.length ? draft.formats.map(formatLabel).join(", ") : "None (processing paused)";
    case "storage": return draft.budget ? `${Number(draft.budget).toLocaleString()} GiB` : "Keeps the current value";
    case "descriptions": {
      if (!draft.descriptionsEnabled) return "Off (existing descriptions are kept)";
      const engine = (info?.engines || []).find((e: Json) => e.id === draft.engine);
      return draft.engine === "local-server" ? `On · local model server ${draft.serverUrl} · model ${draft.serverModel || "not set"}` : `On · ${engine ? `${engine.label} — ${engine.name}` : draft.engine}`;
    }
    case "batch": return setupStepNeeded("batch", draft) ? draft.batch : "Not used";
    default: return "";
  }
}

function Review() {
  const setup = useApp((s) => s.setup);
  const { draft, info, result } = setup;
  if (result) {
    return (
      <div className="grid gap-5">
        <h2 id="setup-saved-title" tabIndex={-1} className="text-[19px] font-semibold outline-none">Setup saved</h2>
        <ul className="grid gap-2 text-[13px]">
          <li className="flex items-center gap-2"><Check className="size-4 text-success" aria-hidden />Settings saved to Settings → General.</li>
          <li className="flex items-start gap-2" id="setup-blender-result">
            {result.blender.status === "faulty" ? <CircleAlert className="mt-0.5 size-4 shrink-0 text-fault" aria-hidden /> : <Check className="mt-0.5 size-4 shrink-0 text-success" aria-hidden />}
            <span>{result.blender.status === "saved" ? `Blender saved to ${result.blender.file}. Process assets uses it from its next run.`
              : result.blender.status === "faulty" ? `${result.blender.reason} Your other choices were saved.` : "Blender unchanged; nothing was written."}</span>
          </li>
        </ul>
        <Paragraph>Next: add a folder of assets in Settings → Asset sources, then run Process assets.</Paragraph>
        <div className="flex flex-wrap gap-3">
          <Button id="setup-go-sources" onClick={() => finishSetup("sources")}>Go to Asset sources</Button>
          <Button variant="secondary" id="setup-close" onClick={() => finishSetup("close")}>Close</Button>
        </div>
      </div>
    );
  }
  const steps = SETUP_STEPS.filter((step) => step !== "welcome" && step !== "review");
  const setBy = info?.set_by || {};
  const badge = (step: SetupStep) => {
    if (setup.baseline && stepChanged(step, draft, setup.baseline)) return <Badge tone="neutral">Changed by you</Badge>;
    const key = STEP_KEYS[step]?.find((name) => setBy[name]);
    return key ? <SetByBadge entry={setBy[key]} /> : null;
  };
  return (
    <>
      <Paragraph>{setup.baseline ? "These are the values saved now. Change anything you like, then Save; only what you change is recorded as set by you." : "Nothing is saved yet. Check your choices, then Save. You can change any of them later in Settings → General, or run setup again."}</Paragraph>
      <Card title="Your choices">
        <dl id="setup-summary" className="grid gap-3">
          {steps.map((step) => (
            <div key={step} className="grid grid-cols-[minmax(0,140px)_minmax(0,1fr)_auto] items-start gap-3 border-b border-border pb-3 last:border-0 last:pb-0">
              <dt className="text-[12.5px] text-muted-foreground">{STEP_LABELS[step]}</dt>
              <dd className="grid justify-items-start gap-1.5 break-words text-[13px]" data-step={step}>{summary(step, draft, info)}{badge(step)}</dd>
              <Button variant="quiet" className="h-8 px-3 text-[12px]" onClick={() => goToSetupStep(SETUP_STEPS.indexOf(step))} aria-label={`Change ${STEP_LABELS[step]}`}>Change</Button>
            </div>
          ))}
        </dl>
      </Card>
    </>
  );
}

const CONTENT: Record<SetupStep, () => ReactNode> = {
  welcome: Welcome, blender: BlenderStep, formats: FormatsStep, storage: StorageStep,
  descriptions: DescriptionsStep, batch: BatchStep, review: Review,
};
const TITLES: Record<SetupStep, string> = {
  welcome: "Set up Assetarium", blender: "Blender", formats: "Formats to process", storage: "Storage budget",
  descriptions: "Descriptions", batch: "Description batch size", review: "Review and finish",
};

export function SetupWizard() {
  const setup = useApp((s) => s.setup);
  const titleId = useId();
  if (!setup.open) return null;
  const step = SETUP_STEPS[setup.step];
  const Content = CONTENT[step];
  const saved = Boolean(setup.result);
  const agentWelcome = step === "welcome" && setup.agentMode;
  // Welcome offers its two paths as cards, so it needs no footer.
  return (
    <div id="setup-wizard" role="dialog" aria-modal="true" aria-labelledby={titleId} data-step={step} className="fixed inset-0 z-[45] flex bg-background text-foreground">
      <aside className="hidden w-[248px] shrink-0 flex-col gap-6 border-r border-border bg-surface px-5 py-7 md:flex">
        <div className="grid gap-1 px-2">
          <span className="text-[12px] font-medium tracking-wide text-muted-foreground uppercase">Assetarium</span>
          <span className="text-[17px] font-semibold">Setup</span>
        </div>
        <nav aria-label="Setup steps">
          <ol className="grid gap-1">
            {SETUP_STEPS.map((item, index) => {
              const needed = setupStepNeeded(item, setup.draft);
              const skipped = setup.draft.skipped.includes(item);
              const current = index === setup.step;
              return (
                <li key={item}>
                  <button type="button" disabled={saved} aria-current={current ? "step" : undefined} data-step={item} onClick={() => goToSetupStep(index)}
                    className={cn("flex w-full items-center gap-3 rounded-xl px-2 py-2 text-left text-[13px] transition-colors disabled:pointer-events-none", current ? "bg-accent-soft font-medium text-accent-soft-foreground" : "text-foreground hover:bg-surface-2", !needed && "text-subtle")}>
                    <span className={cn("grid size-6 shrink-0 place-items-center rounded-full border text-[11px] tabular-nums", current ? "border-primary bg-primary text-primary-foreground" : index < setup.step ? "border-border bg-surface-2" : "border-border")}>
                      {index < setup.step && !skipped && needed ? <Check className="size-3" aria-hidden /> : index + 1}
                    </span>
                    <span className="min-w-0 flex-1 truncate">{STEP_LABELS[item]}</span>
                    {skipped && <span className="text-[11px] text-muted-foreground">Skipped</span>}
                    {!needed && <span className="text-[11px]">Not needed</span>}
                  </button>
                </li>
              );
            })}
          </ol>
        </nav>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between gap-4 px-8 pt-6">
          <span className="text-[12px] text-muted-foreground tabular-nums md:invisible">Step {setup.step + 1} of {SETUP_STEPS.length}</span>
          {!saved && <Button variant="quiet" id="setup-skip-all" onClick={() => void skipSetup()}>Skip setup</Button>}
        </header>
        <main className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-8 pt-2 pb-10 scroll-thin">
          <div className="mx-auto grid max-w-[760px] gap-5">
            <h1 id="setup-step-title" tabIndex={-1} className="text-[26px] font-semibold outline-none"><span id={titleId}>{saved ? "Setup" : agentWelcome ? "Set up with your AI agent" : TITLES[step]}</span></h1>
            {setup.error && <Banner className="setup-error">{setup.error}</Banner>}
            {setup.loading ? <p className="flex items-center gap-2 text-[13px] text-muted-foreground" role="status"><Spinner />Loading current settings…</p> : <Content />}
          </div>
        </main>
        {!saved && step !== "welcome" && (
          <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-border bg-surface px-8 py-4">
            <Button variant="secondary" id="setup-back" disabled={setup.step === 0} onClick={setupBack}>Back</Button>
            <div className="flex flex-wrap items-center gap-3">
              {step !== "review" && <Button variant="quiet" id="setup-skip-step" onClick={() => setupNext(true)}>Skip step</Button>}
              {step === "review" ? (
                <Button id="setup-save" disabled={setup.saving || setup.loading} onClick={() => void saveSetup()}>{setup.saving ? "Saving…" : "Save"}</Button>
              ) : (
                <Button id="setup-next" disabled={setup.loading} onClick={() => setupNext(false)}>Next</Button>
              )}
            </div>
          </footer>
        )}
      </div>
    </div>
  );
}
