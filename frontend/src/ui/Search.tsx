import { ArrowRight, Search, SlidersHorizontal, X } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { SPRING_PANEL } from "@/lib/ease";
import { cn } from "@/lib/utils";
import { formatLabel, LIMITS, MODES, packName, VIEWS } from "../app/format";
import { applyFilters, clearSearch, DEFAULT_FILTERS, type Filters, setFiltersOpen, setQuery, submitSearch, useApp } from "../app/store";
import { Button, IconButton, SelectField, Spinner, TextField } from "./primitives";

export function SearchBar({ compact }: { compact: boolean }) {
  const query = useApp((s) => s.query);
  const busy = useApp((s) => s.search.busy);
  const mode = useApp((s) => s.filters.mode);
  const filtersOpen = useApp((s) => s.filtersOpen);
  const reference = mode === "reference";
  return (
    <form
      role="search"
      id="search-form"
      aria-label="Search library assets"
      onSubmit={(event) => {
        event.preventDefault();
        void submitSearch();
      }}
      className={cn("search-surface relative flex w-full items-center gap-2 rounded-full pr-2.5 pl-5 transition-[height] duration-300", compact ? "h-16" : "h-[84px]", busy && "sheen")}
    >
      <Search className={cn("shrink-0 text-muted-foreground", compact ? "size-5" : "size-6")} strokeWidth={1.75} aria-hidden />
      <label htmlFor="query" className="sr">Search the library</label>
      <input
        id="query"
        type="search"
        value={reference ? "" : query}
        onChange={(event) => setQuery(event.target.value)}
        disabled={reference}
        maxLength={mode === "keyword" ? 256 : 1024}
        autoComplete="off"
        placeholder={reference ? "Searching by a pilot preview reference · change it in filters" : "Search your whole asset library"}
        className={cn("h-full min-w-0 flex-1 bg-transparent px-2 text-foreground outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed [&::-webkit-search-cancel-button]:hidden", compact ? "text-[21px]" : "text-[22px]")}
      />
      {query && !reference && (
        <IconButton id="clear" label="Clear search" onClick={clearSearch} className="size-9 rounded-full text-muted-foreground hover:bg-surface/60">
          <X className="size-4" />
        </IconButton>
      )}
      <span id="search-busy" role="status" aria-live="polite" className={cn("items-center gap-2 text-[12px] text-muted-foreground", busy ? "inline-flex" : "hidden")} hidden={!busy}>
        <Spinner className="text-primary" />
        <span className="sr">Searching…</span>
      </span>
      <button
        id="submit"
        type="submit"
        disabled={busy}
        aria-label={query.trim() || reference ? "Search" : "Browse the filtered library"}
        className="grid size-11 shrink-0 place-items-center rounded-full bg-primary text-primary-foreground transition-[background-color,transform] hover:bg-primary-hover active:scale-95 disabled:opacity-60"
      >
        <ArrowRight className="size-5" />
      </button>
      <IconButton
        id="open-filters"
        label="Filters & search options"
        aria-expanded={filtersOpen}
        aria-controls="filters-panel"
        active={filtersOpen}
        onClick={() => setFiltersOpen(!filtersOpen)}
        className="size-11 rounded-full"
        data-filters-anchor=""
      >
        <SlidersHorizontal className="size-5" strokeWidth={1.75} />
      </IconButton>
    </form>
  );
}

