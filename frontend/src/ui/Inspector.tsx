import { Box, ChevronRight, CircleAlert, Copy, GripVertical, SwatchBook, TriangleAlert, X } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { type ReactNode, useEffect, useLayoutEffect, useRef, useState } from "react";
import { Switch } from "@/components/beui/switch";
import { Tooltip } from "@/components/beui/tooltip";
import { EASE_OUT, SPRING_PANEL } from "@/lib/ease";
import { cn } from "@/lib/utils";
import type { Json } from "../app/api";
import { display, formatLabel, packName, plural, VIEWS } from "../app/format";
import {
  activeGridId, assetTags, type GridId, gridApi, copyText, getState, type InspectorSection, packProfileAction, saveAssetTags, selectAsset,
  markPreviewHintSeen, pushToast, setCollectionItem, startSelection, turnFormatOn,
  setInspectorOpen, setInspectorSection, setInspectorWidth, useApp,
} from "../app/store";
import { FolderPanel } from "./FolderPanel";
import { ImageViewer } from "./ImageViewer";
import { InspectorGhost, Skeleton, useShownWhile } from "./Loading";
import { Badge, Banner, Button, EvidenceBlock, IconButton, SelectField, Spinner } from "./primitives";

const MIN_WIDTH = 320;
const MAX_WIDTH = 960;
const MAIN_MIN = 420;

const ALPHA_TEXT: Record<string, string> = { none: "None (opaque)", binary: "Cut-out (fully transparent or opaque pixels)", partial: "Soft (partially transparent pixels)" };
const ALPHA_CHIP: Record<string, string> = { none: "Opaque", binary: "Cut-out", partial: "Soft transparency" };
const SECTION_TITLE: Record<InspectorSection, string> = { file: "File & license", geometry: "Geometry", image: "Image", record: "Processing record" };
const sectionId = (name: InspectorSection) => `inspector-section-${name}`;

function Section({ title, children, className }: { title: string; children: ReactNode; className?: string }) {
  return (
    <section className={cn("evidence grid gap-2.5 border-t border-border pt-5 first:border-t-0 first:pt-0", className)}>
      <h3 className="text-[14px] font-semibold text-foreground">{title}</h3>
      {children}
    </section>
  );
}
/** A titled group inside a collapsible section. */
function Group({ title, children, className }: { title: string; children: ReactNode; className?: string }) {
  return (
    <div className={cn("grid gap-2", className)}>
      <h4 className="text-[11.5px] font-medium text-muted-foreground">{title}</h4>
      {children}
    </div>
  );
}
function Facts({ entries }: { entries: [string, unknown][] }) {
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-3.5">
      {entries.map(([label, value]) => (
        <div key={label} className="min-w-0">
          <dt className="text-[11.5px] text-muted-foreground">{label}</dt>
          <dd className="mt-1 break-words text-[13.5px] text-foreground">{display(value)}</dd>
        </div>
      ))}
    </dl>
  );
}
const Hint = ({ children }: { children: ReactNode }) => <p className="text-[11.5px] leading-relaxed text-muted-foreground">{children}</p>;
const Text = ({ children, className }: { children: ReactNode; className?: string }) => <p className={cn("text-[13px] leading-relaxed text-foreground break-words", className)}>{children}</p>;

function faultText(fault: Json) {
  return typeof fault === "string" ? fault : fault.evidence || fault.reason || fault.issue || fault.kind || display(fault);
}

/** Every recorded fault of the asset: the fault line and the Processing record show this same list. */
function recordedFaults(result: Json, image: boolean): Json[] {
  const p = result.payload, info = p.presentation || {}, quality = info.caption_quality || {};
  const processed = info.processing?.inspection === "complete";
  return image
    ? [
        ...(info.source_faults || []),
        ...Object.entries(info.stage_faults || {}).filter(([stage]) => stage !== "caption").map(([stage, f]: [string, Json]) => ({ reason: stage + ": " + (f.reason || f.error || display(f)) })),
        ...(quality.issues || []).filter((i: Json) => i.severity === "fault"),
        ...(info.faults || []).filter((f: Json) => processed || !String(f.channel).startsWith("preview")),
      ]
    : [...(info.source_faults || []), ...(quality.issues || []).filter((i: Json) => i.severity === "fault"), ...(info.faults || []), ...(p.preview?.status === "faulty" ? [{ channel: "requested preview", reason: p.preview.reason }] : [])];
}

let revealing: InspectorSection | null = null;
const scrollToSection = (name: InspectorSection, reduce: boolean | null) =>
  document.getElementById(sectionId(name))?.scrollIntoView({ block: "start", behavior: reduce ? "auto" : "smooth" });
/** Open a section and bring it into view: where a fact chip or the fault line points. */
function reveal(name: InspectorSection, reduce: boolean | null) {
  // A closed section scrolls again once it has opened: until then the panel may be too short to reach it.
  revealing = getState().inspector.sections[name] ? null : name;
  setInspectorSection(name, true);
  requestAnimationFrame(() => requestAnimationFrame(() => scrollToSection(name, reduce)));
}

