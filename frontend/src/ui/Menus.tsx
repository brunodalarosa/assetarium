import { Check, ChevronRight, FolderOpen, FolderPlus, FolderSearch, ListX, Plus, RotateCcw, ScanSearch, Search, Trash2, X } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { type CSSProperties, type FormEvent, type KeyboardEvent, type MouseEvent as ReactMouseEvent, useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  ContextMenu, ContextMenuContent, ContextMenuItem, ContextMenuLabel, ContextMenuSeparator, useContextMenuState,
} from "@/components/beui/context-menu";
import { SPRING_PANEL } from "@/lib/ease";
import { cn } from "@/lib/utils";
import type { Json } from "../app/api";
import { plural } from "../app/format";
import {
  addToCollection, assetMenuSource, closeConfirm, closeCreateCollection, closeMenu, collectionsFor, confirmDeleteCollection,
  createCollection, exportCollection, type GridId, type MenuRequest, openCollection, openCreateCollection, pushToast, removeFromCollection, revealAsset, selectAsset,
  startSelection, useApp,
} from "../app/store";
import { Skeleton } from "./Loading";
import { Button, IconButton, Spinner } from "./primitives";

const ICON = "size-4 shrink-0 text-muted-foreground";
const GAP = 8; // Between the menu and the flyout, covered by the bridge.

/**
 * The "Add to a collection" flyout: find, create, and tick collections for one asset.
 * It sits beside the menu as its own layer so typing in its search never reaches the menu's typeahead.
 */
