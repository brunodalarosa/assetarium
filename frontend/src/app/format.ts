import type { Json } from "./api";

export const VIEWS: Record<string, string> = { three_quarter: "Three-quarter", front: "Front", side: "Side", image: "2D image" };

/** Search modes keep their backend values; labels use the handoff wording. */
export const MODES: [string, string][] = [
  ["combined", "Name + description + image"],
  ["keyword_description", "Name + description"],
  ["keyword", "Exact keywords"],
  ["description", "Visual description"],
  ["image", "Text → image"],
  ["reference", "Pilot preview reference"],
];
export const modeLabel = (mode: string) => MODES.find(([value]) => value === mode)?.[1] ?? mode;
export const LIMITS = ["5", "10", "20", "30", "40"];

export function packName(value: string | undefined | null) {
  return (value || "").replace(/^kenney_/, "Kenney · ").replace(/^quaternius_/, "Quaternius · ").replaceAll("_", " ").replaceAll("-", " ");
}
export function display(value: unknown) {
  return value === null || value === undefined ? "Unknown" : typeof value === "object" ? JSON.stringify(value, null, 2) : String(value);
}
export function plural(n: number, one: string, many: string) {
  return `${Number(n).toLocaleString()} ${n === 1 ? one : many}`;
}
export function formatLabel(format: string) {
  return format === "gltf" ? "glTF / GLB" : format.toUpperCase();
}

const relativeTime = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
export function ago(utc: string | undefined) {
  const seconds = (Date.parse(utc || "") - Date.now()) / 1000;
  if (!Number.isFinite(seconds)) return "";
  for (const [unit, size] of [["day", 86400], ["hour", 3600], ["minute", 60]] as const)
    if (Math.abs(seconds) >= size) return relativeTime.format(Math.round(seconds / size), unit);
  return "just now";
}
export function elapsed(seconds: number | undefined) {
  if (!seconds) return "";
  const minutes = Math.round(seconds / 60);
  return minutes < 1 ? `${seconds} s` : minutes < 60 ? `${minutes} min` : `${Math.floor(minutes / 60)} h ${minutes % 60} min`;
}

export function hasDescription(item: Json) {
  return !item.caption_faulty && !["pending", undefined].includes(item.caption_status);
}

/** Card meta line from measured facts: "GLB · 1,248 tris", or "PNG · 512 × 512" for images. */
export function cardMeta(item: Json, card?: Json) {
  const formats: string[] = item.formats || [];
  const format = (card?.format || (formats.length === 1 ? formats[0] : "") || "").toUpperCase();
  const fact =
    item.asset_type === "image"
      ? card?.width ? `${card.width} × ${card.height}` : null
      : typeof card?.triangles === "number" ? `${card.triangles.toLocaleString()} tris` : null;
  const extra = !card?.format && formats.length > 1 ? formats.map((f) => f.toUpperCase()).join(" / ") : null;
  return [format || extra, fact].filter(Boolean).join(" · ");
}

export function operationActive(operation: Json) {
  return ["queued", "scanning", "processing", "publishing", "cancelling", "verifying"].includes(operation?.status);
}
export function describeActive(source: Json) {
  return source.operation?.operation === "describe" && operationActive(source.operation);
}

export function sourceMessage(source: Json) {
  if (source.scan_fault) return source.scan_fault;
  if (source.processing_paused) return "Processing paused. Select formats in Settings → General to resume.";
  if (!source.scanned) return "Waiting for the source scan. Assets must be processed before they appear in searches.";
  if (source.needs_processing) return `${source.pending || 0} ${(source.pending || 0) === 1 ? "asset needs" : "assets need"} processing or publication.`;
  if (source.failed) return "Import finished. Recorded failures are listed in the importing failures report.";
  if (source.skipped_formats && source.eligible_assets === 0) return "No assets match the selected processing formats. Existing results remain available.";
  if (source.skipped_formats) return "Selected formats are up to date. Other assets remain scanned and saved.";
  return "Up to date and published.";
}

