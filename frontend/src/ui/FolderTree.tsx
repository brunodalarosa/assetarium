import { Boxes, ChevronRight, Folder, FolderX, HardDrive, Package } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { type KeyboardEvent, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Tooltip } from "@/components/beui/tooltip";
import { cn } from "@/lib/utils";
import type { Json } from "../app/api";
import { plural } from "../app/format";
import { inspectFolder, openFolderMenu, pathAction, type SourcesView, toggleFolder, useApp } from "../app/store";

const ROW = 34; // px; the tree renders only the rows in view (Kenney-sized libraries have thousands of folders).
const ICONS = { library: HardDrive, bundle: Boxes, pack: Package, folder: Folder, excluded: FolderX } as const;

interface Row {
  id: string;
  key: string;
  path: string;
  depth: number;
  node: Json;
  folder: Json;
  open: boolean;
  parent: string | null;
  hasChildren: boolean;
}

function sortNodes(children: Json[], sort: SourcesView["sort"]) {
  const by = {
    name: (a: Json, b: Json) => (a.name || "").localeCompare(b.name || "", undefined, { numeric: true, sensitivity: "base" }),
    added: (a: Json, b: Json) => (b.new || 0) - (a.new || 0),
    pending: (a: Json, b: Json) => (b.pending || 0) - (a.pending || 0),
    assets: (a: Json, b: Json) => (b.assets || 0) - (a.assets || 0),
  }[sort];
  return [...children].sort((a, b) => by(a, b) || (a.name || "").localeCompare(b.name || ""));
}

/** Visible rows: library folders, then their open folders, depth first. */
function flatten(tree: Json, view: SourcesView): Row[] {
  const rows: Row[] = [];
  for (const folder of tree?.folders || []) {
    const nodes: Record<string, Json> = Object.fromEntries((folder.nodes || []).map((n: Json) => [n.path, n]));
    const excluded = (folder.excluded_folders || []).map((e: Json) => ({ path: e.path, name: e.path.split("/").pop(), kind: "excluded", children: [], assets: 0, files: e.files }));
    const visit = (path: string, depth: number, parent: string | null) => {
      const node = nodes[path] || { path, name: folder.name, kind: "library", children: [], assets: 0 };
      const id = folder.key + ":" + path;
      const children = sortNodes((node.children || []).map((c: string) => nodes[c]).filter(Boolean), view.sort);
      const extra = path === "" ? excluded : [];
      const open = Boolean(view.expanded[id] ?? (path === "" && (tree.folders.length === 1)));
      rows.push({ id, key: folder.key, path, depth, node: path === "" ? { ...node, kind: "library", name: folder.name } : node, folder, open, parent,
        hasChildren: children.length + extra.length > 0 });
      if (!open) return;
      for (const child of children) visit(child.path, depth + 1, id);
      for (const item of extra) rows.push({ id: folder.key + ":excluded:" + item.path, key: folder.key, path: item.path, depth: depth + 1, node: item, folder, open: false, parent: id, hasChildren: false });
    };
    if (folder.offline || !folder.scanned) rows.push({ id: folder.key + ":", key: folder.key, path: "", depth: 0, node: { path: "", name: folder.name, kind: "library", children: [], assets: 0 }, folder, open: false, parent: null, hasChildren: false });
    else visit("", 0, null);
  }
  return rows;
}

function Coverage({ node }: { node: Json }) {
  if (!node.assets) return null;
  const share = node.coverage ?? 0;
  return (
    <span className="coverage relative h-1 w-10 shrink-0 overflow-hidden rounded-full bg-foreground/10" role="img" aria-label={`${Math.round(share * 100)}% have previews`}>
      <motion.span className="absolute inset-y-0 left-0 rounded-full bg-primary/70" initial={false} animate={{ width: `${Math.round(share * 100)}%` }} transition={{ type: "spring", stiffness: 260, damping: 32 }} />
    </span>
  );
}

