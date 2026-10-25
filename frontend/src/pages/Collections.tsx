import { LayoutGrid, Plus, Search, X } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { type CSSProperties, useEffect, useRef, useState } from "react";
import { SPRING_PRESS } from "@/lib/ease";
import { cn } from "@/lib/utils";
import type { Json } from "../app/api";
import { ago, plural } from "../app/format";
import { coverThumb, openCollection, openCollectionMenu, openCreateCollection, setCollectionsQuery, type Thumb, useApp } from "../app/store";
import { CollectionCardGhost, Skeleton, useShownWhile } from "../ui/Loading";
import { Banner, Button, IconButton, Spinner } from "../ui/primitives";

export function updatedText(utc: string) {
  const days = (Date.now() - Date.parse(utc)) / 86400000;
  return "Updated " + (days < 7 ? ago(utc) : new Date(utc).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }));
}

function CoverTile({ entry, index }: { entry?: Json; index: number }) {
  const [thumb, setThumb] = useState<Thumb | null>(null);
  useEffect(() => {
    let live = true;
    if (entry) void coverThumb(entry).then((value) => live && setThumb(value));
    return () => {
      live = false;
    };
  }, [entry]);
  if (!entry) return <span className="rounded-lg bg-thumb/60" />;
  if (!thumb) return <Skeleton className="rounded-lg" wave={(index % 2) * 50 + Math.floor(index / 2) * 30} />;
  return (
    <span className={cn("grid place-items-center overflow-hidden rounded-lg", entry.asset_type === "image" && thumb.image ? "bg-checker" : "bg-thumb")} title={thumb.reason || entry.name}>
      {thumb.image ? (
        <img src={"data:image/png;base64," + thumb.image} alt="" draggable={false} className={cn("reveal-img size-full object-contain", entry.asset_type === "image" && "p-1", thumb.pixelArt && "pixelated")} />
      ) : (
        <span className="px-1 text-center text-[10.5px] leading-tight text-subtle">{thumb.placeholder}</span>
      )}
    </span>
  );
}

function CollectionCard({ summary, index }: { summary: Json; index: number }) {
  const reduce = useReducedMotion();
  const ref = useRef<HTMLButtonElement>(null);
  const cover: Json[] = summary.cover || [];
  const match = summary.match;
  return (
    <motion.button
      ref={ref}
      type="button"
      data-collection={summary.collection_id}
      aria-haspopup="menu"
      aria-label={`${summary.name}, ${plural(summary.asset_count, "asset", "assets")}, ${updatedText(summary.updated_at)}`}
      onClick={() => openCollection(summary.collection_id)}
      onContextMenu={(event) => {
        event.preventDefault();
        openCollectionMenu(summary, event.clientX, event.clientY, ref.current);
      }}
      onKeyDown={(event) => {
        if (event.key !== "ContextMenu" && !(event.shiftKey && event.key === "F10")) return;
        event.preventDefault();
        const rect = event.currentTarget.getBoundingClientRect();
        openCollectionMenu(summary, rect.left + 24, rect.top + rect.height / 2, ref.current, true);
      }}
      whileTap={reduce ? undefined : { scale: 0.985 }}
      transition={SPRING_PRESS}
      style={{ "--enter": `${Math.min(index, 11) * 35}ms` } as CSSProperties}
      className="collection-card ghost-enter group flex min-w-0 flex-col overflow-hidden rounded-[18px] border border-border bg-surface p-2 text-left outline-none transition-[border-color,box-shadow] hover:border-border-strong hover:shadow-[0_6px_20px_rgb(0_0_0/0.06)] focus-visible:ring-2 focus-visible:ring-ring/50"
    >
      <span className="grid aspect-[258/166] grid-cols-2 grid-rows-2 gap-1.5">
        {[0, 1, 2, 3].map((index) => <CoverTile key={cover[index]?.asset_id ?? "empty-" + index} entry={cover[index]} index={index} />)}
      </span>
      <span className="grid gap-1 px-3 pt-3.5 pb-2.5">
        <span className="collection-name truncate text-[14.5px] font-semibold text-foreground">{summary.name}</span>
        <span className="text-[12px] text-muted-foreground">{plural(summary.asset_count, "asset", "assets")}</span>
        {match && !match.collection && match.assets > 0 && (
          <span className="collection-match truncate text-[11.5px] text-primary">{plural(match.assets, "matching asset", "matching assets")}: {match.names.join(", ")}</span>
        )}
        <span className="collection-updated mt-1 text-[11px] text-subtle">{updatedText(summary.updated_at)}</span>
      </span>
    </motion.button>
  );
}