export function descriptionSummary(source: Json) {
  const d = source.descriptions;
  if (!d) return "Description counts appear after scanning.";
  const parts = [
    d.complete && plural(d.complete, "description", "descriptions") + " written",
    d.missing && `${Number(d.missing).toLocaleString()} missing`,
    d.failed && `${Number(d.failed).toLocaleString()} failed`,
  ].filter(Boolean);
  return parts.length ? parts.join(" · ") : d.unavailable ? "Descriptions can be generated after assets are processed." : "No assets to describe.";
}

export function descriptionBlocked(source: Json) {
  const d = source.descriptions || {};
  if (!source.enabled) return "Enable this source in Settings → Asset sources to generate descriptions.";
  if (source.processing_paused) return "Processing is paused. Select formats in Settings → General to generate descriptions.";
  if (operationActive(source.operation)) return "Available when the current operation for this source finishes.";
  if (!d.missing) return d.failed ? "Nothing left to generate. Failed descriptions are recorded and not retried." : "Nothing to generate right now.";
  return "";
}

export const DESCRIBE_RESULTS: Record<string, string> = {
  complete: "Last run finished.",
  complete_with_faults: "Last run finished; some descriptions failed and were recorded.",
  cancelled: "Last run was cancelled; finished descriptions were published.",
  faulty: "Last run stopped.",
  interrupted: "Last run was interrupted.",
};

export type Tone = "info" | "success" | "warning" | "fault";
export function notificationContent(item: Json): { tone: Tone; title: string; body: string } {
  if (item.kind === "collection_changed")
    return {
      tone: "info",
      title: item.change === "created" ? `Agent created “${item.collection_name}”` : `Agent updated “${item.collection_name}”`,
      body: `${item.summary} The collection now holds ${plural(item.asset_count || 0, "asset", "assets")}.`,
    };
  if (item.kind === "setup_proposal")
    return { tone: "warning", title: "Your agent proposes a Blender executable", body: `Blender ${item.version} at ${item.path}. Nothing is saved until you apply it.` };
  if (item.kind === "setup_changed") {
    const changes = (item.changes || []).map((change: Json) => change.label);
    return {
      tone: "info",
      title: item.finished ? "Your agent finished setup" : "Your agent changed setup",
      body: `${changes.length ? "Changed: " + changes.join(", ") + "." : "No values changed."} You can review and change every value.`,
    };
  }
  if (item.kind === "descriptions_ready")
    return {
      tone: "info",
      title: "Descriptions ready to generate",
      body: `${plural(item.missing, "asset has", "assets have")} no description yet. They are already searchable by name and image; descriptions improve text search.`,
    };
  const written = plural(item.written || 0, "description", "descriptions") + " written";
  const remaining = item.remaining ? ` · ${Number(item.remaining).toLocaleString()} still missing` : "";
  switch (item.outcome) {
    case "complete":
      return { tone: "success", title: "Descriptions finished", body: `${written}${item.elapsed_seconds ? " in " + elapsed(item.elapsed_seconds) : ""}. They are published and used by search.` };
    case "complete_with_failures":
      return { tone: "warning", title: "Descriptions finished with failures", body: `${written} · ${Number(item.failed).toLocaleString()} failed. Failed descriptions are recorded and not retried; those assets stay searchable by name and image.` };
    case "cancelled":
      return { tone: "info", title: "Description run cancelled", body: `${written} and published${remaining}.` };
    case "stopped":
      return { tone: "fault", title: "Description run stopped", body: `${item.reason || "The run stopped."} ${written} and published${remaining}.` };
    default:
      return { tone: "fault", title: "Description run interrupted", body: `${item.reason || "The run stopped unexpectedly."} Finished descriptions are saved.` };
  }
}
export const notificationKey = (item: Json) => item.id + "@" + item.created_utc;

/* Setup and Settings → General share this copy (decision 0014). */
export const BUDGET_HELP =
  "The budget caps the disk space Assetarium itself uses: everything in its folder (code, Python environments and caches, project-local models, generated data, logs and scratch) plus each source’s metadata-lal folder, counting hard-linked files once. Your original assets and models in a shared folder outside Assetarium don’t count. Process assets and Generate descriptions measure before they start and after each stage; at the budget they stop and keep finished work. One stage can go past it before the run stops.";
export const DESCRIPTIONS_OFF =
  "Generate descriptions is hidden and no ready-to-generate notices appear. Descriptions already written stay stored and searchable; nothing is deleted or redone. Turn it back on any time.";