function CollectionFlyout({ anchor, grid, item, onBack, onEnter }: { anchor: HTMLElement; grid: GridId; item: Json; onBack: () => void; onEnter: () => void }) {
  const menu = useContextMenuState();
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<Json[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [position, setPosition] = useState({ left: -9999, top: -9999, side: "right" as "right" | "left" });
  const panel = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const reduce = useReducedMotion();
  useEffect(() => {
    collectionsFor(item.asset_id).then(setItems, (reason: Error) => setError(reason.message));
  }, [item.asset_id]);
  useLayoutEffect(() => {
    const element = panel.current;
    if (!element) return;
    const row = anchor.getBoundingClientRect();
    const host = menu.contentRef.current?.getBoundingClientRect() ?? row;
    const width = element.offsetWidth, height = element.offsetHeight;
    const right = host.right + GAP, left = host.left - width - GAP;
    const fits = right + width <= window.innerWidth - 8;
    setPosition({
      left: fits ? right : Math.max(8, left),
      top: Math.max(8, Math.min(row.top - 8, window.innerHeight - height - 8)),
      side: fits ? "right" : "left",
    });
  }, [anchor, menu.contentRef, items]);
  useEffect(() => input.current?.focus({ preventScroll: true }), []);
  const words = query.trim().toLocaleLowerCase();
  const shown = (items || []).filter((c) => !words || c.name.toLocaleLowerCase().includes(words));
  const exact = (items || []).some((c) => c.name.toLocaleLowerCase() === words);
  const close = () => menu.setOpen(false);
  const choose = (collection: Json) => {
    close();
    if (collection.contains) void removeFromCollection(collection.collection_id, [item.asset_id]);
    else void addToCollection(collection, grid, item);
  };
  const create = () => {
    const name = query.trim();
    const sourceKey = assetMenuSource(grid, item);
    close();
    // A typed, unused name creates and adds in one step; otherwise the dialog asks for the details.
    if (name && !exact) void createCollection(name, "", [item.asset_id], sourceKey).catch((reason: Error) => pushToast({ tone: "fault", title: "Could not create the collection", body: reason.message }));
    else openCreateCollection({ assetIds: [item.asset_id], sourceKey, name: name || undefined });
  };
  const focusables = () => [...(panel.current?.querySelectorAll<HTMLElement>("[data-flyout-item]") || [])];
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const inInput = event.target === input.current;
    if (event.key === "Escape" || (event.key === "ArrowLeft" && !inInput)) {
      event.preventDefault();
      event.stopPropagation();
      onBack();
      return;
    }
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const list = focusables();
      const index = list.indexOf(document.activeElement as HTMLElement);
      const next = event.key === "ArrowDown" ? Math.min(list.length - 1, index + 1) : index - 1;
      (next < 0 ? input.current : list[next])?.focus();
      return;
    }
    if (event.key === "Enter" && inInput) {
      event.preventDefault();
      if (shown.length === 1 && words) choose(shown[0]);
      else create();
    }
    if (event.key === "Tab") close();
  };
  return createPortal(
    <>
    {/* An invisible bridge over the gap, so the pointer never leaves the menu on its way to the flyout. */}
    <div
      aria-hidden
      data-context-menu-layer={menu.menuId}
      id="collection-flyout-bridge"
      onPointerEnter={onEnter}
      style={{ left: position.side === "right" ? position.left - GAP : position.left + (panel.current?.offsetWidth ?? 0), top: position.top, width: GAP, height: panel.current?.offsetHeight ?? 0 }}
      className="fixed z-[101]"
    />
    <motion.div
      ref={panel}
      data-context-menu-layer={menu.menuId}
      id="collection-flyout"
      role="menu"
      aria-label="Add to a collection"
      initial={reduce ? { opacity: 0 } : { opacity: 0, x: -6, scale: 0.98 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      transition={SPRING_PANEL}
      style={{ left: position.left, top: position.top }}
      onKeyDown={onKeyDown}
      onPointerEnter={onEnter}
      onContextMenu={(event) => event.preventDefault()}
      className="fixed z-[101] w-72 overflow-hidden rounded-xl border border-border bg-card p-1.5 text-foreground [filter:drop-shadow(0_18px_28px_rgba(0,0,0,0.2))]"
    >
      <label className="flex h-9 items-center gap-2 rounded-lg bg-surface-2 px-2.5">
        <Search className="size-3.5 shrink-0 text-muted-foreground" aria-hidden />
        <span className="sr">Find a collection</span>
        <input
          ref={input}
          id="collection-flyout-search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          maxLength={80}
          autoComplete="off"
          placeholder="Find or name a collection…"
          className="h-full min-w-0 flex-1 bg-transparent text-[13px] outline-none placeholder:text-muted-foreground"
        />
      </label>
      <button
        type="button"
        role="menuitem"
        data-flyout-item=""
        id="collection-flyout-create"
        onClick={create}
        className="mt-1 flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-[13px] font-medium text-primary outline-none hover:bg-foreground/[0.065] focus-visible:bg-foreground/[0.065]"
      >
        <Plus className="size-4 shrink-0" aria-hidden />
        <span className="min-w-0 truncate">{words && !exact ? `Create “${query.trim()}”` : "Create new collection"}</span>
      </button>
      <hr className="-mx-1.5 my-1 h-px border-0 bg-border" />
      <div className="max-h-64 overflow-y-auto overscroll-contain scroll-thin" role="group" aria-label="Collections">
        {items === null && !error && (
          <div role="status" className="grid gap-1 py-1">
            <span className="sr">Loading collections…</span>
            {[64, 48, 56].map((width, index) => (
              <span key={width} aria-hidden className="ghost-enter flex h-8 items-center gap-2.5 px-2.5" style={{ "--enter": `${index * 40}ms` } as CSSProperties}>
                <Skeleton wave={index * 70} className="size-4 rounded" />
                <Skeleton wave={index * 70 + 40} className="h-3 rounded" style={{ width: `${width}%` }} />
              </span>
            ))}
          </div>
        )}
        {error && <p className="px-2.5 py-2 text-[12.5px] text-fault" role="alert">{error}</p>}
        {items !== null && !items.length && <p className="px-2.5 py-2 text-[12.5px] text-muted-foreground">No collections yet. Create one to start grouping assets.</p>}
        {items !== null && items.length > 0 && !shown.length && <p className="px-2.5 py-2 text-[12.5px] text-muted-foreground">No collection matches “{query.trim()}”.</p>}
        {shown.map((collection) => (
          <button
            key={collection.collection_id}
            type="button"
            role="menuitemcheckbox"
            aria-checked={Boolean(collection.contains)}
            data-flyout-item=""
            data-collection={collection.collection_id}
            title={collection.contains ? "Already in this collection; choose to remove it" : undefined}
            onClick={() => choose(collection)}
            className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-[13px] outline-none hover:bg-foreground/[0.065] focus-visible:bg-foreground/[0.065]"
          >
            <span className="grid size-4 shrink-0 place-items-center">{collection.contains && <Check className="size-3.5 text-primary" strokeWidth={2.4} aria-hidden />}</span>
            <span className="min-w-0 flex-1 truncate">{collection.name}</span>
            <span className="shrink-0 text-[11px] text-muted-foreground tabular-nums">{collection.asset_count}</span>
          </button>
        ))}
      </div>
    </motion.div>
    </>,
    document.body,
  );
}

function AssetMenuItems({ request }: { request: MenuRequest }) {
  const menu = useContextMenuState();
  const [flyout, setFlyout] = useState(false);
  const trigger = useRef<HTMLDivElement>(null);
  const hover = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const grid = request.grid!, item = request.item;
  useEffect(() => setFlyout(false), [request.id]);
  useEffect(() => () => clearTimeout(hover.current), []);
  const back = () => {
    setFlyout(false);
    trigger.current?.querySelector<HTMLElement>("[data-context-menu-item]")?.focus();
  };
  return (
    <div
      onKeyDown={(event) => {
        if (event.key === "ArrowRight" && trigger.current?.contains(document.activeElement)) {
          event.preventDefault();
          event.stopPropagation();
          setFlyout(true);
        }
      }}
      onPointerMove={(event) => {
        // Resting on "Add to a collection" opens it. Only resting on another row closes it:
        // gaps, padding and the trip toward the flyout never do, so a slow diagonal move is safe.
        const onTrigger = trigger.current?.contains(event.target as Node);
        const onOtherRow = !onTrigger && (event.target as Element).closest("[data-context-menu-item]");
        if (onTrigger && !flyout) {
          clearTimeout(hover.current);
          hover.current = setTimeout(() => setFlyout(true), 160);
        } else if (onOtherRow && flyout) {
          clearTimeout(hover.current);
          hover.current = setTimeout(() => setFlyout(false), 300);
        } else if (onTrigger) clearTimeout(hover.current);
      }}
    >
      <ContextMenuLabel className="max-w-64 truncate normal-case tracking-normal">{item.name}</ContextMenuLabel>
      <ContextMenuItem textValue="Inspect" onSelect={() => void selectAsset(grid, item.asset_id, null, "three_quarter", true)}>
        <ScanSearch className={ICON} aria-hidden />Inspect
      </ContextMenuItem>
      <div ref={trigger} data-menu-action="add-to-collection">
        <ContextMenuItem textValue="Add to a collection" closeOnSelect={false} onSelect={() => setFlyout(true)} className={flyout ? "bg-foreground/[0.065]" : undefined}>
          <FolderPlus className={ICON} aria-hidden />
          <span className="flex-1">Add to a collection</span>
          <ChevronRight className="size-3.5 text-muted-foreground" aria-hidden />
        </ContextMenuItem>
      </div>
      <ContextMenuItem textValue="Show in Explorer" onSelect={() => void revealAsset(grid, item.asset_id)}>
        <FolderSearch className={ICON} aria-hidden />Show in Explorer
      </ContextMenuItem>
      {grid === "collection" && (
        <>
          <ContextMenuSeparator />
          <ContextMenuItem tone="destructive" textValue="Remove from collection" onSelect={() => startSelection(item.asset_id)}>
            <ListX className="size-4 shrink-0" aria-hidden />Remove from collection…
          </ContextMenuItem>
        </>
      )}
      {flyout && menu.open && trigger.current && <CollectionFlyout anchor={trigger.current} grid={grid} item={item} onBack={back} onEnter={() => clearTimeout(hover.current)} />}
    </div>
  );
}

function CollectionMenuItems({ request }: { request: MenuRequest }) {
  const summary = request.item;
  return (
    <>
      <ContextMenuLabel className="max-w-64 truncate normal-case tracking-normal">{summary.name}</ContextMenuLabel>
      <ContextMenuItem textValue="Open" onSelect={() => openCollection(summary.collection_id)}>
        <FolderOpen className={ICON} aria-hidden />Open
      </ContextMenuItem>
      <ContextMenuSeparator />
      <ContextMenuItem tone="destructive" textValue="Delete" onSelect={() => confirmDeleteCollection(summary)}>
        <Trash2 className="size-4 shrink-0" aria-hidden />Delete…
      </ContextMenuItem>
    </>
  );
}

const EXPORTS: [kind: "json" | "png" | "md" | "pdf", label: string, hint: string][] = [
  ["json", "JSON for agents", "Members, labels, notes and file paths"],
  ["png", "Sample image", "A grid of visual assets with labels"],
  ["md", "Markdown", "Reference doc with thumbnails"],
  ["pdf", "PDF", "Printable reference doc"],
];
function ExportMenuItems({ request }: { request: MenuRequest }) {
  return (
    <>
      <ContextMenuLabel>Export collection</ContextMenuLabel>
      {EXPORTS.map(([kind, label, hint]) => (
        <ContextMenuItem key={kind} textValue={label} onSelect={() => void exportCollection(request.item.collection_id, kind)}>
          <span className="grid min-w-0 gap-0.5" data-export={kind}>
            <span>{label}</span>
            <span className="truncate text-[11.5px] text-muted-foreground">{hint}</span>
          </span>
        </ContextMenuItem>
      ))}
    </>
  );
}

/**
 * Under an open menu: a light dim and blur that puts the menu in focus, and a shield so a click
 * outside only closes the menu, never reaching the card or button underneath. Right-click on
 * another card moves the menu there in one step. The backdrop is still (scrolling closes menus),
 * so the blur is computed once rather than every frame.
 */
function MenuShield() {
  const menu = useContextMenuState();
  const reduce = useReducedMotion();
  const shield = useRef<HTMLDivElement>(null);
  const [hole, setHole] = useState<{ clip: string; rect: string } | undefined>(undefined);
  // The item the menu came from stays sharp: the shield is the window minus its rounded outline.
  // Scrolling and resizing close the menu; a layout change underneath (such as the inspection
  // panel opening or closing) resizes the item, and the observer moves the hole with it.
  useLayoutEffect(() => {
    if (!menu.open) return;
    const origin = menu.triggerRef.current;
    if (!origin?.isConnected) return setHole(undefined);
    const measure = () => {
      const box = origin.getBoundingClientRect(), pad = 2;
      const x = box.left - pad, y = box.top - pad, w = box.width + 2 * pad, h = box.height + 2 * pad;
      const r = Math.min(parseFloat(getComputedStyle(origin).borderTopLeftRadius) + pad || 0, w / 2, h / 2);
      const W = window.innerWidth, H = window.innerHeight;
      setHole({ rect: [x, y, w, h].map((v) => v.toFixed(1)).join(","), clip: `path(evenodd, "M0 0H${W}V${H}H0Z M${x + r} ${y}H${x + w - r}A${r} ${r} 0 0 1 ${x + w} ${y + r}V${y + h - r}` +
        `A${r} ${r} 0 0 1 ${x + w - r} ${y + h}H${x + r}A${r} ${r} 0 0 1 ${x} ${y + h - r}V${y + r}A${r} ${r} 0 0 1 ${x + r} ${y}Z")` });
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(origin);
    return () => observer.disconnect();
  }, [menu.open, menu.invocation, menu.triggerRef]);
  const reopen = (event: ReactMouseEvent) => {
    event.preventDefault();
    const element = shield.current;
    if (!element) return;
    element.style.pointerEvents = "none";
    const below = document.elementFromPoint(event.clientX, event.clientY);
    element.style.pointerEvents = "";
    const target = below?.closest<HTMLElement>(".card[data-id], .collection-card");
    if (target) target.dispatchEvent(new MouseEvent("contextmenu", { bubbles: true, cancelable: true, clientX: event.clientX, clientY: event.clientY, button: 2 }));
    else menu.setOpen(false);
  };
  return createPortal(
    <AnimatePresence>
      {menu.open && (
        <motion.div
          key="menu-shield"
          ref={shield}
          id="menu-shield"
          aria-hidden
          data-context-menu-layer={menu.menuId}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0, transition: { duration: reduce ? 0 : 0.1 } }}
          transition={{ duration: reduce ? 0 : 0.12 }}
          // The press must not close the menu yet: the click that follows would land on what is below.
          onPointerDown={(event) => event.stopPropagation()}
          onClick={() => menu.setOpen(false)}
          onWheel={() => menu.setOpen(false)}
          onContextMenu={reopen}
          style={{ clipPath: hole?.clip }}
          data-hole={hole?.rect}
          className="fixed inset-0 z-[99] bg-black/[0.08] backdrop-blur-[1.5px] dark:bg-black/20"
        />
      )}
    </AnimatePresence>,
    document.body,
  );
}