/** Every collection as a card grid, newest first, with a search over names and contents. */
export function Collections() {
  const collections = useApp((s) => s.collections);
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => heading.current?.focus({ preventScroll: true }), []);
  const searching = Boolean(collections.query.trim());
  // Ghost cards until the first answer; later reloads keep the cards and dim them while searching.
  const waiting = useShownWhile(collections.loading || (!collections.loaded && !collections.error));
  const ghosts = waiting && !collections.items.length && !collections.error;
  return (
    <div id="collections-view" className="flex h-full flex-col overflow-y-auto overscroll-contain px-8 pb-10 scroll-thin">
      <div className="flex flex-wrap items-center gap-4 pt-1">
        <div className="min-w-0 flex-1">
          <h1 ref={heading} tabIndex={-1} className="text-[26px] font-semibold text-foreground outline-none">Collections</h1>
          <p className="mt-1 text-[12.5px] text-muted-foreground">Group assets from any source for a project. Files stay where they are.</p>
        </div>
        <Button id="new-collection" onClick={() => openCreateCollection()}><Plus className="size-4" aria-hidden />New collection</Button>
      </div>
      {collections.total > 0 && (
        <form role="search" aria-label="Search collections" onSubmit={(event) => event.preventDefault()} className={cn("search-surface mt-6 flex h-14 w-full max-w-[720px] items-center gap-2 rounded-full pr-2 pl-5", waiting && searching && "sheen")}>
          <Search className="size-5 shrink-0 text-muted-foreground" strokeWidth={1.75} aria-hidden />
          <label htmlFor="collections-query" className="sr">Search collections and what they contain</label>
          <input
            id="collections-query"
            type="search"
            autoComplete="off"
            maxLength={200}
            value={collections.query}
            onChange={(event) => setCollectionsQuery(event.target.value)}
            placeholder="Search collections and what’s inside"
            className="h-full min-w-0 flex-1 bg-transparent px-2 text-[16px] text-foreground outline-none placeholder:text-muted-foreground [&::-webkit-search-cancel-button]:hidden"
          />
          {collections.loading && <Spinner className="text-primary" />}
          {collections.query && (
            <IconButton id="collections-clear" label="Clear search" onClick={() => setCollectionsQuery("")} className="size-9 rounded-full text-muted-foreground">
              <X className="size-4" />
            </IconButton>
          )}
        </form>
      )}
      {collections.error && <Banner className="mt-5"><span id="collections-error">{collections.error}</span></Banner>}
      <p id="collections-status" role="status" aria-live="polite" className="sr">
        {collections.loaded ? (searching ? plural(collections.items.length, "collection matches", "collections match") : plural(collections.total, "collection", "collections")) : "Loading collections"}
      </p>
      {collections.items.length > 0 && (
        <div id="collections-grid" aria-label="Collections" aria-busy={collections.loading} className={cn("mt-6 grid grid-cols-[repeat(auto-fill,minmax(min(100%,232px),1fr))] content-start gap-5", waiting && searching && "refreshing")}>
          {collections.items.map((summary, index) => <CollectionCard key={summary.collection_id} summary={summary} index={index} />)}
        </div>
      )}
      {ghosts && (
        <div id="collections-loading" aria-hidden className="mt-6 grid grid-cols-[repeat(auto-fill,minmax(min(100%,232px),1fr))] content-start gap-5">
          {Array.from({ length: 6 }, (_, index) => <CollectionCardGhost key={index} index={index} />)}
        </div>
      )}
      {collections.loaded && !collections.error && collections.total === 0 && (
        <div id="collections-empty" className="grid flex-1 place-items-center content-center gap-4 pb-[10vh] text-center">
          <span aria-hidden className="grid size-[72px] place-items-center rounded-2xl bg-surface text-muted-foreground"><LayoutGrid className="size-7" strokeWidth={1.5} /></span>
          <p className="text-[17px] font-semibold text-foreground">No collections yet</p>
          <p className="max-w-[380px] text-[13px] leading-relaxed text-muted-foreground">
            Create a collection for a project, then right-click any asset card and choose <span className="font-medium text-foreground">Add to a collection</span>.
          </p>
          <Button onClick={() => openCreateCollection()}><Plus className="size-4" aria-hidden />Create your first collection</Button>
        </div>
      )}
      {collections.loaded && searching && collections.total > 0 && collections.items.length === 0 && !collections.loading && (
        <p id="collections-no-match" className="py-16 text-center text-[13px] text-muted-foreground">No collection or asset inside one matches “{collections.query.trim()}”.</p>
      )}
    </div>
  );
}
