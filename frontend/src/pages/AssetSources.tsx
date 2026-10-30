import { Box, Copy, FolderOpen, FolderPlus, Grid2x2, Image as ImageIcon, LayoutList, Layers, Package } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import type { Json } from "../app/api";
import { plural } from "../app/format";
import {
  addLibraryFolder, chooseSourceDirectory, copyText, libraryCover, loadFolderItems, makePreviews, openFolderMenu, pathAction, type SourcesView, setSourcesFilter, useApp,
} from "../app/store";
import { AssetGrid } from "../ui/AssetGrid";
import { FolderTree } from "../ui/FolderTree";
import { Banner, Button, SelectField, Spinner } from "../ui/primitives";

const SORTS: [string, string][] = [["name", "Name"], ["added", "Recently added"], ["pending", "Most without previews"], ["assets", "Most assets"]];
const STATUS: [string, string][] = [["new", "Has new"], ["no_previews", "Needs previews"], ["blocked", "Blocked"], ["failed", "Failures"], ["missing", "Missing"]];
const TYPE_ICON: Record<string, typeof Box> = { model_3d: Box, image: ImageIcon, material_texture: Layers };

function Chip({ active, onClick, children, id }: { active: boolean; onClick: () => void; children: React.ReactNode; id?: string }) {
  return (
    <button type="button" id={id} aria-pressed={active} onClick={onClick}
      className={cn("inline-flex h-8 items-center gap-1.5 rounded-full border px-3 text-[12.5px] transition-colors",
        active ? "border-primary bg-accent-soft text-accent-soft-foreground" : "border-border text-muted-foreground hover:border-border-strong hover:text-foreground")}>
      {children}
    </button>
  );
}

function Header() {
  const view = useApp((s) => s.sourcesView);
  const types: Json[] = view.tree?.types || [];
  const [busy, setBusy] = useState(false);
  const toggle = (list: string[], value: string) => (list.includes(value) ? list.filter((v) => v !== value) : [...list, value]);
  const add = async () => {
    const directory = await chooseSourceDirectory();
    if (!directory) return;
    setBusy(true);
    await addLibraryFolder(directory);
    setBusy(false);
  };
  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <h1 id="sources-title" tabIndex={-1} className="mr-auto text-[26px] font-semibold outline-none">Asset sources</h1>
        <SelectField id="sources-sort" label="Sort" value={view.sort} onChange={(value) => setSourcesFilter({ sort: value as SourcesView["sort"] })}
          options={SORTS} className="w-52" />
        <Button id="add-library-folder" disabled={busy} onClick={() => void add()}>{busy ? <Spinner className="size-4" /> : <FolderPlus className="size-4" aria-hidden />}Add library folder</Button>
      </div>
      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Filters">
        {types.map((t) => {
          const Icon = TYPE_ICON[t.id] || Box;
          return <Chip key={t.id} id={"type-" + t.id} active={view.types.includes(t.id)} onClick={() => setSourcesFilter({ types: toggle(view.types, t.id) })}><Icon className="size-3.5" aria-hidden />{t.label}</Chip>;
        })}
        <span className="mx-1 h-5 w-px bg-border" aria-hidden />
        {STATUS.map(([id, label]) => <Chip key={id} id={"status-" + id} active={view.states.includes(id)} onClick={() => setSourcesFilter({ states: toggle(view.states, id) })}>{label}</Chip>)}
      </div>
    </div>
  );
}

function Notices() {
  const tree = useApp((s) => s.sourcesView.tree);
  if (!tree) return null;
  return (
    <>
      {tree.migration?.needed && (
        <Banner tone="info">
          <span id="migration-notice" className="grid gap-1.5">
            <span>Your previews and descriptions are still in the old per-folder data, shown read only. Move them into the library store once; nothing renders or is described again. Close the app, then run:</span>
            <span className="flex flex-wrap items-center gap-2">
              <code className="rounded-md bg-surface px-2 py-1 font-mono text-[12px]">{tree.migration.command}</code>
              <Button variant="quiet" className="h-7 px-2" onClick={() => void copyText(tree.migration.command, "Command copied")}><Copy className="size-3.5" aria-hidden />Copy</Button>
            </span>
          </span>
        </Banner>
      )}
      {(tree.blockers || []).length > 0 && (
        <Banner tone="warning" className="py-2.5 text-[12.5px]">
          <span id="blockers" className="grid gap-1">
            {(tree.blockers || []).map((b: Json) => (
              <span key={b.reason} className="blocker flex flex-wrap items-baseline gap-x-2">
                <strong className="font-medium">{b.reason}:</strong>
                <span className="min-w-0 break-words select-text">{b.fix}</span>
              </span>
            ))}
            <span className="text-[11.5px] opacity-80">Work that needs it is shown as blocked and waits; it is never offered as something to process.</span>
          </span>
        </Banner>
      )}
    </>
  );
}

