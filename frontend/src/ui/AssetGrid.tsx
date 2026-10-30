import { Ban, Box, Check, CircleAlert, Clock, FileQuestion, FileText, FileX, Image as ImageIcon, Layers, Loader, Sparkles, TriangleAlert, Unlink } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { type CSSProperties, type KeyboardEvent, useEffect, useRef } from "react";
import { SPRING_PRESS } from "@/lib/ease";
import { cn } from "@/lib/utils";
import type { Json } from "../app/api";
import { Tooltip } from "@/components/beui/tooltip";
import { cardMeta, hasDescription, packName } from "../app/format";
import { type GridId, openAssetMenu, pathAction, pickAsset, requestThumb, selectAsset, type Thumb, toggleSelected, useApp } from "../app/store";

/** A library pack is an object on the Asset sources tab ({name}); elsewhere a folder key. */
const packLabel = (item: Json) => (item.pack && typeof item.pack === "object" ? item.pack.name : packName(item.pack));

/** Work states (decision 0023), each with a shape and a label so color is never the only signal. */
const STATE: Record<string, { icon: typeof Clock; label: string }> = {
  no_previews: { icon: Clock, label: "No previews yet" }, queued: { icon: Clock, label: "Queued" }, running: { icon: Loader, label: "Making previews" },
  blocked: { icon: Ban, label: "Blocked" }, failed: { icon: CircleAlert, label: "Recorded failure" }, missing: { icon: Unlink, label: "Missing" },
  excluded: { icon: FileX, label: "Excluded" },
};
const DESCRIPTION: Record<string, { icon: typeof FileText; label: string }> = {
  complete: { icon: FileText, label: "Described" }, failed: { icon: FileX, label: "Description failed" }, missing: { icon: FileQuestion, label: "No description yet" },
};

/** The icon strip over a card's preview: its state and overlays, with tooltips. */
function StateStrip({ item }: { item: Json }) {
  const icons: { icon: typeof Clock; label: string; tone?: string; spin?: boolean }[] = [];
  const state = STATE[item.state];
  if (state && item.state !== "ready") icons.push({ ...state, label: item.reason ? `${state.label}: ${item.reason}` : state.label,
    tone: item.state === "failed" ? "text-fault" : item.state === "blocked" ? "text-warning" : undefined, spin: item.state === "running" });
  const overlays = item.overlays || {};
  if (overlays.warning) icons.push({ icon: TriangleAlert, label: "Description warning", tone: "text-warning" });
  if (overlays.description && DESCRIPTION[overlays.description]) icons.push(DESCRIPTION[overlays.description]);
  if (overlays.collections) icons.push({ icon: Layers, label: `In ${overlays.collections} ${overlays.collections === 1 ? "collection" : "collections"}` });
  if (item.new) icons.push({ icon: Sparkles, label: "New since your last visit", tone: "text-primary" });
  if (!icons.length) return null;
  return (
    <span className="state-strip absolute top-3 right-3 z-10 flex gap-1" data-state={item.state}>
      {icons.map(({ icon: Icon, label, tone, spin }) => (
        <Tooltip key={label} content={label} delay={250}>
          <span role="img" aria-label={label} className={cn("grid size-6 place-items-center rounded-full bg-surface/90 shadow-sm backdrop-blur", tone)}>
            <Icon className={cn("size-3.5", spin && "animate-spin")} strokeWidth={2} />
          </span>
        </Tooltip>
      ))}
    </span>
  );
}

/** "No previews yet" is a designed state: the format glyph, the name and a quiet label, never a broken image. */
function NoPreview({ item }: { item: Json }) {
  const Icon = item.kind === "image" || item.kind === "material_texture" ? ImageIcon : Box;
  const label = item.state === "blocked" ? "Waiting for a fix" : item.state === "missing" ? "File not found" : item.state === "failed" ? "No usable preview"
    : item.reason === "Search data pending" ? "Search data pending" : "No previews yet";
  return (
    <span className="no-preview flex flex-col items-center gap-2 text-muted-foreground">
      <Icon className="size-9 opacity-50" strokeWidth={1.25} aria-hidden />
      <span className="text-[11.5px]">{(item.formats || []).map((f: string) => f.toUpperCase()).join(" · ")}{item.formats?.length ? " · " : ""}{label}</span>
    </span>
  );
}
import { AssetCardGhost, Skeleton, useShownWhile } from "./Loading";
import { Badge } from "./primitives";