export function FiltersPanel() {
  const open = useApp((s) => s.filtersOpen);
  const applied = useApp((s) => s.filters);
  const context = useApp((s) => s.context);
  const references = useApp((s) => s.referenceOptions);
  const [draft, setDraft] = useState<Filters>(applied);
  const panelRef = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();
  useEffect(() => {
    if (open) setDraft(applied);
  }, [open, applied]);
  useEffect(() => {
    if (!open) return;
    panelRef.current?.querySelector<HTMLElement>("h2")?.focus();
    const onPointer = (event: PointerEvent) => {
      const target = event.target as Element;
      if (!panelRef.current?.contains(target) && !target.closest("[data-filters-anchor]") && !target.closest('[role="listbox"]')) setFiltersOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !(event.target as Element).closest?.('[aria-expanded="true"][aria-haspopup="listbox"], [role="listbox"]')) {
        setFiltersOpen(false);
        document.getElementById("open-filters")?.focus();
      }
    };
    window.addEventListener("pointerdown", onPointer);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("pointerdown", onPointer);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);
  const set = (key: keyof Filters) => (value: string) => setDraft((d) => ({ ...d, [key]: value }));
  const packs: [string, string][] = [["", "All packs"], ...((context?.packs || []) as string[]).map((p): [string, string] => [p, packName(p)])];
  const formats: [string, string][] = [["", "Any format"], ...((context?.formats || []) as string[]).map((f): [string, string] => [f, formatLabel(f)])];
  const referenceChoices: [string, string][] = references.map((r) => [r.id, r.label]);
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          ref={panelRef}
          id="filters-panel"
          role="dialog"
          aria-labelledby="filters-title"
          initial={reduce ? { opacity: 0 } : { opacity: 0, y: -8, scale: 0.985 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={reduce ? { opacity: 0 } : { opacity: 0, y: -6, scale: 0.985, transition: { duration: 0.14 } }}
          transition={SPRING_PANEL}
          style={{ transformOrigin: "top center" }}
          className="absolute top-full right-0 left-0 z-30 mx-auto mt-3 w-[min(960px,100%)] rounded-[28px] border border-border bg-surface p-7 shadow-panel"
        >
          <div className="mb-5 flex items-center justify-between">
            <h2 id="filters-title" tabIndex={-1} className="text-[15px] font-semibold outline-none">Filters &amp; search options</h2>
            <IconButton label="Close filters" onClick={() => setFiltersOpen(false)} className="size-9">
              <X className="size-4" />
            </IconButton>
          </div>
          <div className="grid grid-cols-1 gap-x-5 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
            <SelectField id="asset-type" label="Asset type" value={draft.asset_type} onChange={set("asset_type")} options={[["", "All assets"], ["model_3d", "3D models"], ["image", "2D images"]]} />
            <SelectField id="pack" label="Pack" value={draft.pack} onChange={set("pack")} options={packs} />
            <SelectField id="format" label="Source format" value={draft.format} onChange={set("format")} options={formats} />
            <TextField id="triangles" label="Maximum triangles" type="number" min={0} max={1000000000} step={1} placeholder="No limit" value={draft.triangles} onChange={(e) => set("triangles")(e.target.value)} />
            <SelectField id="rigged" label="Rigged" value={draft.rigged} onChange={set("rigged")} options={[["", "Any / unknown"], ["true", "Yes"], ["false", "No"]]} />
            <SelectField id="transparent" label="Image transparency" value={draft.transparent} onChange={set("transparent")} options={[["", "Any"], ["true", "Has transparency"], ["false", "Opaque"]]} />
            <SelectField id="size-class" label="Image size" value={draft.size_class} onChange={set("size_class")} options={[["", "Any size"], ["tiny", "Tiny (up to 32 px)"], ["small", "Small (up to 128 px)"], ["medium", "Medium (up to 1024 px)"], ["large", "Large (over 1024 px)"]]} />
            <SelectField id="mode" label="Search mode" value={draft.mode} onChange={set("mode")} options={MODES} />
            <SelectField id="limit" label="Shortlist limit" value={draft.limit} onChange={set("limit")} options={LIMITS.map((l): [string, string] => [l, l])} />
            {draft.mode === "reference" && (
              <>
                <SelectField id="reference-asset" className="lg:col-span-2" label="Reference pilot asset" value={draft.reference_asset} onChange={set("reference_asset")} options={referenceChoices.length ? referenceChoices : [["", "Loading pilot assets…"]]} />
                <SelectField id="reference-view" label="Reference view" value={draft.reference_view} onChange={set("reference_view")} options={Object.entries(VIEWS)} />
              </>
            )}
          </div>
          <div className="mt-6 flex flex-wrap items-center gap-x-6 gap-y-3 border-t border-border pt-5">
            <p className="min-w-[240px] flex-1 text-[12px] leading-relaxed text-muted-foreground">
              Image and 3D filters apply to their asset types; technical filters need measured evidence. An empty search browses the filtered library.
            </p>
            <div className="ml-auto flex items-center gap-2">
              <Button variant="quiet" onClick={() => setDraft({ ...DEFAULT_FILTERS })}>Reset</Button>
              <Button id="apply-filters" disabled={draft.mode === "reference" && !draft.reference_asset} onClick={() => void applyFilters(draft)}>Apply filters</Button>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