/** One shared menu for asset cards, collection cards and the export button. */
export function AppMenus() {
  const request = useApp((s) => s.menu);
  // The last request stays rendered while the menu animates closed.
  const last = useRef<MenuRequest | null>(null);
  if (request) last.current = request;
  const shown = request ?? last.current;
  return (
    <ContextMenu
      request={request && { id: request.id, x: request.x, y: request.y, modality: request.keyboard ? "keyboard" : "pointer", returnFocus: request.returnFocus }}
      onOpenChange={(open) => !open && closeMenu()}
    >
      <MenuShield />
      <ContextMenuContent ariaLabel={{ asset: "Asset actions", collection: "Collection actions", export: "Export collection" }[shown?.kind ?? "asset"]} className="w-64">
        {shown?.kind === "asset" && <AssetMenuItems request={shown} />}
        {shown?.kind === "collection" && <CollectionMenuItems request={shown} />}
        {shown?.kind === "export" && <ExportMenuItems request={shown} />}
      </ContextMenuContent>
    </ContextMenu>
  );
}

function useModal(open: boolean) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (open && !dialog.current?.open) {
      dialog.current?.showModal();
      // showModal focuses the first control (the close button); the intended field wins.
      dialog.current?.querySelector<HTMLElement>("[data-autofocus]")?.focus();
    }
    if (!open && dialog.current?.open) dialog.current.close();
  }, [open]);
  return dialog;
}

