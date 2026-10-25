import { ArrowRight, Download, ListChecks, Pencil, Search, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/beui/select";
import { cn } from "@/lib/utils";
import { MODES, modeLabel, plural } from "../app/format";
import {
  cancelSelection, clearCollectionSearch, navigate, openExportMenu, removeSelected, searchCollection, selectAllShown,
  setCollectionMode, setCollectionQuery, startSelection, updateCollection, useApp,
} from "../app/store";
import { AssetGrid } from "../ui/AssetGrid";
import { SelectionBar } from "../ui/Menus";
import { Skeleton, SkeletonLines, useShownWhile } from "../ui/Loading";
import { Banner, Button, IconButton, Spinner } from "../ui/primitives";
import { updatedText } from "./Collections";

// Reference search compares to one library preview; it has no meaning inside a collection.
const COLLECTION_MODES = MODES.filter(([value]) => value !== "reference");

function SearchBar() {
  const view = useApp((s) => s.collectionView);
  return (
    <form
      role="search"
      id="collection-search"
      aria-label="Search this collection"
      onSubmit={(event) => {
        event.preventDefault();
        void searchCollection();
      }}
      className={cn("search-surface relative flex h-16 w-full items-center gap-2 rounded-full pr-2.5 pl-5", view.busy && "sheen")}
    >
      <Search className="size-5 shrink-0 text-muted-foreground" strokeWidth={1.75} aria-hidden />
      <label htmlFor="collection-query" className="sr">Search this collection</label>
      <input
        id="collection-query"
        type="search"
        value={view.query}
        onChange={(event) => setCollectionQuery(event.target.value)}
        maxLength={1024}
        autoComplete="off"
        placeholder={`Search in ${view.name || "this collection"}`}
        className="h-full min-w-0 flex-1 bg-transparent px-2 text-[19px] text-foreground outline-none placeholder:text-muted-foreground [&::-webkit-search-cancel-button]:hidden"
      />
      {view.query && (
        <IconButton id="collection-clear" label="Clear search" onClick={() => void clearCollectionSearch()} className="size-9 rounded-full text-muted-foreground hover:bg-surface/60">
          <X className="size-4" />
        </IconButton>
      )}
      {view.busy && <Spinner className="text-primary" />}
      <Select value={view.mode} onValueChange={setCollectionMode}>
        <SelectTrigger labelledBy="collection-mode-label" className="h-10 w-auto shrink-0 rounded-full border-transparent bg-surface/70 px-3.5 text-[12.5px] hover:bg-surface">
          <span id="collection-mode-label" className="sr">Search mode</span>
          <SelectValue className="truncate" />
        </SelectTrigger>
        <SelectContent className="rounded-xl border-border bg-surface shadow-panel">
          {COLLECTION_MODES.map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}
        </SelectContent>
      </Select>
      <button id="collection-submit" type="submit" disabled={view.busy} aria-label={view.query.trim() ? "Search" : "Show all assets"} className="grid size-11 shrink-0 place-items-center rounded-full bg-primary text-primary-foreground transition-[background-color,transform] hover:bg-primary-hover active:scale-95 disabled:opacity-60">
        <ArrowRight className="size-5" />
      </button>
    </form>
  );
}

/** The description reads as text; the pencil edits it in place. */
function Description() {
  const view = useApp((s) => s.collectionView);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const field = useRef<HTMLTextAreaElement>(null);
  const opening = useShownWhile(view.loading && !view.name, 150, 300);
  useEffect(() => {
    if (editing) field.current?.focus();
  }, [editing]);
  const save = async () => {
    if (draft.trim() === view.description) return setEditing(false);
    try {
      await updateCollection(view.id!, { description: draft });
      setEditing(false);
    } catch (reason) {
      setError((reason as Error).message);
    }
  };
  if (editing)
    return (
      <div className="grid max-w-[760px] gap-2">
        <label htmlFor="collection-description-edit" className="sr">Collection description</label>
        <textarea
          id="collection-description-edit"
          ref={field}
          rows={3}
          maxLength={2000}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              event.preventDefault();
              event.stopPropagation();
              setEditing(false);
            }
            if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) void save();
          }}
          placeholder="What this collection is for"
          className="resize-none rounded-xl border border-border bg-surface px-3 py-2.5 text-[13px] leading-relaxed outline-none focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-ring/25"
        />
        {error && <p role="alert" className="text-[12px] text-fault">{error}</p>}
        <div className="flex gap-2">
          <Button className="h-9 px-4 text-[12.5px]" id="collection-description-save" onClick={() => void save()}>Save</Button>
          <Button variant="quiet" className="h-9 px-4 text-[12.5px]" onClick={() => setEditing(false)}>Cancel</Button>
        </div>
      </div>
    );
  if (!view.name) return opening ? <SkeletonLines lines={2} className="ghost-enter w-[min(520px,70vw)] py-1" /> : <div className="h-5" />;
  return (
    <div className="flex max-w-[760px] items-start gap-1.5">
      {view.description ? (
        <p id="collection-description" className="text-[13.5px] leading-relaxed whitespace-pre-wrap text-muted-foreground">{view.description}</p>
      ) : (
        <p className="text-[13px] text-subtle">No description</p>
      )}
      <IconButton label={view.description ? "Edit description" : "Add a description"} id="edit-description" onClick={() => { setDraft(view.description); setError(null); setEditing(true); }} className="-mt-1.5 size-8 shrink-0 rounded-lg text-muted-foreground">
        <Pencil className="size-3.5" />
      </IconButton>
    </div>
  );
}

