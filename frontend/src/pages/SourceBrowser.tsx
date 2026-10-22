import { ArrowLeft } from "lucide-react";
import { useEffect, useRef } from "react";
import { browseSource, getState, goBack, navigate, useApp } from "../app/store";
import { AssetGrid } from "../ui/AssetGrid";
import { Banner, Button, Spinner } from "../ui/primitives";

/** Saved contents of one asset source; shares cards and inspection with Home. */
export function SourceBrowser({ sourceKey }: { sourceKey: string }) {
  const source = useApp((s) => s.sources.find((item) => item.key === sourceKey));
  const collection = useApp((s) => s.source);
  const scroller = useRef<HTMLDivElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    heading.current?.focus({ preventScroll: true });
  }, [sourceKey]);
  // Infinite scroll: load the next page when the end of the list comes near.
  const maybeLoad = () => {
    const area = scroller.current;
    if (area && area.scrollHeight - area.scrollTop - area.clientHeight < 400) void browseSource();
  };
  useEffect(maybeLoad, [collection.items.length]);
  const back = () => {
    const s = getState();
    const previous = s.history[s.historyIndex - 1];
    if (previous?.page === "settings" && previous.tab === "asset-sources") goBack();
    else navigate({ page: "settings", tab: "asset-sources" });
    // Keyboard focus returns to the link that opened this source.
    const selector = `[data-action=browse][data-source="${CSS.escape(sourceKey)}"]`;
    const started = Date.now();
    const focus = () => {
      const link = document.querySelector<HTMLElement>(selector);
      if (link) link.focus();
      else if (Date.now() - started < 2000) requestAnimationFrame(focus);
    };
    requestAnimationFrame(focus);
  };
  return (
    <div id="source-browser-view" ref={scroller} onScroll={maybeLoad} className="h-full overflow-y-auto overscroll-contain px-8 pb-12 scroll-thin">
      <div className="grid gap-5">
        <div className="flex flex-wrap items-start gap-4">
          <div className="min-w-0 flex-1">
            <p className="text-[12px] text-muted-foreground">Asset source contents</p>
            <h1 id="source-browser-title" ref={heading} tabIndex={-1} className="mt-1 text-[26px] font-semibold break-words outline-none">{source?.name ?? "Asset source"}</h1>
            <p id="source-browser-path" className="mt-1 truncate text-[12px] text-muted-foreground" title={source?.path}>{source?.path}</p>
          </div>
          <Button variant="secondary" id="close-source-browser" onClick={back}><ArrowLeft className="size-4" aria-hidden />Back to asset sources</Button>
        </div>
        <p id="source-browser-status" role="status" aria-live="polite" className="flex items-center gap-2 text-[12.5px] text-muted-foreground">
          {collection.loading && <Spinner className="size-3.5" />}{collection.status}
        </p>
        {collection.error && <Banner><span id="source-browser-error">{collection.error}</span></Banner>}
        <section id="source-collection" aria-label="Source assets" className="collection">
          <AssetGrid collection="source" id="source-grid" />
          {!collection.loading && collection.items.length === 0 && collection.emptyText && <p id="source-empty" className="py-16 text-center text-[13px] text-muted-foreground">{collection.emptyText}</p>}
        </section>
        {!collection.finished && collection.items.length > 0 && (
          <div className="flex justify-center"><Button variant="secondary" id="source-load-more" disabled={collection.loading} onClick={() => void browseSource()}>Load more assets</Button></div>
        )}
      </div>
    </div>
  );
}
