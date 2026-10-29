// The shared loading language (KnowledgeBase/Architecture/Desktop App/Desktop app design.md → Loading states): ghosts stand where
// content of a known shape will appear, after a short delay so fast loads never flash.
import { type CSSProperties, useEffect, useState } from "react";
import { cn } from "@/lib/utils";

const SHIMMER_MS = 1900;

/**
 * True while `active`, but only once it has lasted `delay` ms, and then for at least `min` ms:
 * quick loads show nothing and slow ones never flicker.
 */
export function useShownWhile(active: boolean, delay = 150, min = 400) {
  const [shown, setShown] = useState(false);
  const [since, setSince] = useState(0);
  useEffect(() => {
    if (active && !shown) {
      const timer = setTimeout(() => {
        setShown(true);
        setSince(performance.now());
      }, delay);
      return () => clearTimeout(timer);
    }
    if (!active && shown) {
      const timer = setTimeout(() => setShown(false), Math.max(0, min - (performance.now() - since)));
      return () => clearTimeout(timer);
    }
  }, [active, shown, since, delay, min]);
  return shown;
}

/** One ghost block. All ghosts share the page clock, so their shimmer stays in step. */
export function Skeleton({ className, wave = 0, style }: { className?: string; wave?: number; style?: CSSProperties }) {
  const [phase] = useState(() => -(performance.now() % SHIMMER_MS));
  return <span aria-hidden className={cn("skeleton block", className)} style={{ "--shimmer-delay": `${phase}ms`, "--wave": `${wave}ms`, ...style } as CSSProperties} />;
}

/** Ghost text: a few lines of decreasing width. */
export function SkeletonLines({ lines = 3, className, wave = 0 }: { lines?: number; className?: string; wave?: number }) {
  const widths = ["92%", "78%", "60%", "84%", "45%"];
  return (
    <span aria-hidden className={cn("grid gap-2", className)}>
      {Array.from({ length: lines }, (_, index) => <Skeleton key={index} wave={wave + index * 40} className="h-3" style={{ width: widths[index % widths.length] }} />)}
    </span>
  );
}

/** Ghosts enter with a short stagger so a grid of them settles in like the real cards. */
const enter = (index: number) => ({ "--enter": `${Math.min(index, 11) * 35}ms` }) as CSSProperties;
const wave = (index: number) => (index % 4) * 90 + Math.floor(index / 4) * 60;

/** An asset card's ghost: same frame, thumbnail and text rhythm as AssetGrid's cards. */
export function AssetCardGhost({ index = 0 }: { index?: number }) {
  return (
    <div aria-hidden className="card-ghost ghost-enter flex min-w-0 flex-col rounded-[18px] border border-border bg-surface p-2" style={enter(index)}>
      <Skeleton wave={wave(index)} className="aspect-[258/166] rounded-xl" />
      <span className="grid gap-2 px-3 pt-4 pb-3">
        <Skeleton wave={wave(index) + 60} className="h-3.5 w-[68%]" />
        <Skeleton wave={wave(index) + 100} className="h-3 w-[44%]" />
        <Skeleton wave={wave(index) + 140} className="h-2.5 w-[30%]" />
      </span>
    </div>
  );
}

/** A collection card's ghost: four cover tiles, a name and a count. */
export function CollectionCardGhost({ index = 0 }: { index?: number }) {
  return (
    <div aria-hidden className="collection-ghost ghost-enter flex min-w-0 flex-col rounded-[18px] border border-border bg-surface p-2" style={enter(index)}>
      <span className="grid aspect-[258/166] grid-cols-2 grid-rows-2 gap-1.5">
        {[0, 1, 2, 3].map((tile) => <Skeleton key={tile} wave={wave(index) + (tile % 2) * 50 + Math.floor(tile / 2) * 30} className="rounded-lg" />)}
      </span>
      <span className="grid gap-2 px-3 pt-4 pb-3">
        <Skeleton wave={wave(index) + 80} className="h-3.5 w-[58%]" />
        <Skeleton wave={wave(index) + 120} className="h-3 w-[32%]" />
        <Skeleton wave={wave(index) + 160} className="mt-1 h-2.5 w-[40%]" />
      </span>
    </div>
  );
}

/** The inspector's ghost: heading, badges, preview, the section switch and a few facts. */
export function InspectorGhost() {
  return (
    <div className="ghost-enter grid content-start gap-5 px-6 pb-8" role="status">
      <span className="sr">Loading asset evidence…</span>
      <span aria-hidden className="grid gap-2.5">
        <Skeleton className="h-6 w-[62%]" />
        <span className="flex gap-2">
          <Skeleton wave={40} className="h-6 w-[72px] rounded-md" />
          <Skeleton wave={80} className="h-6 w-[96px] rounded-md" />
        </span>
      </span>
      <Skeleton wave={60} className="aspect-[4/3] w-full rounded-[14px]" />
      <Skeleton wave={100} className="h-11 w-full rounded-full" />
      <SkeletonLines lines={4} wave={140} />
    </div>
  );
}
