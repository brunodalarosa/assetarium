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