/** Every deletion is confirmed here; only the red button deletes. */
export function ConfirmDialog() {
  const request = useApp((s) => s.confirm);
  const dialog = useModal(Boolean(request));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setBusy(false);
    setError(null);
  }, [request]);
  const neutral = request?.tone === "neutral";
  const confirm = async () => {
    if (!request?.run) return;
    setBusy(true);
    try {
      const result = (await request.run()) as Json;
      if (result && result.status === "faulty") throw Error(result.reason);
      closeConfirm();
    } catch (reason) {
      setError((reason as Error).message);
      setBusy(false);
    }
  };
  return (
    <dialog
      ref={dialog}
      id="confirm-dialog"
      aria-labelledby="confirm-title"
      aria-describedby="confirm-body"
      onCancel={(event) => { event.preventDefault(); if (!busy) closeConfirm(); }}
      className="m-auto w-[min(460px,calc(100vw-32px))] rounded-[24px] border border-border bg-surface p-0 text-foreground shadow-panel backdrop:bg-black/35"
    >
      {request && (
        <div className="grid gap-4 p-6">
          <div className="flex items-start gap-3">
            <span aria-hidden className={cn("grid size-10 shrink-0 place-items-center rounded-full", neutral ? "bg-surface-2 text-primary" : "bg-fault-bg text-fault")}>
              {neutral ? <RotateCcw className="size-[18px]" /> : <Trash2 className="size-[18px]" />}
            </span>
            <div className="min-w-0">
              <h2 id="confirm-title" className="text-[17px] font-semibold break-words">{request.title}</h2>
              <p id="confirm-body" className="mt-1.5 text-[13px] leading-relaxed text-muted-foreground">{request.body}</p>
            </div>
          </div>
          {error && <p role="alert" className="rounded-xl bg-fault-bg px-4 py-3 text-[12.5px] text-fault">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button variant="secondary" id="confirm-cancel" data-autofocus="" disabled={busy} onClick={closeConfirm}>{request.run ? "Cancel" : "Close"}</Button>
            {request.run && (
              <Button variant={neutral ? "primary" : "destructive"} id="confirm-accept" disabled={busy} onClick={() => void confirm()}>
                {busy && <Spinner className="size-3.5" />}{request.confirmLabel}
              </Button>
            )}
          </div>
        </div>
      )}
    </dialog>
  );
}