function badges(item: Json, thumb?: Thumb) {
  const latest = { ...item, ...(thumb?.presentation || {}) };
  const list: { label: string; tone: "neutral" | "warning" | "fault" }[] = [];
  if (item.asset_type === "image") list.push({ label: (item.formats || []).includes("svg") && item.formats.length === 1 ? "SVG image" : "2D image", tone: "neutral" });
  if (item.source_faulty) list.push({ label: "Source fault", tone: "fault" });
  if (latest.caption_status === "warning") list.push({ label: "Caption warning", tone: "warning" });
  if (hasDescription(latest) && latest.caption_owner_review !== "approved") list.push({ label: "Review " + (latest.caption_owner_review || "pending"), tone: "neutral" });
  if (thumb?.badge) list.push({ label: thumb.badge.label, tone: thumb.badge.tone === "fault" ? "fault" : "neutral" });
  return list;
}

function AssetCard({ grid, item, selected, index }: { grid: GridId; item: Json; selected: boolean; index: number }) {
  const thumb = useApp((s) => s[grid].thumbs[item.asset_id]);
  const choosing = useApp((s) => grid === "collection" && s.selection.active);
  const picked = useApp((s) => grid === "source" && s.sourcesView.picked.includes(item.asset_id));
  const ticked = useApp((s) => (choosing && s.selection.ids.includes(item.asset_id)) || picked);
  const ref = useRef<HTMLButtonElement>(null);
  const reduce = useReducedMotion();
  useEffect(() => {
    const element = ref.current;
    if (!element || thumb) return;
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        observer.disconnect();
        requestThumb(grid, item);
      }
    }, { rootMargin: "200px" });
    observer.observe(element);
    return () => observer.disconnect();
  }, [grid, item, thumb]);
  const list = badges(item, thumb);
  const latest = { ...item, ...(thumb?.presentation || {}) };
  const label = `${item.name}, ${packLabel(item)}${item.source_faulty ? ", source fault" : ""}${latest.caption_status === "warning" ? ", caption warning" : ""}`;
  const describedBy = thumb?.reason ? `${grid}-preview-state-${item.asset_id}` : undefined;
  const meta = cardMeta(item, thumb?.card);
  const menu = (x: number, y: number, keyboard = false) => openAssetMenu(grid, item, x, y, ref.current, keyboard);
  return (
    <motion.button
      ref={ref}
      type="button"
      data-id={item.asset_id}
      aria-pressed={choosing ? ticked : selected}
      aria-label={(choosing ? (ticked ? "Selected: " : "Not selected: ") : "") + label + (item.label ? `, labeled ${item.label}` : "")}
      aria-describedby={describedBy}
      aria-haspopup="menu"
      title={thumb?.presentation?.faults?.length ? "Recorded faults available in detail" : undefined}
      onClick={(event) => {
        if (choosing) return toggleSelected(item.asset_id, event.shiftKey);
        // Ctrl- or Shift-click picks several assets on the Asset sources tab, for queue actions and collections.
        if (grid === "source" && (event.ctrlKey || event.metaKey || event.shiftKey)) return pickAsset(item.asset_id, event.shiftKey);
        void selectAsset(grid, item.asset_id, null, "three_quarter", true);
      }}
      onDoubleClick={() => grid === "source" && item.path && void pathAction("reveal", item.path.split("/")[0], item.path.split("/").slice(1).join("/"))}
      onContextMenu={(event) => {
        event.preventDefault();
        menu(event.clientX, event.clientY);
      }}
      onKeyDown={(event) => {
        if (event.key !== "ContextMenu" && !(event.shiftKey && event.key === "F10")) return;
        event.preventDefault();
        const rect = event.currentTarget.getBoundingClientRect();
        menu(rect.left + 24, rect.top + rect.height / 2, true);
      }}
      whileTap={reduce ? undefined : { scale: 0.985 }}
      transition={SPRING_PRESS}
      style={{ "--enter": `${Math.min(index % 40, 11) * 35}ms` } as CSSProperties}
      className={cn(
        "card ghost-enter group relative flex min-w-0 flex-col overflow-hidden rounded-[18px] border bg-surface p-2 text-left transition-[border-color,box-shadow] outline-none",
        (choosing || picked ? ticked : selected) ? "border-primary ring-1 ring-primary" : "border-border hover:border-border-strong hover:shadow-[0_6px_20px_rgb(0_0_0/0.06)]",
        "focus-visible:ring-2 focus-visible:ring-ring/50",
      )}
    >
      {choosing && (
        <span aria-hidden className={cn("absolute top-4 left-4 z-10 grid size-6 place-items-center rounded-full border-2 shadow-sm transition-colors", ticked ? "border-primary bg-primary text-primary-foreground" : "border-white/90 bg-black/15")}>
          {ticked && <Check className="size-3.5" strokeWidth={3} />}
        </span>
      )}
      {grid === "source" && <StateStrip item={item} />}
      <div className={cn("thumb flex aspect-[258/166] items-center justify-center overflow-hidden rounded-xl", item.asset_type === "image" && thumb?.image ? "bg-checker" : "bg-thumb",
        grid === "source" && item.state === "missing" && "opacity-60")}>
        {thumb?.image ? (
          <img
            src={"data:image/png;base64," + thumb.image}
            alt={item.name + (item.asset_type === "image" ? " — image thumbnail" : " — three-quarter preview")}
            className={cn("reveal-img size-full object-contain", item.asset_type === "image" && "p-2", thumb.pixelArt && "pixelated")}
            draggable={false}
          />
        ) : thumb && grid === "source" && item.state ? (
          <NoPreview item={item} />
        ) : thumb ? (
          <span className="placeholder px-3 text-center text-[12px] leading-snug text-muted-foreground" title={thumb.reason} aria-label={thumb.placeholder ? `${thumb.placeholder}: ${thumb.reason}` : undefined}>
            {thumb.placeholder}
          </span>
        ) : (
          <span className="thumb-loading size-full" role="img" aria-label="Loading preview…">
            <Skeleton className="size-full rounded-none" wave={(index % 4) * 90} />
          </span>
        )}
      </div>
      <div className="card-text grid gap-1 px-3 pt-3.5 pb-2.5">
        {item.label && <span className="card-label w-fit max-w-full truncate rounded-md bg-accent-soft px-1.5 py-0.5 text-[11.5px] font-semibold text-accent-soft-foreground">{item.label}</span>}
        <span className="card-name truncate text-[14px] font-medium text-foreground">{item.name}</span>
        {/* Collection members come from several sources; their saved source name says which. */}
        <span className="pack truncate text-[12px] text-muted-foreground">{grid === "collection" && item.source_name ? item.source_name : packLabel(item)}</span>
        {meta && <span className="truncate text-[11px] text-muted-foreground">{meta}</span>}
        {list.length > 0 && (
          <span className="badges mt-1 flex flex-wrap gap-1">
            {list.map((badge) => (
              <Badge key={badge.label} tone={badge.tone} className={cn("h-5 px-1.5 text-[10.5px]", badge.label === "Caption warning" && "caption-quality-badge warning", badge.label === "2D image" || badge.label === "SVG image" ? "type" : undefined)}>
                {badge.label}
              </Badge>
            ))}
          </span>
        )}
      </div>
      {thumb?.reason && <span id={describedBy} className="sr">{thumb.reason}</span>}
    </motion.button>
  );
}