/** One collection: like Home, but every search and card stays inside it. */
export function Collection({ collectionId }: { collectionId: string }) {
  const view = useApp((s) => s.collectionView);
  const grid = useApp((s) => s.collection);
  const selection = useApp((s) => s.selection);
  useEffect(() => {
    if (!selection.active) return;
    const onKey = (event: KeyboardEvent) => {
      const typing = (event.target as Element).closest?.("input, textarea, dialog, [role=menu]");
      if (event.key === "Escape" && !typing) {
        event.preventDefault();
        cancelSelection();
      }
      if (event.key.toLowerCase() === "a" && (event.ctrlKey || event.metaKey) && !typing) {
        event.preventDefault();
        selectAllShown();
      }
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [selection.active]);
  const searching = view.phase === "search";
  const searchFault = view.search?.status === "faulty";
  const empty = !view.loading && !view.error && view.count === 0;
  const unnamed = !view.name && view.loading;
  const opening = useShownWhile(unnamed, 150, 300);
  return (
    <div id="collection-view" data-collection={collectionId} className="flex h-full min-h-0 flex-col overflow-y-auto overscroll-contain scroll-thin">
      <div className="mx-auto grid w-full max-w-[1120px] gap-5 px-8 pt-3 pb-10">
        <SearchBar />
        <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
          <div className="grid min-w-0 gap-2">
            <Description />
            <p id="collection-status" role="status" aria-live="polite" className="flex items-center gap-2 text-[12px] text-muted-foreground">
              {unnamed || opening ? <><span className="sr">Loading collection…</span>{opening && <Skeleton className="ghost-enter h-3 w-44" wave={80} />}</> : view.loading && <Spinner className="size-3.5" />}
              {!unnamed && !opening && [plural(view.count, "asset", "assets"), view.unavailable ? `${view.unavailable} unavailable` : "", view.updatedAt ? updatedText(view.updatedAt) : ""].filter(Boolean).join(" · ")}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="secondary" id="collection-select" className="h-9 px-4 text-[12.5px]" disabled={!view.count || selection.active} onClick={() => startSelection()}>
              <ListChecks className="size-4" aria-hidden />Select
            </Button>
            <Button
              variant="secondary"
              id="collection-export"
              aria-haspopup="menu"
              className="h-9 px-4 text-[12.5px]"
              disabled={!view.id}
              onClick={(event) => {
                const button = event.currentTarget, rect = button.getBoundingClientRect();
                openExportMenu(collectionId, rect.left, rect.bottom + 6, button, event.detail === 0);
              }}
            >
              <Download className="size-4" aria-hidden />Export
            </Button>
          </div>
        </div>
        {view.error && <Banner className="error" role="alert"><span id="collection-error">{view.error}</span></Banner>}
        {/* Stays while a background refresh repeats the search, so the heading does not flicker. */}
        {searching && (grid.items.length > 0 || !view.busy) && (
          <div className="grid gap-1">
            <h2 id="collection-results-title" className="text-[17px] font-semibold">{plural(grid.items.length, "match", "matches")} for “{view.query}”</h2>
            {!searchFault && view.search && <p className="text-[11.5px] text-muted-foreground">Labels, notes, tags and names first, then {modeLabel(view.mode).toLowerCase()} ranking among members. Ranked suggestions may include unrelated assets.</p>}
          </div>
        )}
        {searchFault && (
          <Banner tone="warning" role="note"><span id="collection-search-fault">Ranked search is unavailable: {view.search.reason || "the search failed"}. Showing matches in names, labels, notes and tags only; no fallback or automatic retry.</span></Banner>
        )}
        <section aria-label="Collection assets" className={cn("collection", selection.active && "pb-2")}>
          <AssetGrid grid="collection" id="collection-grid" pending={view.busy || (view.loading && !grid.items.length)} />
        </section>
        {empty && (
          <div id="collection-empty" className="grid place-items-center gap-3 py-16 text-center">
            <p className="text-[17px] font-semibold text-foreground">This collection is empty</p>
            <p className="max-w-[380px] text-[13px] leading-relaxed text-muted-foreground">
              Search from Home, then right-click an asset and choose <span className="font-medium text-foreground">Add to a collection</span>.
            </p>
            <Button variant="secondary" onClick={() => navigate({ page: "home" })}>Go to Home</Button>
          </div>
        )}
        {searching && !view.busy && !grid.items.length && !view.error && (
          <p id="collection-no-match" className="py-12 text-center text-[13px] text-muted-foreground">No asset in this collection matches “{view.query}”.</p>
        )}
        {selection.active && (
          <SelectionBar count={selection.ids.length} total={grid.items.length} onSelectAll={selectAllShown} onRemove={() => void removeSelected()} onCancel={cancelSelection} />
        )}
      </div>
    </div>
  );
}
