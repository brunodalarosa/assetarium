import { Box, Copy, GripVertical, X } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { type ReactNode, useEffect, useLayoutEffect, useRef, useState } from "react";
import { Tabs, TabsList, TabsTrigger } from "@/components/beui/tabs";
import { SPRING_PANEL } from "@/lib/ease";
import { cn } from "@/lib/utils";
import type { Json } from "../app/api";
import { display, packName, plural, VIEWS } from "../app/format";
import {
  activeGridId, assetTags, type GridId, gridApi, gridVersion, copyText, getState, type InspectorTab, saveAssetTags, selectAsset,
  pushToast, setCollectionItem, startSelection,
  setInspectorOpen, setInspectorTab, setInspectorWidth, useApp,
} from "../app/store";
import { ImageViewer } from "./ImageViewer";
import { InspectorGhost, Skeleton, useShownWhile } from "./Loading";
import { Badge, Banner, Button, EvidenceBlock, IconButton, SelectField, Spinner } from "./primitives";

const MIN_WIDTH = 320;
const MAX_WIDTH = 960;
const MAIN_MIN = 420;

const ALPHA_TEXT: Record<string, string> = { none: "None (opaque)", binary: "Cut-out (fully transparent or opaque pixels)", partial: "Soft (partially transparent pixels)" };

