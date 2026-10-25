import { Check } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { type CSSProperties, type KeyboardEvent, useEffect, useRef } from "react";
import { SPRING_PRESS } from "@/lib/ease";
import { cn } from "@/lib/utils";
import type { Json } from "../app/api";
import { cardMeta, hasDescription, packName } from "../app/format";
import { type GridId, openAssetMenu, requestThumb, selectAsset, type Thumb, toggleSelected, useApp } from "../app/store";
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
  const ticked = useApp((s) => choosing && s.selection.ids.includes(item.asset_id));
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
  const label = `${item.name}, ${packName(item.pack)}${item.source_faulty ? ", source fault" : ""}${latest.caption_status === "warning" ? ", caption warning" : ""}`;
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
      onClick={(event) => (choosing ? toggleSelected(item.asset_id, event.shiftKey) : void selectAsset(grid, item.asset_id, null, "three_quarter", true))}
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
        (choosing ? ticked : selected) ? "border-primary ring-1 ring-primary" : "border-border hover:border-border-strong hover:shadow-[0_6px_20px_rgb(0_0_0/0.06)]",
        "focus-visible:ring-2 focus-visible:ring-ring/50",
      )}
    >
      {choosing && (
        <span aria-hidden className={cn("absolute top-4 left-4 z-10 grid size-6 place-items-center rounded-full border-2 shadow-sm transition-colors", ticked ? "border-primary bg-primary text-primary-foreground" : "border-white/90 bg-black/15")}>
          {ticked && <Check className="size-3.5" strokeWidth={3} />}
        </span>
      )}
      <div className={cn("thumb flex aspect-[258/166] items-center justify-center overflow-hidden rounded-xl", item.asset_type === "image" && thumb?.image ? "bg-checker" : "bg-thumb")}>
        {thumb?.image ? (
          <img
            src={"data:image/png;base64," + thumb.image}
            alt={item.name + (item.asset_type === "image" ? " — image thumbnail" : " — three-quarter preview")}
            className={cn("reveal-img size-full object-contain", item.asset_type === "image" && "p-2", thumb.pixelArt && "pixelated")}
            draggable={false}
          />
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
        <span className="pack truncate text-[12px] text-muted-foreground">{grid === "collection" && item.source_name ? item.source_name : packName(item.pack)}</span>
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