/** Title and description for a new collection; from a menu it also adds that asset. */
export function CreateCollectionDialog() {
  const request = useApp((s) => s.create);
  const page = useApp((s) => s.history[s.historyIndex].page);
  const dialog = useModal(Boolean(request));
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setName(request?.name ?? "");
    setDescription("");
    setBusy(false);
    setError(null);
  }, [request]);
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!request || !name.trim()) return;
    setBusy(true);
    try {
      const result = await createCollection(name, description, request.assetIds, request.sourceKey);
      closeCreateCollection();
      // From the Collections tab the new, empty collection opens and explains how to fill it.
      if (!request.assetIds.length && page === "collections") openCollection(result.collection_id);
    } catch (reason) {
      setError((reason as Error).message);
      setBusy(false);
    }
  };
  const adding = Boolean(request?.assetIds.length);
  return (
    <dialog
      ref={dialog}
      id="create-collection-dialog"
      aria-labelledby="create-collection-title"
      onCancel={(event) => { event.preventDefault(); if (!busy) closeCreateCollection(); }}
      className="m-auto w-[min(520px,calc(100vw-32px))] rounded-[24px] border border-border bg-surface p-0 text-foreground shadow-panel backdrop:bg-black/35"
    >
      {request && (
        <form className="grid gap-4 p-6" onSubmit={(event) => void submit(event)}>
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 id="create-collection-title" className="text-[17px] font-semibold">New collection</h2>
              <p className="mt-1 text-[12.5px] text-muted-foreground">
                {adding ? `The selected ${plural(request.assetIds.length, "asset is", "assets are")} added to it.` : "Group assets from any source. Files stay where they are."}
              </p>
            </div>
            <IconButton label="Close" onClick={closeCreateCollection} disabled={busy} className="size-9"><X className="size-4" /></IconButton>
          </div>
          <div className="grid gap-1.5">
            <label htmlFor="collection-name" className="text-xs text-muted-foreground">Title</label>
            <input
              id="collection-name"
              data-autofocus=""
              required
              maxLength={80}
              value={name}
              onChange={(event) => { setName(event.target.value); setError(null); }}
              placeholder="For example: Aquarium minigame"
              className="h-11 rounded-xl border border-border bg-surface px-3 text-[13px] outline-none hover:border-border-strong focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-ring/25"
            />
          </div>
          <div className="grid gap-1.5">
            <label htmlFor="collection-description" className="text-xs text-muted-foreground">Description <span className="text-subtle">(optional)</span></label>
            <textarea
              id="collection-description"
              maxLength={2000}
              rows={3}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="What the collection is for"
              className="resize-none rounded-xl border border-border bg-surface px-3 py-2.5 text-[13px] leading-relaxed outline-none hover:border-border-strong focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-ring/25"
            />
          </div>
          {error && <p role="alert" id="create-collection-error" className="rounded-xl bg-fault-bg px-4 py-3 text-[12.5px] text-fault">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="secondary" disabled={busy} onClick={closeCreateCollection}>Cancel</Button>
            <Button type="submit" id="create-collection-submit" disabled={busy || !name.trim()}>{busy && <Spinner className="size-3.5" />}{adding ? "Create and add" : "Create collection"}</Button>
          </div>
        </form>
      )}
    </dialog>
  );
}

