import { ChevronLeft, ChevronRight, Copy } from "lucide-react";
import { motion } from "motion/react";
import { SPRING_LAYOUT } from "@/lib/ease";
import { cn } from "@/lib/utils";
import { modeLabel, plural } from "../app/format";
import { copyText, pageBrowse, useApp } from "../app/store";
import { AssetGrid } from "../ui/AssetGrid";
import { Badge, Banner, Button, IconButton } from "../ui/primitives";
import { FiltersPanel, SearchBar } from "../ui/Search";

function ResultsHeader() {
  const search = useApp((s) => s.search);
  const library = useApp((s) => s.library);
  const browsing = search.phase === "browse";
  const count = browsing ? library.total : search.count;
  const heading = search.busy && !library.items.length ? "Searching…" : browsing ? plural(count, "asset", "assets") : plural(count, "result", "results");
  return (
    <div className="results-bar flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
      <div className="min-w-0">
        <h2 id="results-title" className="text-[21px] font-semibold text-foreground" aria-label={search.title}>{heading}</h2>
        <p className="mt-1.5 truncate text-[13px] text-muted-foreground">{browsing ? "Browsing the filtered library" : search.queryUsed || (search.modeUsed === "reference" ? "Similar to a pilot preview" : "")}</p>
        <p id="status" role="status" aria-live="polite" title={search.statusTitle || undefined} className="mt-1 text-[11.5px] text-subtle">{search.status}</p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Badge className="h-7 px-2.5">{browsing ? "Browse" : modeLabel(search.modeUsed)}</Badge>
        {!browsing && (
          <Button id="copy-settings" variant="quiet" className="h-8 px-3 text-[12px]" disabled={!search.lastSettings} title="Copies the completed search for agents (MCP search_assets)" onClick={() => search.lastSettings && void copyText(JSON.stringify(search.lastSettings, null, 2), "Exact MCP search_assets settings copied. Use the same catalog and index versions.")}>
            <Copy className="size-3.5" aria-hidden />Copy search settings
          </Button>
        )}
        {browsing && (
          <nav aria-label="Asset pages" className="paging flex items-center gap-1">
            <IconButton id="previous-page" label="Previous page" disabled={library.offset === 0 || library.loading} onClick={() => void pageBrowse(-1)} className="size-8"><ChevronLeft className="size-4" /></IconButton>
            <span id="page-info" className="min-w-24 text-center text-[12px] text-muted-foreground tabular-nums">{count ? `${library.offset + 1}–${library.offset + library.items.length} of ${count}` : "0 of 0"}</span>
            <IconButton id="next-page" label="Next page" disabled={library.offset + 40 >= count || library.loading} onClick={() => void pageBrowse(1)} className="size-8"><ChevronRight className="size-4" /></IconButton>
          </nav>
        )}
      </div>
    </div>
  );
}

export function Home() {
  const phase = useApp((s) => s.search.phase);
  const error = useApp((s) => s.search.error);
  const candidateNote = useApp((s) => s.search.candidateNote);
  const startupError = useApp((s) => s.startupError);
  const empty = useApp((s) => !s.library.loading && s.library.items.length === 0);
  const filtersOpen = useApp((s) => s.filtersOpen);
  const compact = phase !== "idle";
  // Idle Home keeps the search centred; open filters lift it so the panel fits below.
  return (
    <div id="library-view" className="flex h-full min-h-0 flex-col overflow-y-auto overscroll-contain scroll-thin">
      <motion.div layout="position" transition={SPRING_LAYOUT} className={cn("px-8", compact ? "pt-3 pb-8" : filtersOpen ? "flex flex-1 items-start pt-[6vh]" : "flex flex-1 items-center pb-[14vh]")}>
        <div className={cn("relative mx-auto w-full transition-[max-width] duration-300", compact ? "max-w-[1120px]" : "max-w-[880px]")}>
          <SearchBar compact={compact} />
          <FiltersPanel />
        </div>
      </motion.div>
      {startupError && <Banner className="mx-8 mb-6">{startupError} Startup data is faulty. No model loading or fallback attempted.</Banner>}
      {compact && (
        <section aria-label="Library assets" className="collection grid gap-5 px-8 pb-10">
          <ResultsHeader />
          {candidateNote && <p className="-mt-2 text-[11.5px] text-muted-foreground">Ranked suggestions may include unrelated assets—even when the requested object is absent. Review the previews.</p>}
          {error && <Banner className="error" role="alert"><span id="error">{error}</span></Banner>}
          <AssetGrid grid="library" id="grid" />
          {empty && !error && <p id="empty" className="py-16 text-center text-[13px] text-muted-foreground">No assets match these settings.</p>}
        </section>
      )}
    </div>
  );
}