export const ENGINE_NOTE =
  "Different engines and models word descriptions differently. Descriptions you already have stay as they are; switching never redoes them. Where search by description and by image runs is a separate choice below.";
export const SEARCH_HELP =
  "Search by description and by image uses the EmbeddingGemma model on this computer, on an NVIDIA GPU or on the CPU. Both use the same model and precision, so results match closely; the GPU builds search data about ten times faster. After switching, run the search check again and Process assets to rebuild search data. Until then, names, filters and keyword search keep working.";
export const SEARCH_THREADS_HELP =
  "How many CPU threads build search data. More are faster until the processor is saturated; fewer leave the computer more responsive. Search results are identical at any number, so changing it never redoes work. Automatic uses the speed test's choice: the fewest threads within 3% of the fastest.";
/** "Now: 24 of 32 threads (fastest in the speed test)." */
export function searchThreadsText(search: Json) {
  return `Now: ${search.threads} of ${search.cpu_threads} threads (${search.reason}).`;
}
/** The speed test's search data line: each tested count, or why there is none. */
export function searchTestText(search: Json) {
  if (search.device !== "cpu") return "Search data runs on the GPU, so CPU threads are not tested.";
  if (!search.test) return "Not tested yet.";
  const tested = search.test.results.map((r: Json) => `${r.threads} threads ${r.seconds_per_image.toFixed(2)} s`).join(" · ");
  return `Per test image: ${tested} · ${search.test.chosen} threads chosen (the fewest within 3% of the fastest).`;
}
export const SPEED_TEST_HELP =
  "A short test on this computer with synthetic shapes and images, never your assets (about 2–3 minutes). It finds the faster render device, the CPU or a graphics card, and how many renders at a time help, and, when search runs on the CPU, how many CPU threads build search data fastest. It runs by itself when processing first needs it and again after Blender, the hardware or the search runtime changes; Automatic in Rendering and Search uses its results.";
export const RENDER_HELP =
  "Previews render in Blender. Automatic uses the speed test's fastest device and number of renders at a time. Your limits can lower that number or change how much memory rendering may use, for example more when the computer does nothing else overnight. Rendering never goes past the fastest tested number or the memory that is free, so a limit never makes it slower.";
const STOPPED: Record<string, string> = {
  "no gain": "more at a time did not help", slower: "more at a time was slower", memory: "more at a time would not fit in memory",
  "processor cores": "limited by processor cores", "tested every step": "", cancelled: "test cancelled",
};
/** One line per tested device: its best speed, or why it is not used. */
export function renderTestLine(result: Json, chosen: string) {
  if (!result.best) {
    if (result.stopped === "much slower than another device") return `${result.label}: much slower than another device; not used`;
    return `${result.label}: could not render${result.stopped?.startsWith("failed: ") ? " (" + result.stopped.slice(8) + ")" : ""}; not used`;
  }
  const why = STOPPED[result.stopped] ?? "";
  return `${result.label}: ${result.best.seconds_per_asset.toFixed(2)} s per test asset, ${result.best.processes} at a time${why ? ` (${why})` : ""}${result.key === chosen ? " · fastest" : ""}`;
}
export function renderNowText(plan: Json) {
  const count = `${plan.processes} ${plan.processes === 1 ? "render" : "renders"} at a time`;
  if (plan.reason === plan.best_reason) return `Now: ${plan.device}, ${count} (${plan.reason}).`;
  return `Now: ${plan.device}, ${count}, limited by ${plan.reason} (${plan.best_reason}: ${plan.best}).`;
}
export const BATCH_HELP =
  "How many assets the model describes in one call. Larger batches finish sooner but need more GPU memory. If memory runs out, the run stops safely: nothing is marked failed and those assets stay waiting, so you can lower the size and continue. Wording can differ slightly with which assets share a batch. Changing this never redoes finished descriptions.";
export function setupRecordText(record: Json | null | undefined) {
  if (!record?.state || record.state === "not_run") return "Setup has not been run on this computer.";
  const when = (value: string) => new Date(value).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  const by = record.by === "agent" ? " by an agent" : "";
  return record.state === "completed" ? `Setup completed ${when(record.completed_utc)}${by}.` : `Setup skipped ${when(record.skipped_utc)}${by}.`;
}