/** One of the panel's collapsible sections; it stays open or closed as the owner left it, app-wide. */
function Collapsible({ name, children }: { name: InspectorSection; children: ReactNode }) {
  const open = useApp((s) => s.inspector.sections[name]);
  const reduce = useReducedMotion();
  const id = sectionId(name);
  return (
    <section id={id} data-section={name} aria-labelledby={id + "-toggle"} className="inspector-section scroll-mt-3 border-t border-border">
      <h3>
        <button
          id={id + "-toggle"}
          type="button"
          aria-expanded={open}
          aria-controls={id + "-content"}
          onClick={() => setInspectorSection(name, !open)}
          className="-mx-1.5 flex min-h-12 w-[calc(100%+0.75rem)] items-center gap-2 rounded-lg px-1.5 text-left text-[13.5px] font-semibold text-foreground outline-none hover:bg-surface-2/70 focus-visible:ring-2 focus-visible:ring-ring/40"
        >
          <motion.span animate={{ rotate: open ? 90 : 0 }} transition={reduce ? { duration: 0 } : { type: "spring", duration: 0.35, bounce: 0.25 }} className="grid place-items-center text-muted-foreground">
            <ChevronRight className="size-4" aria-hidden />
          </motion.span>
          {SECTION_TITLE[name]}
        </button>
      </h3>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            id={id + "-content"}
            key="content"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={reduce ? { duration: 0 } : { height: { type: "spring", duration: 0.4, bounce: 0.18 }, opacity: { duration: 0.16, ease: EASE_OUT } }}
            onAnimationComplete={() => {
              if (revealing !== name) return;
              revealing = null;
              scrollToSection(name, reduce);
            }}
            className="overflow-hidden"
          >
            <div className="grid gap-4 pt-1 pb-5">{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}

/** A fact at a glance; it opens the section that holds the detail behind it. */
function FactChip({ to, hint, children }: { to: InspectorSection; hint: string; children: ReactNode }) {
  const reduce = useReducedMotion();
  return (
    <li>
      <Tooltip content={`${hint} · Opens ${SECTION_TITLE[to]}`} delay={350}>
        <button type="button" data-section={to} onClick={() => reveal(to, reduce)}
          className="fact-chip inline-flex h-7 items-center rounded-full bg-surface-2 px-2.5 text-[12px] text-foreground outline-none transition-colors hover:bg-accent-soft hover:text-accent-soft-foreground focus-visible:ring-2 focus-visible:ring-ring/40">
          {children}
        </button>
      </Tooltip>
    </li>
  );
}

/** The license as far as Assetarium can tell: only CC0 is recognized; anything else stays honest. */
function licenseFact(licenses: Json[]): [string, string] {
  if (!licenses.length) return ["No license file", "No license file was found with this asset"];
  if (licenses.every((l) => l.license_identifier === "CC0-1.0")) return ["CC0", "Creative Commons Zero, recognized in the license file supplied with it"];
  return ["License file", `${plural(licenses.length, "license file", "license files")} supplied with it; the license is not recognized automatically`];
}

function FactChips({ result, image }: { result: Json; image: boolean }) {
  const p = result.payload, info = p.presentation || {}, t = info.technical || {};
  const [license, licenseHint] = licenseFact(info.license_evidence || []);
  const chips: [InspectorSection, string, string][] = [];
  let caveat: string | null = null;
  if (image) {
    if (t.width != null) {
      chips.push(["image", t.vector ? `${t.width} × ${t.height} canvas units` : `${t.width} × ${t.height} px`, "Measured size"]);
      if (t.alpha) chips.push(["image", ALPHA_CHIP[t.alpha] || t.alpha, "Transparency"]);
      if (t.color_count != null) chips.push(["image", plural(t.color_count, "colour", "colours"), "Distinct colours"]);
    }
    const format = t.format || p.selected_source?.format || (info.formats || [])[0];
    if (format) chips.push(["file", formatLabel(format), "File format"]);
  } else {
    const format = p.selected_source?.format;
    // Measurements come from the inspected file; when another format is selected they name their source.
    const measured = format && t.inspected_format && format !== t.inspected_format ? t.inspected_format : null;
    const from = measured ? ` · ${formatLabel(measured)}` : "";
    const fromHint = measured ? `, measured in ${formatLabel(measured)}` : "";
    const triangles = t.evaluated_instance_totals?.triangles;
    if (triangles != null) chips.push(["geometry", `${triangles.toLocaleString()} tris${from}`, `Triangles${fromHint}`]);
    if (format) chips.push(["file", formatLabel(format), "Source format"]);
    const dependencies: Json[] = p.dependencies || info.dependencies || [];
    if (dependencies.length) chips.push(["file", plural(dependencies.length, "dependency file", "dependency files"), "Files this model refers to"]);
    if ((t.armatures || []).length) chips.push(["geometry", `Rigged${from}`, plural(t.armatures.length, "armature", "armatures") + fromHint]);
    const clips: Json[] = t.animation_clips || t.actions || [];
    if (clips.length) chips.push(["geometry", `Animated · ${plural(clips.length, "clip", "clips")}${from}`, `Animation clips${fromHint}`]);
    if (measured && chips.some(([to]) => to === "geometry")) caveat = `${formatLabel(format)} is uninspected; the measurements describe ${formatLabel(measured)}.`;
  }
  chips.push(["file", license, licenseHint]);
  return (
    <div className="grid gap-2">
      <ul className="fact-chips flex flex-wrap gap-1.5" aria-label="Facts">
        {chips.map(([to, label, hint]) => <FactChip key={label} to={to} hint={hint}>{label}</FactChip>)}
      </ul>
      {caveat && (
        <p role="note" className="format-caveat flex items-start gap-2 text-[12px] leading-relaxed text-warning">
          <TriangleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          <span>{caveat}</span>
        </p>
      )}
    </div>
  );
}

/** Shown only when something is recorded as faulty: the first reason, and where the rest is. */
function FaultLine({ faults }: { faults: Json[] }) {
  const reduce = useReducedMotion();
  return (
    <div role="alert" className="fault-line flex items-start gap-2.5 rounded-xl bg-fault-bg px-3.5 py-2.5 text-[12.5px] leading-relaxed text-fault">
      <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
      <span className="line-clamp-3 min-w-0 flex-1 break-words">
        {faultText(faults[0])}{faults.length > 1 && <span className="font-medium"> · {plural(faults.length - 1, "more fault", "more faults")}</span>}
      </span>
      <button type="button" onClick={() => reveal("record", reduce)} className="shrink-0 rounded font-medium underline-offset-2 outline-none hover:underline focus-visible:ring-2 focus-visible:ring-fault/40">Details</button>
    </div>
  );
}

/** The 3D still and interactive viewer from ui/interactive-preview.js, mounted per selection. */
function ModelPreview({ grid, assetId, result, view }: { grid: GridId; assetId: string; result: Json; view: string }) {
  const ref = useRef<HTMLDivElement>(null);
  // Every entry point uses the snapshot that actually produced this resolved detail.
  const version = result.generation ?? null;
  useEffect(() => {
    const p = result.payload, info = p.presentation || {};
    const container = ref.current;
    if (!container) return;
    const name = info.name || p.name || assetId;
    // The preview appends its still and dialog; each mount starts from an empty container.
    container.replaceChildren();
    window.LALPreview.mount(container, {
      assetId, name, sourceFormat: p.selected_source?.format, version, view,
      hintSeen: getState().previewHintSeen, onHintSeen: markPreviewHintSeen,
      // Before the live view loads, the view buttons switch the Blender stills.
      onView: (next: string) => void selectAsset(grid, assetId, p.selected_source?.format ?? null, next, false),
      onEscape: () => { setInspectorOpen(false); document.getElementById("toggle-inspector")?.focus(); },
      onRefresh: () => void selectAsset(grid, assetId, p.selected_source?.format ?? null, view, false, true),
      onSearch: () => document.getElementById({ library: "query", source: "source-grid", collection: "collection-query" }[grid])?.focus(),
      image: result.image, imageAlt: `${name} — ${VIEWS[view] || view} view`,
      imageReason: p.preview?.reason || p.reason || "Requested view unavailable; no substitute.",
    }, gridApi(grid, assetId));
    return () => {
      window.LALPreview.dispose();
      container.replaceChildren();
    };
  }, [grid, assetId, result, view, version]);
  return <div ref={ref} className="detail-preview" />;
}

function Preview({ grid, result, assetId, format, view }: { grid: GridId; result: Json; assetId: string; format: string | null; view: string }) {
  const p = result.payload, info = p.presentation || {}, t = info.technical || {};
  const formats: string[] = info.formats || [];
  const formatValue = format || p.selected_source?.format || formats[0] || "";
  const prefix = { library: "", source: "source-", collection: "collection-" }[grid];
  // The format choice only appears when there is a choice to make.
  const formatSelect = (nextView: string) => formats.length > 1 && (
    <SelectField id={prefix + "detail-format"} label="Source format" value={formatValue} onChange={(value) => void selectAsset(grid, assetId, value, nextView, false)} options={formats.map((f): [string, string] => [f, formatLabel(f)])} />
  );
  if (info.asset_type === "image") {
    const processed = info.processing?.inspection === "complete";
    return (
      <>
        <div className="detail-preview">
          {processed ? (
            <ImageViewer key={assetId + formatValue} assetId={assetId} name={info.name || p.name || assetId} image={result.image} api={gridApi(grid, assetId)} version={result.generation ?? null} native={[t.width, t.height]} pixelArt={Boolean(t.pixel_art_candidate)} vector={t.format === "svg"} />
          ) : (
            <div className="grid min-h-40 place-items-center rounded-2xl bg-thumb p-6 text-center text-[12.5px] text-muted-foreground">
              {({ pending: "This image has not been processed yet. Process this source in Asset processing to measure it and prepare image search.", failed: "This image could not be processed; the recorded fault is in the Processing record.", unsupported: "This image is recognized but not supported yet; the reason is in the Processing record." } as Record<string, string>)[info.processing?.inspection] || p.preview?.reason || "Image unavailable."}
            </div>
          )}
        </div>
        {formatSelect("image")}
      </>
    );
  }
  // The view buttons and display options sit on the canvas (ui/interactive-preview.js).
  return (
    <>
      <ModelPreview grid={grid} assetId={assetId} result={result} view={view} />
      {formatSelect(view)}
    </>
  );
}

/** The generated description and suggested uses, labeled as generated; caption notes open beside it. */
function Description({ info, image }: { info: Json; image: boolean }) {
  const [notesOpen, setNotesOpen] = useState(false);
  const notes: Json[] = ((info.caption_quality || {}).issues || []).filter((issue: Json) => issue.severity !== "fault");
  const warnings = notes.filter((issue) => issue.severity === "warning").length;
  const uses: string[] = info.suggested_uses || [];
  const processed = !image || info.processing?.inspection === "complete";
  const text = info.observations ? info.observations.description || display(info.observations) : null;
  const generated = info.description_shared_from
    ? `Shared from ${info.description_shared_from}: one description serves this variant group, so colors or materials may describe another variant.`
    : "Written from the previews during processing. It interprets how the asset looks; measured facts are in the sections below.";
  return (
    <section className="inspector-description grid gap-2.5" aria-labelledby="description-title">
      <div className="flex min-h-7 flex-wrap items-center gap-2">
        <h3 id="description-title" className="text-[14px] font-semibold text-foreground">Description</h3>
        {notes.length > 0 && (
          <button type="button" aria-expanded={notesOpen} aria-controls="caption-notes" onClick={() => setNotesOpen(!notesOpen)}
            className={cn("caption-notes-chip inline-flex h-6 items-center gap-1 rounded-md px-2 text-[11px] font-medium outline-none focus-visible:ring-2 focus-visible:ring-ring/40", warnings ? "bg-warning-bg text-warning" : "bg-surface-2 text-muted-foreground hover:text-foreground")}>
            {warnings > 0 && <TriangleAlert className="size-3" aria-hidden />}
            {[warnings && plural(warnings, "warning", "warnings"), notes.length - warnings && plural(notes.length - warnings, "review note", "review notes")].filter(Boolean).join(" · ")}
          </button>
        )}
        {text && (
          <Tooltip content={generated} delay={250}>
            <span tabIndex={0} className="generated-label ml-auto rounded px-1 text-[11px] text-muted-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring/40">{info.description_shared_from ? "Generated · shared" : "Generated"}</span>
          </Tooltip>
        )}
      </div>
      {notesOpen && (
        <ul id="caption-notes" className="caption-notes grid gap-3 rounded-xl bg-surface-2/60 px-3.5 py-3">
          {notes.map((issue, index) => (
            <li key={index} className={cn("grid justify-items-start gap-1.5", issue.severity === "warning" && "caption-warning")}>
              <Badge tone={issue.severity === "warning" ? "warning" : "neutral"}>{issue.severity === "warning" ? "Warning" : "Review note"}</Badge>
              <Text>{issue.reason}</Text>
            </li>
          ))}
        </ul>
      )}
      {text ? (
        <Text>{text}</Text>
      ) : (
        <Text className="text-muted-foreground">
          {info.caption_faulty
            ? "Description generation failed; the fault is in the Processing record."
            : !processed
              ? "Descriptions can be generated after the image is processed. It is still found by name."
              : `No description yet. This ${image ? "image is searchable by name and by its pixels" : "asset is searchable by name and image"}; generate descriptions in Asset processing.`}
        </Text>
      )}
      {uses.length > 0 && (
        <div className="suggested-uses grid gap-1.5">
          <h4 className="text-[11.5px] font-medium text-muted-foreground">Suggested uses</h4>
          <ul className="flex flex-wrap gap-1.5">
            {uses.map((use) => <li key={use} className="inline-flex h-7 items-center rounded-full border border-border px-2.5 text-[12px] text-foreground">{use}</li>)}
          </ul>
        </div>
      )}
    </section>
  );
}

function FileSection({ result, image }: { result: Json; image: boolean }) {
  const p = result.payload, info = p.presentation || {}, meta = info.type_metadata || {};
  const licenses: Json[] = info.license_evidence || [];
  const dependencies: Json[] = p.dependencies || info.dependencies || [];
  const source = p.selected_source;
  const others: Json[] = source ? (p.source_variants || []).filter((v: Json) => v.variant !== source.variant || v.format !== source.format) : [];
  const suggested = meta.suggested_purpose;
  return (
    <Collapsible name="file">
      <Group title="Source file">
        {source ? (
          <>
            <Text>{formatLabel(source.format)}{source.variant ? ` · ${source.variant} folder` : ""}</Text>
            <code className="path block rounded-xl bg-surface-2 px-3 py-2.5 font-mono text-[11.5px] leading-relaxed break-all text-muted-foreground select-text">{source.resolved_path}</code>
            <div><Button variant="secondary" className="h-9 px-4" onClick={() => void copyText(source.resolved_path, "Source path copied. Asset files were not copied.")}><Copy className="size-3.5" aria-hidden />Copy source path</Button></div>
            {others.length > 0 && (
              <Hint>Also in this asset: {others.map((v) => `${v.variant} (${formatLabel(v.format)}${v.usable === false ? `, unusable: ${v.reason}` : ""})`).join(" · ")}. Agents can ask for a usable one by its folder name.</Hint>
            )}
          </>
        ) : (
          <Text className="text-muted-foreground">No usable source file; the reason is in the Processing record.</Text>
        )}
      </Group>
      {!image && dependencies.length > 0 && (
        <Group title={`Dependencies · ${plural(dependencies.length, "file", "files")}`}>
          <ul className="dependency-list grid gap-1 rounded-xl bg-surface-2 px-3 py-2.5 font-mono text-[11.5px] leading-relaxed text-muted-foreground select-text">
            {dependencies.map((d, index) => (
              <li key={index} className="break-all">{d.path || d.resolved_path || display(d)}{(d.fault || d.status === "missing") && <span className="text-fault"> · {d.fault || "missing"}</span>}</li>
            ))}
          </ul>
        </Group>
      )}
      <Group title="License" className="license">
        {licenses.length ? licenses.map((l, index) => (
          <div key={l.path || index} className="grid gap-1.5">
            <Text>{l.license_identifier === "CC0-1.0" ? "CC0 1.0 (Creative Commons Zero)" : "Not recognized automatically"} <span className="text-muted-foreground">· {l.path}</span></Text>
            {l.excerpt && <pre className="license-excerpt max-h-48 overflow-auto whitespace-pre-wrap break-words rounded-xl bg-surface-2 p-3 font-mono text-[11px] leading-relaxed text-muted-foreground select-text scroll-thin">{l.excerpt}</pre>}
          </div>
        )) : <Text className="text-muted-foreground">No license file was found with this asset.</Text>}
      </Group>
      {image && (suggested || meta.identical_content) && (
        <Group title="Purpose">
          {suggested && <Text>Suggested: {suggested.value} — {suggested.evidence}</Text>}
          {suggested && <Hint>Suggestions come from folder names and are not verified. Search and filters treat every image the same way.</Hint>}
          {meta.identical_content && <Text>Byte-identical to {plural(meta.identical_content.total, "other image", "other images")} in this source; kept separate.</Text>}
        </Group>
      )}
    </Collapsible>
  );
}

function GeometrySection({ result }: { result: Json }) {
  const p = result.payload, t = p.presentation?.technical || {};
  const totals = t.evaluated_instance_totals || {};
  const armatures: Json[] = t.armatures || [];
  const clips: Json[] = t.animation_clips || t.actions || [];
  const selected = p.selected_source?.format;
  const differs = Boolean(selected && t.inspected_format && selected !== t.inspected_format);
  if (totals.triangles == null) return null;
  const entries: [string, unknown][] = [["Triangles", totals.triangles.toLocaleString()], ["Vertices", totals.vertices?.toLocaleString?.()]];
  if (armatures.length) entries.push(["Armatures", armatures.map((a) => (a.bones != null ? `${a.object} · ${plural(a.bones, "bone", "bones")}` : a.object || display(a))).join(", ")]);
  if (clips.length) entries.push(["Animations", clips.map((c) => c.name || display(c)).join(", ")]);
  if (differs) entries.push(["Inspected format", formatLabel(t.inspected_format)]);
  return (
    <Collapsible name="geometry">
      {differs && <Banner tone="warning" role="note">{formatLabel(selected)} is uninspected; these facts describe {formatLabel(t.inspected_format)}.</Banner>}
      <Facts entries={entries} />
    </Collapsible>
  );
}

function imageFacts(t: Json): [string, unknown][] {
  const size = t.width == null ? "Unknown" : t.vector ? `${t.width} × ${t.height} canvas units` : `${t.width} × ${t.height} px`;
  return [
    ["Format", t.format ? formatLabel(t.format) : undefined], ["Size", size],
    ["Transparency", t.alpha ? ALPHA_TEXT[t.alpha] + (t.alpha !== "none" && t.alpha_coverage != null ? ` · ${Math.round(t.alpha_coverage * 100)}% of pixels visible` : "") : undefined],
    ["Colours", t.color_count == null ? (t.vector ? "Not measured for vectors" : "More than 4,096") : t.color_count.toLocaleString()],
    ["Size class", t.size_class], ["Shape", t.aspect],
    ...(t.vector
      ? ([["Vector canvas", t.vector.canvas_basis === "content-bounds-v1" ? "No declared size; measured from visible content" : `Declared by the SVG (${t.vector.canvas_basis})`], ["Renderer", t.vector.renderer]] as [string, unknown][])
      : ([["Display hint", t.pixel_art_candidate ? "Small palette: shown with hard pixel edges" : "Smooth scaling"]] as [string, unknown][])),
  ];
}

function ImageSection({ result }: { result: Json }) {
  const info = result.payload.presentation || {}, t = info.technical || {};
  const derivation = info.model_input?.derivation;
  if (t.width == null) return null;
  return (
    <Collapsible name="image">
      <Facts entries={imageFacts(t)} />
      <Hint>{info.scale}</Hint>
      <Text className="search-input text-muted-foreground">
        {derivation
          ? `Image search and descriptions read a derived copy${derivation.scale > 1 ? `, enlarged ${derivation.scale}× with hard pixel edges` : ""}${derivation.resample?.includes("lanczos-downscale") ? ", reduced to fit 1024 px" : ""}${derivation.background ? ` on a flat rgb(${derivation.background.join(", ")}) backdrop. The backdrop fills transparent pixels only; it is not a colour of this image.` : ". No backdrop was needed."}`
          : "No derived search input yet; the image is still found by name."}
      </Text>
    </Collapsible>
  );
}

/** The raw record behind everything above: faults with their evidence, hashes and measurement JSON. */
function RecordSection({ result, image, faults }: { result: Json; image: boolean; faults: Json[] }) {
  const p = result.payload, info = p.presentation || {}, quality = info.caption_quality || {};
  const technical: Json = info.technical || {};
  const measured = image ? technical.width != null : Object.values(technical).some((value) => value != null);
  const derivation = info.model_input?.derivation;
  return (
    <Collapsible name="record">
      {faults.length > 0 && (
        <Group title={plural(faults.length, "recorded fault", "recorded faults")}>
          <ul className="fault-list grid gap-1.5 rounded-xl bg-fault-bg px-4 py-3 text-[12.5px] leading-relaxed text-fault">
            {faults.map((fault, index) => <li key={index} className="break-words">{faultText(fault)}</li>)}
          </ul>
        </Group>
      )}
      <div className="grid gap-1">
        <EvidenceBlock title="Fault & processing evidence" value={image ? { stages: info.stage_faults, caption: quality, runtime: info.faults, processing: info.processing } : { source: info.source_faults, caption: quality, runtime: info.faults, processing: info.processing }} />
        {p.selected_source?.sha256 && <EvidenceBlock title="Source SHA-256" value={p.selected_source.sha256} />}
        {measured && <EvidenceBlock title={image ? "Measurement evidence" : "Measurement & inspected-source evidence"} value={technical} />}
        {info.observations && <EvidenceBlock title="Structured observations" value={info.observations} />}
        {((quality.issues || []).length > 0 || (info.caption_faults || []).length > 0) && (
          <EvidenceBlock title="Caption review evidence" value={{ classification: quality.classification, issues: quality.issues, original_findings: info.caption_faults }} />
        )}
        {derivation && <EvidenceBlock title="Image derivation record" value={derivation} />}
      </div>
    </Collapsible>
  );
}

/** Owner tags: on the asset itself and shared by the whole app, unlike a collection's label. */
function TagsSection({ assetId }: { assetId: string }) {
  const known = useApp((s) => s.knownTags);
  const [tags, setTags] = useState<string[] | null>(null);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const listId = "tag-suggestions";
  useEffect(() => {
    let live = true;
    setTags(null);
    setError(null);
    assetTags(assetId).then((value) => live && setTags(value), (reason: Error) => live && setError(reason.message));
    return () => {
      live = false;
    };
  }, [assetId]);
  const save = async (next: string[]) => {
    const previous = tags;
    setTags(next);
    setError(null);
    try {
      setTags(await saveAssetTags(assetId, next));
    } catch (reason) {
      setTags(previous);
      setError((reason as Error).message);
    }
  };
  const add = () => {
    const values = draft.split(",").map((value) => value.trim().replace(/\s+/g, " ")).filter(Boolean);
    setDraft("");
    const current = tags || [];
    const fresh = values.filter((value) => !current.some((tag) => tag.toLowerCase() === value.toLowerCase()));
    if (fresh.length) void save([...current, ...fresh]);
  };
  return (
    <Section title="Tags" className="asset-tags">
      <Hint>Tags describe the asset everywhere in Assetarium and can be used as a search filter. Collection labels are separate.</Hint>
      {tags === null && !error && (
        <span className="flex gap-1.5" role="status">
          <span className="sr">Loading tags…</span>
          {[56, 72, 48].map((width, index) => <Skeleton key={width} wave={index * 60} className="ghost-enter h-7 rounded-full" style={{ width }} />)}
        </span>
      )}
      {tags && tags.length > 0 && (
        <ul className="flex flex-wrap gap-1.5" aria-label="Tags">
          {tags.map((tag) => (
            <li key={tag} className="inline-flex h-7 items-center gap-1 rounded-full bg-surface-2 pr-1 pl-2.5 text-[12px] text-foreground">
              {tag}
              <button type="button" aria-label={`Remove tag ${tag}`} onClick={() => void save(tags.filter((t) => t !== tag))} className="grid size-5 place-items-center rounded-full text-muted-foreground hover:bg-surface hover:text-foreground">
                <X className="size-3" />
              </button>
            </li>
          ))}
        </ul>
      )}
      {tags !== null && (
        <form className="flex gap-2" onSubmit={(event) => { event.preventDefault(); add(); }}>
          <label htmlFor="tag-input" className="sr">Add tags</label>
          <input
            id="tag-input"
            list={listId}
            value={draft}
            maxLength={120}
            onChange={(event) => setDraft(event.target.value)}
            placeholder={tags.length ? "Add another tag" : "Add a tag, e.g. fish"}
            className="h-9 min-w-0 flex-1 rounded-xl border border-border bg-surface px-3 text-[12.5px] outline-none hover:border-border-strong focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-ring/25"
          />
          <datalist id={listId}>{known.filter((t) => !tags.includes(t.tag)).map((t) => <option key={t.tag} value={t.tag} />)}</datalist>
          <Button type="submit" variant="secondary" className="h-9 px-3.5 text-[12.5px]" disabled={!draft.trim()}>Add</Button>
        </form>
      )}
      {error && <p role="alert" className="text-[12px] text-fault">{error}</p>}
    </Section>
  );
}

const AUTOSAVE_MS = 700;

/**
 * The asset's label and notes in the open collection. They save shortly after typing stops and when
 * a field is left; a pending edit is also saved if the panel closes or another asset is selected,
 * so nothing typed depends on a blur event arriving.
 */
function CollectionEntry({ assetId }: { assetId: string }) {
  const id = useApp((s) => s.collectionView.id);
  const name = useApp((s) => s.collectionView.name);
  const entry = useApp((s) => s.collectionView.members[assetId]);
  const [label, setLabel] = useState(entry?.label ?? "");
  const [notes, setNotes] = useState(entry?.notes ?? "");
  const [status, setStatus] = useState<{ tone: "info" | "fault"; text: string } | null>(null);
  const saved = useRef<{ label: string; notes: string }>({ label: entry?.label ?? "", notes: entry?.notes ?? "" });
  const pending = useRef<{ collection: string; patch: { label?: string; notes?: string } } | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const live = useRef(true);
  useEffect(() => {
    setLabel(entry?.label ?? "");
    setNotes(entry?.notes ?? "");
    saved.current = { label: entry?.label ?? "", notes: entry?.notes ?? "" };
    setStatus(null);
    // A different asset starts from its saved entry.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [assetId]);
  useEffect(() => {
    // Only a change made elsewhere (an agent, another view) replaces the fields; the echo of this
    // field's own save, or anything while typing, never overwrites what is being typed.
    if (pending.current) return;
    if ((entry?.label ?? "") !== saved.current.label) {
      saved.current = { ...saved.current, label: entry?.label ?? "" };
      setLabel(entry?.label ?? "");
    }
    if ((entry?.notes ?? "") !== saved.current.notes) {
      saved.current = { ...saved.current, notes: entry?.notes ?? "" };
      setNotes(entry?.notes ?? "");
    }
  }, [entry?.label, entry?.notes]);
  const save = async (collection: string, patch: { label?: string; notes?: string }) => {
    const key = Object.keys(patch)[0] as "label" | "notes";
    if ((patch[key] ?? "").trim() === saved.current[key]) return;
    saved.current = { ...saved.current, [key]: (patch[key] ?? "").trim() };
    if (live.current) setStatus({ tone: "info", text: "Saving…" });
    try {
      await setCollectionItem(collection, assetId, patch);
      if (live.current) setStatus({ tone: "info", text: "Saved" });
    } catch (reason) {
      if (live.current) setStatus({ tone: "fault", text: (reason as Error).message });
      else pushToast({ tone: "fault", title: "Label or notes not saved", body: (reason as Error).message });
    }
  };
  const flush = () => {
    clearTimeout(timer.current);
    const next = pending.current;
    pending.current = null;
    if (next) void save(next.collection, next.patch);
  };
  // Leaving this asset (another selection, closing the panel) saves what was typed.
  useEffect(() => {
    live.current = true;
    return () => {
      live.current = false;
      flush();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [assetId]);
  if (!id || !entry) return null;
  const edit = (patch: { label?: string; notes?: string }) => {
    if (pending.current && Object.keys(pending.current.patch)[0] !== Object.keys(patch)[0]) flush();
    pending.current = { collection: id, patch };
    clearTimeout(timer.current);
    timer.current = setTimeout(flush, AUTOSAVE_MS);
  };
  return (
    <section id="collection-entry" aria-label={`In ${name}`} className="grid gap-3 rounded-2xl border border-border bg-surface-2/60 p-4">
      <div className="flex items-center justify-between gap-2">
        <h3 className="min-w-0 truncate text-[13px] font-semibold">In “{name}”</h3>
        {status && <span role="status" className={cn("shrink-0 text-[11.5px]", status.tone === "fault" ? "text-fault" : "text-muted-foreground")}>{status.text}</span>}
      </div>
      <div className="grid gap-1.5">
        <label htmlFor="collection-label" className="text-xs text-muted-foreground">Label <span className="text-subtle">· only in this collection</span></label>
        <input
          id="collection-label"
          value={label}
          maxLength={60}
          onChange={(event) => { setLabel(event.target.value); edit({ label: event.target.value }); }}
          onBlur={flush}
          onKeyDown={(event) => event.key === "Enter" && (event.currentTarget as HTMLInputElement).blur()}
          placeholder="Where it is used, e.g. Coin pickup"
          className="h-10 rounded-xl border border-border bg-surface px-3 text-[13px] outline-none hover:border-border-strong focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-ring/25"
        />
      </div>
      <div className="grid gap-1.5">
        <label htmlFor="collection-notes" className="text-xs text-muted-foreground">Notes</label>
        <textarea
          id="collection-notes"
          value={notes}
          maxLength={4000}
          rows={4}
          onChange={(event) => { setNotes(event.target.value); edit({ notes: event.target.value }); }}
          onBlur={flush}
          placeholder="Implementation details for this project"
          className="resize-y rounded-xl border border-border bg-surface px-3 py-2.5 text-[13px] leading-relaxed outline-none hover:border-border-strong focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-ring/25"
        />
      </div>
      <Hint>Saved automatically as you type. Exports and agents receive the label and notes with this collection.</Hint>
    </section>
  );
}

/** A member that can no longer be read keeps its entry; inspection says why and still allows organizing it. */
function UnavailableDetail({ entry }: { entry: Json }) {
  return (
    <div className="grid content-start gap-5 px-6 pb-8">
      <div className="grid gap-2">
        <h2 tabIndex={-1} className="text-[22px] leading-tight font-semibold break-words">{entry.name || entry.asset_id}</h2>
        <span className="text-[12px] text-muted-foreground">{entry.source_name}</span>
      </div>
      <Banner tone="warning" role="note"><span id="unavailable-reason">Unavailable: {entry.reason}</span></Banner>
      <CollectionEntry assetId={entry.asset_id} />
      <Button variant="danger" onClick={() => startSelection(entry.asset_id)}>Remove from collection…</Button>
      <Hint>Asset ID {entry.asset_id}. Restoring or re-adding its source brings it back with this label and notes.</Hint>
    </div>
  );
}

/** A variant group (decision 0024): pick a variant, and choose whether its variants share one description. */
function Variants({ grid, group, assetId }: { grid: GridId; group: Json; assetId: string }) {
  const [busy, setBusy] = useState(false);
  const toggle = async () => {
    setBusy(true);
    await packProfileAction("separate_descriptions", group.key, "", { group: group.group, separate: !group.separate });
    setBusy(false);
    void selectAsset(grid, assetId, null, "three_quarter", false);
  };
  return (
    <div className="variant-group grid gap-2.5 rounded-2xl border border-border bg-surface-2/60 p-3.5">
      <div className="flex items-center gap-2 text-[12.5px] font-medium text-foreground">
        <SwatchBook className="size-4 text-muted-foreground" aria-hidden />{plural(group.variants.length, "variant", "variants")}
      </div>
      <div className="variant-chips flex flex-wrap gap-1.5" role="radiogroup" aria-label="Variants">
        {group.variants.map((v: Json) => (
          <button key={v.asset_id} type="button" role="radio" aria-checked={v.asset_id === assetId} title={v.name}
            onClick={() => v.asset_id !== assetId && void selectAsset(grid, v.asset_id, null, "three_quarter", false)}
            className={cn("h-7 min-w-8 rounded-full border px-2.5 text-[12px] transition-colors",
              v.asset_id === assetId ? "border-primary bg-accent-soft text-accent-soft-foreground" : "border-border text-muted-foreground hover:border-border-strong hover:text-foreground")}>
            {v.value}
          </button>
        ))}
      </div>
      {grid === "source" && (
        <div id="separate-descriptions" className="grid gap-1">
          <Switch checked={!!group.separate} disabled={busy} onCheckedChange={() => void toggle()} label="Generate separate descriptions for each variant" ariaLabel="Generate separate descriptions for each variant" />
          <Hint>{group.separate ? "Each variant is described on its own by Generate descriptions." : `Off: one description, from ${group.representative.name}, serves them all.`}</Hint>
        </div>
      )}
    </div>
  );
}

/** Shown, but made from a file whose format is off: the facts, and the one action that resolves it (P5). */
function FormatOff({ hold }: { hold: Json }) {
  const [busy, setBusy] = useState(false);
  const label = hold.format === "gltf" ? "glTF" : String(hold.format).toUpperCase();
  return (
    <Banner tone="warning" className="format-off grid gap-2">
      <span>{hold.reason}</span>
      <span>
        <Button variant="secondary" className="h-8 px-3" disabled={busy} onClick={() => { setBusy(true); void turnFormatOn(hold.format).finally(() => setBusy(false)); }}>
          {busy && <Spinner className="size-3.5" />}Turn {label} on
        </Button>
      </span>
    </Banner>
  );
}

function DetailBody({ grid }: { grid: GridId }) {
  const detail = useApp((s) => s[grid].detail);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const focusToken = detail?.focusToken ?? 0;
  const hasResult = Boolean(detail?.result);
  const waiting = useShownWhile(Boolean(detail && !detail.result && !detail.error && !detail.unavailable));
  useEffect(() => {
    if (focusToken && hasResult) headingRef.current?.focus();
  }, [focusToken, hasResult]);
  if (!detail)
    return (
      <div className="detail-empty grid flex-1 place-items-center content-center gap-4 px-8 pb-16 text-center">
        <span aria-hidden className="grid size-[72px] place-items-center rounded-2xl bg-surface-2 text-muted-foreground"><Box className="size-7" strokeWidth={1.5} /></span>
        <h2 className="text-[19px] font-semibold text-foreground">No asset selected</h2>
        <p className="max-w-[280px] text-[13px] leading-relaxed text-muted-foreground">Select an asset to inspect its preview, files and details.</p>
      </div>
    );
  if (detail.unavailable) return <UnavailableDetail entry={detail.unavailable} />;
  if (!detail.result)
    return detail.error ? (
      <div className="grid gap-3 p-6"><Banner tone={detail.stale ? "info" : "fault"}>{detail.stale ? "Inspection changed" : "Detail fault"}: {detail.error}</Banner>
        {detail.stale && <Button variant="secondary" onClick={() => void selectAsset(grid, detail.assetId, detail.format, detail.view, false, true)}>Refresh inspection</Button>}
      </div>
    ) : (
      waiting ? <InspectorGhost /> : <span className="sr" role="status">Loading asset evidence…</span>
    );
  const result = detail.result, p = result.payload, info = p.presentation || {};
  const image = info.asset_type === "image";
  const faults = recordedFaults(result, image);
  // One scroll, top to bottom: what is wrong, the asset itself, its facts, then the detail behind them.
  return (
    <div className="grid content-start gap-5 px-6 pb-8">
      <div className="detail-header grid gap-2">
        <h2 ref={headingRef} tabIndex={-1} className="text-[22px] leading-tight font-semibold break-words text-foreground outline-none">{info.name || p.name || detail.assetId}</h2>
        <div className="flex flex-wrap gap-1.5">
          <Badge>{image ? ((info.formats || []).length === 1 && info.formats[0] === "svg" ? "SVG image" : "2D image") : "3D model"}</Badge>
          <span className="pack inline-flex h-6 items-center text-[12px] text-muted-foreground">{packName(info.pack || p.pack || "")}</span>
          {detail.loading && <Spinner className="ml-1 size-3.5 self-center text-muted-foreground" />}
        </div>
      </div>
      {faults.length > 0 && <FaultLine faults={faults} />}
      {info.format_off && <FormatOff hold={info.format_off} />}
      {p.status === "faulty" && !faults.some((fault) => faultText(fault) === p.reason) && <Banner className="state-banner">{p.reason}</Banner>}
      <Preview grid={grid} result={result} assetId={detail.assetId} format={detail.format} view={detail.view} />
      <FactChips result={result} image={image} />
      {info.variant_group && <Variants grid={grid} group={info.variant_group} assetId={detail.assetId} />}
      {grid === "collection" && <CollectionEntry assetId={detail.assetId} />}
      <Description key={detail.assetId} info={info} image={image} />
      <TagsSection assetId={detail.assetId} />
      <div className="inspector-sections grid">
        <FileSection result={result} image={image} />
        {image ? <ImageSection result={result} /> : <GeometrySection result={result} />}
        <RecordSection result={result} image={image} faults={faults} />
      </div>
    </div>
  );
}

/** The right sidebar: asset inspection only, continuously resizable. */
export function Inspector() {
  const open = useApp((s) => s.inspector.open);
  const width = useApp((s) => s.inspector.width);
  const grid = useApp((s) => activeGridId(s));
  // On the Asset sources tab a folder, pack or library folder can be inspected too.
  const folder = useApp((s) => s.history[s.historyIndex].page === "sources" && s.sourcesView.panel === "folder");
  const reduce = useReducedMotion();
  const [available, setAvailable] = useState(() => window.innerWidth);
  const [dragging, setDragging] = useState(false);
  useLayoutEffect(() => {
    const update = () => setAvailable(window.innerWidth);
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);
  // The rail (96 px) and a usable results column always keep their room; on narrow
  // windows the panel floats over the results instead of squeezing them away.
  const overlay = available - 96 - MAIN_MIN < MIN_WIDTH;
  const max = overlay ? Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, available - 96 - 40)) : Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, available - 96 - MAIN_MIN));
  const shown = Math.min(Math.max(width, MIN_WIDTH), max);
  const startDrag = (event: React.PointerEvent<HTMLDivElement>) => {
    event.preventDefault();
    const startX = event.clientX, startWidth = shown;
    setDragging(true);
    const move = (e: PointerEvent) => setInspectorWidth(Math.min(max, Math.max(MIN_WIDTH, startWidth + startX - e.clientX)));
    const up = () => {
      setDragging(false);
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      setInspectorWidth(getStateWidth(), true);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };
  return (
    <AnimatePresence initial={false}>
      {open && (
        <motion.aside
          key="inspector"
          id="inspector"
          aria-label="Asset inspection"
          initial={reduce ? { opacity: 0 } : { opacity: 0, x: 24 }}
          animate={{ opacity: 1, x: 0 }}
          exit={reduce ? { opacity: 0 } : { opacity: 0, x: 24, transition: { duration: 0.16 } }}
          transition={SPRING_PANEL}
          style={{ width: shown + 24 }}
          className={cn("flex h-full shrink-0 pt-0 pr-4 pb-4 pl-6", overlay ? "absolute top-0 right-0 z-20 [&>div:last-child]:shadow-panel" : "relative", dragging && "select-none")}
        >
          <div
            role="separator"
            aria-orientation="vertical"
            aria-label="Resize asset inspection"
            aria-valuemin={MIN_WIDTH}
            aria-valuemax={max}
            aria-valuenow={shown}
            tabIndex={0}
            onPointerDown={startDrag}
            onKeyDown={(event) => {
              const delta = event.key === "ArrowLeft" ? 24 : event.key === "ArrowRight" ? -24 : 0;
              if (event.key === "Home" || event.key === "End") {
                event.preventDefault();
                setInspectorWidth(event.key === "Home" ? MIN_WIDTH : max, true);
              } else if (delta) {
                event.preventDefault();
                setInspectorWidth(Math.min(max, Math.max(MIN_WIDTH, shown + delta)), true);
              }
            }}
            className="group absolute top-0 bottom-4 left-0 flex w-6 cursor-col-resize items-center justify-center outline-none"
          >
            <GripVertical className={cn("size-4 text-subtle transition-colors group-hover:text-muted-foreground group-focus-visible:text-primary", dragging && "text-primary")} aria-hidden />
          </div>
          <div className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-[22px] border border-border bg-surface">
            <div className="flex h-[76px] shrink-0 items-center justify-between pr-4 pl-6">
              <span className="text-[14px] font-semibold text-foreground">{folder ? "Folder" : "Asset inspection"}</span>
              <IconButton label="Hide asset inspection" onClick={() => setInspectorOpen(false)} className="close-detail size-9">
                <X className="size-4" />
              </IconButton>
            </div>
            <div id="detail" className="detail-body flex min-h-0 flex-1 flex-col overflow-y-auto overscroll-contain scroll-thin" aria-busy={false}>
              {folder ? <FolderPanel /> : <DetailBody grid={grid} />}
            </div>
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  );
}

const getStateWidth = () => getState().inspector.width;