function Section({ title, children, className }: { title: string; children: ReactNode; className?: string }) {
  return (
    <section className={cn("evidence grid gap-2.5 border-t border-border pt-5 first:border-t-0 first:pt-0", className)}>
      <h3 className="text-[14px] font-semibold text-foreground">{title}</h3>
      {children}
    </section>
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

/** The 3D still and interactive viewer from ui/interactive-preview.js, mounted per selection. */
function ModelPreview({ grid, assetId, result, view }: { grid: GridId; assetId: string; result: Json; view: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const gridVer = useApp((s) => gridVersion(s, grid));
  // Collection members come from the library or a source; the card's own generation is the one its preview must match.
  const version = grid === "collection" ? result.generation ?? null : gridVer;
  useEffect(() => {
    const p = result.payload, info = p.presentation || {};
    const container = ref.current;
    if (!container) return;
    const name = info.name || p.name || assetId;
    // The preview appends its still and dialog; each mount starts from an empty container.
    container.replaceChildren();
    window.LALPreview.mount(container, {
      assetId, name, sourceFormat: p.selected_source?.format, version,
      onSearch: () => document.getElementById({ library: "query", source: "source-grid", collection: "collection-query" }[grid])?.focus(),
      image: result.image, imageAlt: `${name} — ${VIEWS[view] || view} view`,
      imageReason: p.preview?.reason || p.reason || "Requested view unavailable; no substitute.",
    }, gridApi(grid));
    return () => {
      window.LALPreview.dispose();
      container.replaceChildren();
    };
  }, [grid, assetId, result, view, version]);
  return <div ref={ref} className="detail-preview" />;
}

function CaptionNotes({ info }: { info: Json }) {
  const quality = info.caption_quality || {};
  const notes = (quality.issues || []).filter((issue: Json) => issue.severity !== "fault");
  return (
    <Section title="Caption warnings & notes">
      {notes.length ? (
        <ul className="grid gap-3">
          {notes.map((issue: Json, index: number) => (
            <li key={index} className={cn("grid justify-items-start gap-1.5", issue.severity === "warning" && "caption-warning")}>
              <Badge tone={issue.severity === "warning" ? "warning" : "neutral"}>{issue.severity === "warning" ? "Warning" : "Review note"}</Badge>
              <Text>{issue.reason}</Text>
            </li>
          ))}
        </ul>
      ) : (
        <Text className="text-muted-foreground">{quality.status === "fault" ? "Caption unavailable; see recorded faults below." : "No caption review notes recorded."}</Text>
      )}
      {notes.length > 0 && <Hint>Notes and warnings do not make the description unusable. Owner review is {info.owner_review || "pending"}.</Hint>}
      <EvidenceBlock title="Original caption review evidence" value={{ classification: quality.classification, issues: quality.issues, original_findings: info.caption_faults }} />
    </Section>
  );
}

function Observations({ info, processed = true, image = false }: { info: Json; processed?: boolean; image?: boolean }) {
  return (
    <Section title="Generated observations">
      {info.observations ? (
        <>
          <Text>{info.observations.description || display(info.observations)}</Text>
          <Hint>Generated description · owner review {info.owner_review || "pending"}. Interpretations, separate from measured facts.</Hint>
        </>
      ) : (
        <Text className="text-muted-foreground">
          {info.caption_faulty
            ? "Description generation failed; the recorded fault is listed under Evidence."
            : !processed
              ? "Descriptions can be generated after the image is processed. It is still found by name."
              : `No description yet. Descriptions are optional: this ${image ? "image is searchable by name and by its pixels" : "asset is searchable by name and image"}. Generate them in Asset processing.`}
        </Text>
      )}
    </Section>
  );
}

function SuggestedUses({ info }: { info: Json }) {
  const uses: string[] = info.suggested_uses || [];
  return (
    <Section title="Suggested uses">
      {uses.length ? <Text>{uses.join(", ")}</Text> : <Text className="text-muted-foreground">No suggestions recorded.</Text>}
      <Hint>Suggestions are interpretations, not verified asset capabilities.</Hint>
    </Section>
  );
}

function SourcesTab({ result, image }: { result: Json; image: boolean }) {
  const p = result.payload, info = p.presentation || {};
  const licenses: Json[] = info.license_evidence || [];
  const dependencies: Json[] = p.dependencies || info.dependencies || [];
  return (
    <div className="grid gap-5">
      <Section title="Source location">
        {p.selected_source ? (
          <>
            <Text>{p.selected_source.format.toUpperCase()}{p.selected_source.variant ? ` · ${p.selected_source.variant} folder` : ""} · original file · verified hash</Text>
            {(p.source_variants || []).length > 1 && (
              <Hint>
                Also in this asset: {(p.source_variants as Json[]).filter((v) => v.variant !== p.selected_source.variant || v.format !== p.selected_source.format).map((v) => `${v.variant} (${String(v.format).toUpperCase()})`).join(" · ")}. Agents can ask for one by its folder name.
              </Hint>
            )}
            <code className="path block rounded-xl bg-surface-2 px-3 py-2.5 font-mono text-[11.5px] leading-relaxed break-all text-muted-foreground select-text">{p.selected_source.resolved_path}</code>
            <div><Button variant="secondary" className="h-9 px-4" onClick={() => void copyText(p.selected_source.resolved_path, "Source path copied. Asset files were not copied.")}><Copy className="size-3.5" aria-hidden />Copy source path</Button></div>
            <Hint>Original files stay in their source folder.</Hint>
            <EvidenceBlock title="Source SHA-256" value={p.selected_source.sha256} />
          </>
        ) : (
          <Text className="text-muted-foreground">No currently verified usable source. See recorded fault evidence.</Text>
        )}
      </Section>
      {!image && (
        <Section title="Dependencies">
          <Text className="text-muted-foreground">{dependencies.length ? `${plural(dependencies.length, "referenced file", "referenced files")} · ` : ""}{p.dependency_completeness || "Known references only; completeness is unknown."}</Text>
          <EvidenceBlock title="Dependency paths & referring source" value={dependencies} />
        </Section>
      )}
      <Section title="License evidence">
        <Text className="text-muted-foreground">{licenses.length ? plural(licenses.length, "license record", "license records") + " supplied with the source." : "No license evidence recorded."} Unknowns remain unknown.</Text>
        <EvidenceBlock title="Recorded license evidence" value={licenses} />
      </Section>
    </div>
  );
}

function EvidenceTab({ result, image }: { result: Json; image: boolean }) {
  const p = result.payload, info = p.presentation || {}, quality = info.caption_quality || {};
  const processed = info.processing?.inspection === "complete";
  const combined: Json[] = image
    ? [
        ...(info.source_faults || []),
        ...Object.entries(info.stage_faults || {}).filter(([stage]) => stage !== "caption").map(([stage, f]: [string, Json]) => ({ reason: stage + ": " + (f.reason || f.error || display(f)) })),
        ...(quality.issues || []).filter((i: Json) => i.severity === "fault"),
        ...(info.faults || []).filter((f: Json) => processed || !String(f.channel).startsWith("preview")),
      ]
    : [...(info.source_faults || []), ...(quality.issues || []).filter((i: Json) => i.severity === "fault"), ...(info.faults || []), ...(p.preview?.status === "faulty" ? [{ channel: "requested preview", reason: p.preview.reason }] : [])];
  const derivation = info.model_input?.derivation;
  return (
    <div className="grid gap-5">
      <CaptionNotes info={info} />
      <Section title="Recorded faults">
        {combined.length ? (
          <ul className="fault-list grid gap-1.5 rounded-xl bg-fault-bg px-4 py-3 text-[12.5px] leading-relaxed text-fault">
            {combined.map((fault, index) => <li key={index} className="break-words">{faultText(fault)}</li>)}
          </ul>
        ) : (
          <Text className="fault-list text-muted-foreground">No faults recorded for this asset.</Text>
        )}
        <EvidenceBlock title="Full fault & processing evidence" value={image ? { stages: info.stage_faults, caption: quality, runtime: info.faults, processing: info.processing } : { source: info.source_faults, caption: quality, runtime: info.faults, processing: info.processing }} />
      </Section>
      {(!image || info.technical?.width != null || info.observations) && (
        <Section title="Measurements & observations">
          {/* Unmeasured images have no measurement evidence to show. */}
          {(!image || info.technical?.width != null) && <EvidenceBlock title={image ? "Measurement evidence" : "Measurement & inspected-source evidence"} value={info.technical} />}
          {info.observations && <EvidenceBlock title="Structured generated observations" value={info.observations} />}
        </Section>
      )}
      {image && (
        <Section title="Search and description input">
          <Text className="text-muted-foreground">
            {derivation
              ? `Image search and descriptions read a derived copy${derivation.scale > 1 ? `, enlarged ${derivation.scale}× with hard pixel edges` : ""}${derivation.resample?.includes("lanczos-downscale") ? ", reduced to fit 1024 px" : ""}${derivation.background ? ` on a flat rgb(${derivation.background.join(", ")}) backdrop. The backdrop fills transparent pixels only; it is not a colour of this image.` : ". No backdrop was needed."}`
              : "No derived search input yet; the image is still found by name."}
          </Text>
          {derivation && <EvidenceBlock title="Derivation record" value={derivation} />}
        </Section>
      )}
      <Section title="Owner review">
        <dl className="grid gap-1 text-[13px] text-muted-foreground">
          <div><dt className="inline">Caption review: </dt><dd className="inline">{info.owner_review || "pending"}</dd></div>
          <div><dt className="inline">Artistic suitability: </dt><dd className="inline">{info.owner_artistic_approval || "pending"}</dd></div>
        </dl>
      </Section>
    </div>
  );
}

function imageFacts(t: Json): [string, unknown][] {
  const size = t.width == null ? "Unknown" : t.vector ? `${t.width} × ${t.height} canvas units` : `${t.width} × ${t.height} px`;
  return [
    ["Format", t.format?.toUpperCase()], ["Size", size],
    ["Transparency", t.alpha ? ALPHA_TEXT[t.alpha] + (t.alpha !== "none" && t.alpha_coverage != null ? ` · ${Math.round(t.alpha_coverage * 100)}% of pixels visible` : "") : undefined],
    ["Colours", t.color_count == null ? (t.vector ? "Not measured for vectors" : "More than 4,096") : t.color_count.toLocaleString()],
    ["Size class", t.size_class], ["Shape", t.aspect],
    ...(t.vector
      ? ([["Vector canvas", t.vector.canvas_basis === "content-bounds-v1" ? "No declared size; measured from visible content" : `Declared by the SVG (${t.vector.canvas_basis})`], ["Renderer", t.vector.renderer]] as [string, unknown][])
      : ([["Display hint", t.pixel_art_candidate ? "Small palette: shown with hard pixel edges" : "Smooth scaling"]] as [string, unknown][])),
  ];
}

function OverviewTab({ grid, result, assetId, format, view }: { grid: GridId; result: Json; assetId: string; format: string | null; view: string }) {
  const p = result.payload, info = p.presentation || {}, t = info.technical || {};
  const context = useApp((s) => s.context);
  const version = useApp((s) => gridVersion(s, grid));
  const formats: string[] = info.formats || [];
  const formatValue = format || p.selected_source?.format || formats[0] || "";
  const prefix = { library: "", source: "source-", collection: "collection-" }[grid];
  if (info.asset_type === "image") {
    const meta = info.type_metadata || {}, processed = info.processing?.inspection === "complete";
    const suggested = meta.suggested_purpose;
    return (
      <div className="grid gap-5">
        <div className="detail-preview">
          {processed ? (
            <ImageViewer key={assetId + formatValue} assetId={assetId} name={info.name || p.name || assetId} image={result.image} api={gridApi(grid)} version={version} native={[t.width, t.height]} pixelArt={Boolean(t.pixel_art_candidate)} vector={t.format === "svg"} />
          ) : (
            <div className="grid min-h-40 place-items-center rounded-2xl bg-thumb p-6 text-center text-[12.5px] text-muted-foreground">
              {({ pending: "This image has not been processed yet. Process this source in Asset processing to measure it and prepare image search.", failed: "This image could not be processed; the recorded fault is listed under Evidence.", unsupported: "This image is recognized but not supported yet; the reason is listed under Evidence." } as Record<string, string>)[info.processing?.inspection] || p.preview?.reason || "Image unavailable."}
            </div>
          )}
        </div>
        {formats.length > 1 && <SelectField id={prefix + "detail-format"} label="Source format" value={formatValue} onChange={(value) => void selectAsset(grid, assetId, value, "image", false)} options={formats.map((f): [string, string] => [f, f.toUpperCase()])} />}
        <Section title="Measured facts">
          <Hint>{info.scale}</Hint>
          {t.width != null ? <Facts entries={imageFacts(t)} /> : <Text className="text-muted-foreground">{processed ? "No measurements recorded." : "Measured when the image is processed successfully."}</Text>}
        </Section>
        <Section title="Purpose">
          <Facts entries={[["Recorded", "Generic image"], ["Suggested", suggested ? suggested.value + " — " + suggested.evidence : "None"]]} />
          <Hint>Suggestions come from folder names and are not verified. Search and filters treat every image the same way.</Hint>
          {meta.identical_content && <Text>Byte-identical to {plural(meta.identical_content.total, "other image", "other images")} in this source; kept separate.</Text>}
        </Section>
        <Observations info={info} processed={processed} image />
        <SuggestedUses info={info} />
        <TagsSection assetId={assetId} />
      </div>
    );
  }
  const selectedFormat = p.selected_source?.format;
  const views: string[] = (context?.views as string[] | undefined)?.filter((v) => v !== "image") || ["three_quarter", "front", "side"];
  return (
    <div className="grid gap-5">
      <ModelPreview grid={grid} assetId={assetId} result={result} view={view} />
      <div className="detail-controls grid grid-cols-2 gap-3">
        <SelectField id={prefix + "detail-format"} label="Source format" value={formatValue} onChange={(value) => void selectAsset(grid, assetId, value, view, false)} options={formats.map((f): [string, string] => [f, f.toUpperCase()])} />
        <SelectField id={prefix + "detail-view"} label="Preview view" value={view} onChange={(value) => void selectAsset(grid, assetId, format, value, false)} options={views.map((v): [string, string] => [v, VIEWS[v] || v])} />
      </div>
      <Button variant="secondary" className="w-full" disabled={!selectedFormat} onClick={() => void window.LALPreview.current?.start(false)}>Open interactive 3D preview</Button>
      <Section title="Measured facts">
        {selectedFormat && t.inspected_format && selectedFormat !== t.inspected_format && (
          <Banner tone="warning" role="note">{selectedFormat.toUpperCase()} is uninspected; the facts below describe {t.inspected_format.toUpperCase()}.</Banner>
        )}
        <Facts entries={[["Triangles", t.evaluated_instance_totals?.triangles?.toLocaleString?.()], ["Vertices", t.evaluated_instance_totals?.vertices?.toLocaleString?.()], ["Inspected format", t.inspected_format?.toUpperCase()], ["Physical scale", "Unknown"], ["Armatures", t.armatures?.length], ["Actions", t.actions?.length]]} />
        <Hint>{info.scale}</Hint>
      </Section>
      <Observations info={info} />
      <SuggestedUses info={info} />
      <TagsSection assetId={assetId} />
    </div>
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

function DetailBody({ grid }: { grid: GridId }) {
  const detail = useApp((s) => s[grid].detail);
  const tab = useApp((s) => s.inspector.tab);
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
      <div className="p-6"><Banner>Detail fault: {detail.error}</Banner></div>
    ) : (
      waiting ? <InspectorGhost /> : <span className="sr" role="status">Loading asset evidence…</span>
    );
  const result = detail.result, p = result.payload, info = p.presentation || {};
  const image = info.asset_type === "image";
  const tabs: [InspectorTab, string][] = [["overview", "Overview"], ["sources", "Sources"], ["evidence", "Evidence"]];
  const ids = (value: string) => ({ tab: `inspector-tab-${value}`, panel: `inspector-panel-${value}` });
  return (
    <div className="grid content-start gap-5 px-6 pb-8">
      <div className="detail-header grid gap-2">
        <h2 ref={headingRef} tabIndex={-1} className="text-[22px] leading-tight font-semibold break-words text-foreground outline-none">{info.name || p.name || detail.assetId}</h2>
        <div className="flex flex-wrap gap-1.5">
          <Badge>{image ? ((info.formats || []).length === 1 && info.formats[0] === "svg" ? "SVG image" : "2D image") : "3D model"}</Badge>
          <span className="pack inline-flex h-6 items-center text-[12px] text-muted-foreground">{packName(info.pack || p.pack || "")}</span>
          {detail.loading && <Spinner className="ml-1 size-3.5 self-center text-muted-foreground" />}
        </div>
        {p.status === "faulty" && <Banner className="state-banner mt-1">{p.reason}</Banner>}
      </div>
      {grid === "collection" && <CollectionEntry assetId={detail.assetId} />}
      <Tabs value={tab} onValueChange={(value) => setInspectorTab(value as InspectorTab)} variant="segment">
        <TabsList aria-label="Inspection sections" wrapperClassName="w-full" className="flex w-full rounded-full bg-surface-2 p-1 [--tabs-active-fg:var(--color-foreground)]">
          {tabs.map(([value, label]) => (
            <TabsTrigger key={value} value={value} id={ids(value).tab} aria-controls={ids(value).panel} wrapperClassName="flex-1" className="h-9 w-full rounded-full text-[12.5px] font-medium" indicatorClassName="rounded-full bg-surface shadow-[0_1px_3px_rgb(0_0_0/0.08)]">
              {label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
      {tabs.map(([value]) => (
        <div key={value} id={ids(value).panel} role="tabpanel" aria-labelledby={ids(value).tab} hidden={tab !== value} tabIndex={0} className="outline-none">
          {value === "overview" && <OverviewTab grid={grid} result={result} assetId={detail.assetId} format={detail.format} view={detail.view} />}
          {value === "sources" && <SourcesTab result={result} image={image} />}
          {value === "evidence" && <EvidenceTab result={result} image={image} />}
        </div>
      ))}
    </div>
  );
}

/** The right sidebar: asset inspection only, continuously resizable. */
export function Inspector() {
  const open = useApp((s) => s.inspector.open);
  const width = useApp((s) => s.inspector.width);
  const grid = useApp((s) => activeGridId(s));
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
              <span className="text-[14px] font-semibold text-foreground">Asset inspection</span>
              <IconButton label="Hide asset inspection" onClick={() => setInspectorOpen(false)} className="close-detail size-9">
                <X className="size-4" />
              </IconButton>
            </div>
            <div id="detail" className="detail-body flex min-h-0 flex-1 flex-col overflow-y-auto overscroll-contain scroll-thin" aria-busy={false}>
              <DetailBody grid={grid} />
            </div>
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  );
}

const getStateWidth = () => getState().inspector.width;