/** Floating bar while choosing assets to remove together, like forwarding several messages. */
export function SelectionBar({ onSelectAll, onRemove, onCancel, count, total }: { onSelectAll: () => void; onRemove: () => void; onCancel: () => void; count: number; total: number }) {
  const reduce = useReducedMotion();
  return (
    <AnimatePresence>
      <motion.div
        id="selection-bar"
        role="toolbar"
        aria-label="Selected assets"
        initial={reduce ? { opacity: 0 } : { opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        exit={reduce ? { opacity: 0 } : { opacity: 0, y: 16 }}
        transition={SPRING_PANEL}
        className="pointer-events-auto sticky bottom-5 z-10 mx-auto flex w-fit max-w-full flex-wrap items-center gap-2 rounded-2xl border border-border bg-surface py-2 pr-2 pl-4 shadow-panel"
      >
        <span id="selection-count" role="status" aria-live="polite" className="mr-2 text-[13px] font-medium tabular-nums">
          {count ? `${plural(count, "asset", "assets")} selected` : "Select assets to remove"}
        </span>
        <Button variant="quiet" className="h-9 px-3 text-[12.5px]" id="selection-all" disabled={count === total} onClick={onSelectAll}>Select all</Button>
        <Button variant="danger" className={cn("h-9 px-4 text-[12.5px]")} id="selection-remove" disabled={!count} onClick={onRemove}>
          <ListX className="size-4" aria-hidden />Remove from collection
        </Button>
        <Button variant="secondary" className="h-9 px-4 text-[12.5px]" id="selection-cancel" onClick={onCancel}>Cancel</Button>
      </motion.div>
    </AnimatePresence>
  );
}