function Cover({ folderKey, path }: { folderKey: string; path: string | null }) {
  const [image, setImage] = useState<string | null>(null);
  const reduce = useReducedMotion();
  useEffect(() => {
    setImage(null);
    if (path) void libraryCover(folderKey, path).then(setImage);
  }, [folderKey, path]);
  return (
    <div className="grid size-20 shrink-0 place-items-center overflow-hidden rounded-2xl bg-thumb">
      {image ? <motion.img initial={reduce ? false : { opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} src={"data:image/png;base64," + image} alt="" className="size-full object-cover" />
        : <Package className="size-7 text-muted-foreground" strokeWidth={1.5} aria-hidden />}
    </div>
  );
}

/** Above the grid: the shown pack or folder, its counts and the one action its state calls for. */
function FolderHeader() {
  const view = useApp((s) => s.sourcesView);
  const folder = (view.tree?.folders || []).find((f: Json) => f.key === view.key);
  if (!folder) return null;
  const node = (folder.nodes || []).find((n: Json) => n.path === view.path) || {};
  const name = view.path ? node.name : folder.name;
  const pending = view.counts?.no_previews ?? node.pending ?? 0;
  const kind = view.path ? node.kind : "library";
  return (
    <div id="folder-header" className="flex flex-wrap items-center gap-x-4 gap-y-3 rounded-[22px] border border-border bg-surface p-4">
      {kind === "pack" && <Cover folderKey={folder.key} path={node.pack?.cover ?? null} />}
      <div className="grid min-w-[180px] flex-1 gap-1">
        <h2 className="truncate text-[17px] font-semibold" title={name}>{name}</h2>
        <p className="text-[12.5px] text-muted-foreground tabular-nums">
          {plural(node.assets || 0, "asset", "assets")}
          {node.assets ? ` · ${Math.round((node.coverage || 0) * 100)}% with previews` : ""}
          {node.blocked ? ` · ${node.blocked.toLocaleString()} blocked` : ""}
          {node.failed ? ` · ${node.failed.toLocaleString()} recorded ${node.failed === 1 ? "failure" : "failures"}` : ""}
          {(node.pack?.markers || []).some((m: Json) => m.kind === "license") ? " · License file" : ""}
        </p>
      </div>
      {pending > 0 && !folder.offline && (
        <Button id="make-previews" onClick={() => void makePreviews({ key: folder.key, path: view.path }, pending)}>
          {plural(pending, "without previews", "without previews").replace(/^(\d[\d,]*) /, "$1 ")} · Make previews
        </Button>
      )}
    </div>
  );
}

function OtherFiles() {
  const view = useApp((s) => s.sourcesView);
  if (!view.showFiles || !view.files.length) return null;
  return (
    <section aria-label="Other files" className="grid gap-1">
      <h3 className="text-[12px] font-medium text-muted-foreground">Other files</h3>
      <ul id="other-files" className="grid gap-0.5 opacity-60">
        {view.files.map((file: Json) => (
          <li key={file.path}>
            <button type="button" className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-[12.5px] hover:bg-surface-2"
              onDoubleClick={() => void pathAction("reveal", view.key!, file.path.split("/").slice(1).join("/"))}
              onContextMenu={(event) => { event.preventDefault(); openFolderMenu({ ...file, key: view.key, relative: file.path.split("/").slice(1).join("/") }, event.clientX, event.clientY, event.currentTarget); }}>
              <span className="min-w-0 flex-1 truncate">{file.name}</span>
              <span className="shrink-0 truncate text-[11px] text-muted-foreground">{file.folder}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Empty() {
  const reduce = useReducedMotion();
  const [busy, setBusy] = useState(false);
  return (
    <motion.div initial={reduce ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} id="sources-empty" className="mx-auto grid max-w-md justify-items-center gap-4 py-24 text-center">
      <svg viewBox="0 0 120 80" className="h-24 w-36 text-primary" aria-hidden>
        <rect x="10" y="22" width="100" height="50" rx="10" className="fill-current opacity-10" />
        <path d="M10 30a8 8 0 0 1 8-8h26l8 8h50a8 8 0 0 1 8 8" className="fill-none stroke-current opacity-50" strokeWidth="3" />
        <rect x="34" y="38" width="16" height="16" rx="3" className="fill-current opacity-60" />
        <path d="M62 54l8-14 8 14z" className="fill-current opacity-40" />
        <circle cx="90" cy="46" r="7" className="fill-current opacity-25" />
      </svg>
      <p className="text-[15px] font-medium">Point Assetarium at a folder of game assets</p>
      <p className="text-[12.5px] text-muted-foreground">Models and images are found and grouped into packs. Nothing is written into your folders, and nothing is processed until you ask.</p>
      <Button disabled={busy} onClick={async () => { const d = await chooseSourceDirectory(); if (d) { setBusy(true); await addLibraryFolder(d); setBusy(false); } }}>
        <FolderOpen className="size-4" aria-hidden />Add library folder
      </Button>
    </motion.div>
  );
}

/** Browse by place (decision 0023): library folders → bundles → packs → folders, with the shared grid and inspector. */
export function AssetSources() {
  const tree = useApp((s) => s.sourcesView.tree);
  const loading = useApp((s) => s.sourcesView.loading);
  const error = useApp((s) => s.sourcesView.error);
  const grid = useApp((s) => s.source);
  const view = useApp((s) => s.sourcesView);
  const scroller = useRef<HTMLDivElement>(null);
  const heading = useRef(false);
  useEffect(() => {
    if (!heading.current) document.getElementById("sources-title")?.focus({ preventScroll: true });
    heading.current = true;
  }, []);
  const maybeLoad = () => {
    const area = scroller.current;
    if (area && area.scrollHeight - area.scrollTop - area.clientHeight < 500) void loadFolderItems();
  };
  useEffect(maybeLoad, [grid.items.length]);
  const empty = tree && !(tree.folders || []).length;
  return (
    <div id="sources-view" className="flex h-full min-w-0 flex-col gap-4 overflow-x-hidden overflow-y-auto px-8 pb-4 scroll-thin lg:overflow-y-hidden">
      <Header />
      <Notices />
      {error && <Banner tone="fault"><span id="sources-error">Library folders could not be loaded: {error}. Your folders and their results are kept.</span></Banner>}
      {empty ? <Empty /> : (
        <div className="flex min-w-0 flex-col gap-4 lg:min-h-0 lg:flex-1 lg:flex-row">
          {/* Narrow windows stack the tree above the grid; wide ones put them side by side. */}
          <aside className="h-[280px] w-full shrink-0 overflow-hidden rounded-[22px] border border-border bg-surface pt-2 lg:h-auto lg:w-[300px]" aria-busy={loading && !tree}>
            {!tree && loading ? <p className="flex items-center gap-2 p-4 text-[12.5px] text-muted-foreground"><Spinner className="size-3.5" />Loading library folders…</p> : <FolderTree />}
          </aside>
          <div ref={scroller} onScroll={maybeLoad} className="min-w-0 flex-1 pr-1 pb-8 lg:overflow-y-auto lg:overscroll-contain scroll-thin">
            <div className="grid gap-4">
              <FolderHeader />
              <div className="flex flex-wrap items-center gap-3">
                <p id="sources-status" role="status" aria-live="polite" className="mr-auto flex items-center gap-2 text-[12.5px] text-muted-foreground">{grid.loading && <Spinner className="size-3.5" />}{grid.status}</p>
                <label className="flex items-center gap-2 text-[12.5px] text-muted-foreground">
                  <input type="checkbox" id="show-other-files" checked={view.showFiles} onChange={(e) => setSourcesFilter({ showFiles: e.target.checked })} className="accent-[var(--color-primary)]" />Show other files
                </label>
                <div className="flex rounded-lg border border-border p-0.5" role="group" aria-label="View">
                  <button type="button" aria-pressed={!view.list} aria-label="Grid view" className={cn("grid size-7 place-items-center rounded-md", !view.list && "bg-surface-2")} onClick={() => setSourcesFilter({ list: false })}><Grid2x2 className="size-4" /></button>
                  <button type="button" aria-pressed={view.list} aria-label="List view" className={cn("grid size-7 place-items-center rounded-md", view.list && "bg-surface-2")} onClick={() => setSourcesFilter({ list: true })}><LayoutList className="size-4" /></button>
                </div>
              </div>
              {grid.error && <Banner><span id="sources-grid-error">{grid.error}</span></Banner>}
              <section id="sources-collection" aria-label="Assets in this folder" className={cn("collection", view.list && "list-view")}>
                <AssetGrid grid="source" id="sources-grid" append />
                {!grid.loading && grid.items.length === 0 && grid.emptyText && <p id="sources-grid-empty" className="py-12 text-center text-[13px] text-muted-foreground">{grid.emptyText}</p>}
              </section>
              {!grid.finished && grid.items.length > 0 && (
                <div className="flex justify-center"><Button variant="secondary" id="sources-load-more" disabled={grid.loading} onClick={() => void loadFolderItems()}>Load more</Button></div>
              )}
              <OtherFiles />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