function TreeRow({ row, selected, focused, onFocus }: { row: Row; selected: boolean; focused: boolean; onFocus: () => void }) {
  const Icon = ICONS[(row.node.kind as keyof typeof ICONS) || "folder"] || Folder;
  const offline = row.folder.offline && row.depth === 0;
  const excluded = row.node.kind === "excluded";
  const reduce = useReducedMotion();
  const label = `${row.node.name || row.folder.name}${offline ? ", offline" : ""}${excluded ? ", excluded" : ""}${row.node.assets ? ", " + plural(row.node.assets, "asset", "assets") : ""}${row.node.new ? `, ${row.node.new} new` : ""}`;
  const menu = (x: number, y: number, element: HTMLElement | null, keyboard = false) =>
    openFolderMenu({ key: row.key, path: row.path, kind: row.node.kind, name: row.node.name || row.folder.name, node: row.node, folder: row.folder }, x, y, element, keyboard);
  return (
    <div
      role="treeitem"
      id={"tree-" + row.id.replace(/[^a-zA-Z0-9_-]/g, "_")}
      aria-level={row.depth + 1}
      aria-expanded={row.hasChildren ? row.open : undefined}
      aria-selected={selected}
      aria-label={label}
      tabIndex={focused ? 0 : -1}
      data-key={row.key}
      data-path={row.path}
      data-kind={row.node.kind}
      onFocus={onFocus}
      onClick={() => !excluded && !offline && inspectFolder(row.key, row.path)}
      onDoubleClick={() => void pathAction("reveal", row.key, row.path)}
      onContextMenu={(event) => {
        event.preventDefault();
        menu(event.clientX, event.clientY, event.currentTarget);
      }}
      style={{ height: ROW, paddingLeft: 8 + row.depth * 16 }}
      className={cn(
        "tree-row group flex cursor-default items-center gap-1.5 rounded-lg pr-2 text-[13px] outline-none select-none",
        selected ? "bg-accent-soft text-accent-soft-foreground" : "hover:bg-surface-2/70",
        "focus-visible:ring-2 focus-visible:ring-ring/50",
        (offline || excluded) && "opacity-55",
      )}
    >
      <button
        type="button"
        tabIndex={-1}
        aria-hidden
        className={cn("grid size-5 shrink-0 place-items-center rounded text-muted-foreground", !row.hasChildren && "invisible")}
        onClick={(event) => {
          event.stopPropagation();
          toggleFolder(row.id);
        }}
      >
        <motion.span animate={{ rotate: row.open ? 90 : 0 }} transition={reduce ? { duration: 0 } : { type: "spring", stiffness: 420, damping: 30 }}>
          <ChevronRight className="size-3.5" />
        </motion.span>
      </button>
      <Icon className={cn("size-4 shrink-0", row.node.kind === "pack" ? "text-primary" : "text-muted-foreground")} strokeWidth={1.75} aria-hidden />
      <span className="min-w-0 flex-1 truncate">{row.node.name || row.folder.name}</span>
      {offline && <span className="text-[11px] text-muted-foreground">Offline</span>}
      {excluded && <span className="text-[11px] text-muted-foreground">Excluded</span>}
      {row.node.new > 0 && (
        <Tooltip content={`${row.node.new} new since your last visit`} delay={300}>
          <span className="new rounded-full bg-primary/12 px-1.5 text-[10.5px] font-semibold text-primary tabular-nums">+{row.node.new}</span>
        </Tooltip>
      )}
      {!excluded && !offline && (
        <Tooltip content={row.node.assets ? `${Math.round((row.node.coverage ?? 0) * 100)}% have previews · ${plural(row.node.assets, "asset", "assets")}` : "No assets"} delay={300}>
          <span className="flex items-center"><Coverage node={row.node} /></span>
        </Tooltip>
      )}
    </div>
  );
}

/** Library folders → bundles → packs → folders (folders only; files are in the grid). */
export function FolderTree() {
  const tree = useApp((s) => s.sourcesView.tree);
  const view = useApp((s) => s.sourcesView);
  const rows = useMemo(() => flatten(tree, view), [tree, view]);
  const scroller = useRef<HTMLDivElement>(null);
  const [scroll, setScroll] = useState({ top: 0, height: 600 });
  const [focus, setFocus] = useState<string | null>(null);
  const selectedId = view.key ? view.key + ":" + view.path : null;
  useLayoutEffect(() => {
    const element = scroller.current;
    if (!element) return;
    const update = () => setScroll({ top: element.scrollTop, height: element.clientHeight });
    update();
    const observer = new ResizeObserver(update);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  const focused = focus && rows.some((r) => r.id === focus) ? focus : selectedId ?? rows[0]?.id;
  const first = Math.max(0, Math.floor(scroll.top / ROW) - 8);
  const last = Math.min(rows.length, Math.ceil((scroll.top + scroll.height) / ROW) + 8);
  const move = (index: number) => {
    const target = rows[Math.max(0, Math.min(rows.length - 1, index))];
    if (!target) return;
    setFocus(target.id);
    const element = scroller.current;
    if (element) {
      const top = rows.indexOf(target) * ROW;
      if (top < element.scrollTop) element.scrollTop = top;
      else if (top + ROW > element.scrollTop + element.clientHeight) element.scrollTop = top + ROW - element.clientHeight;
    }
    requestAnimationFrame(() => document.getElementById("tree-" + target.id.replace(/[^a-zA-Z0-9_-]/g, "_"))?.focus());
  };
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const index = rows.findIndex((r) => r.id === focused);
    const row = rows[index];
    if (!row) return;
    if (event.key === "ArrowDown") move(index + 1);
    else if (event.key === "ArrowUp") move(index - 1);
    else if (event.key === "Home") move(0);
    else if (event.key === "End") move(rows.length - 1);
    else if (event.key === "ArrowRight") {
      if (row.hasChildren && !row.open) toggleFolder(row.id, true);
      else if (row.open) move(index + 1);
    } else if (event.key === "ArrowLeft") {
      if (row.open) toggleFolder(row.id, false);
      else if (row.parent) move(rows.findIndex((r) => r.id === row.parent));
    } else if (event.key === "Enter" || event.key === " ") inspectFolder(row.key, row.path);
    else if (event.key === "ContextMenu" || (event.shiftKey && event.key === "F10")) {
      const element = document.getElementById("tree-" + row.id.replace(/[^a-zA-Z0-9_-]/g, "_"));
      const rect = element?.getBoundingClientRect();
      openFolderMenu({ key: row.key, path: row.path, kind: row.node.kind, name: row.node.name || row.folder.name, node: row.node, folder: row.folder },
        (rect?.left ?? 0) + 24, (rect?.top ?? 0) + ROW / 2, element, true);
    } else return;
    event.preventDefault();
  };
  return (
    <div
      ref={scroller}
      role="tree"
      id="folder-tree"
      aria-label="Library folders"
      onScroll={(event) => setScroll({ top: event.currentTarget.scrollTop, height: event.currentTarget.clientHeight })}
      onKeyDown={onKeyDown}
      className="h-full overflow-y-auto overscroll-contain px-2 pb-6 scroll-thin"
    >
      <div style={{ height: rows.length * ROW, position: "relative" }}>
        <div style={{ transform: `translateY(${first * ROW}px)` }}>
          {rows.slice(first, last).map((row, index) => (
            <div key={row.id} className="tree-enter" style={{ animationDelay: `${Math.min(first + index, 12) * 18}ms` }}>
              <TreeRow row={row} selected={row.id === selectedId} focused={row.id === focused} onFocus={() => setFocus(row.id)} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