/**
 * Responsive card grid with arrow-key movement between cards. While it loads it shows ghost
 * cards (`append` adds a row of them after the cards already shown) or dims the cards it is
 * about to replace; `pending` overrides the grid's own loading flag.
 */
export function AssetGrid({ grid, id, pending, append }: { grid: GridId; id: string; pending?: boolean; append?: boolean }) {
  const items = useApp((s) => s[grid].items);
  const selected = useApp((s) => s[grid].selected);
  const own = useApp((s) => s[grid].loading);
  const loading = pending ?? own;
  const shown = useShownWhile(loading);
  const ghosts = !shown ? 0 : !items.length ? 8 : append ? 4 : 0;
  const gridRef = useRef<HTMLDivElement>(null);
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const card = (event.target as Element).closest(".card");
    const grid = gridRef.current;
    if (!card || !grid) return;
    const cards = [...grid.querySelectorAll<HTMLElement>(".card")];
    const index = cards.indexOf(card as HTMLElement);
    const columns = Math.max(1, getComputedStyle(grid).gridTemplateColumns.split(" ").length);
    let next = index;
    if (event.key === "ArrowRight") next++;
    else if (event.key === "ArrowLeft") next--;
    else if (event.key === "ArrowDown") next += columns;
    else if (event.key === "ArrowUp") next -= columns;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = cards.length - 1;
    else return;
    event.preventDefault();
    cards[Math.max(0, Math.min(cards.length - 1, next))]?.focus();
  };
  return (
    <div
      ref={gridRef}
      id={id}
      tabIndex={-1}
      aria-busy={loading}
      aria-label="Asset results"
      onKeyDown={onKeyDown}
      className={cn("grid grid-cols-[repeat(auto-fill,minmax(min(100%,232px),1fr))] content-start gap-5 outline-none", shown && items.length > 0 && !append && "refreshing")}
    >
      {items.map((item, index) => <AssetCard key={item.asset_id} grid={grid} item={item} index={index} selected={item.asset_id === selected} />)}
      {Array.from({ length: ghosts }, (_, index) => <AssetCardGhost key={"ghost-" + index} index={index} />)}
    </div>
  );
}
