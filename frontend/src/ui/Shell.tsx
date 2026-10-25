import { ArrowLeft, ArrowRight, Bell, House, LayoutGrid, PanelRight, Pencil, Settings, Workflow } from "lucide-react";
import { motion } from "motion/react";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { Tooltip } from "@/components/beui/tooltip";
import { SPRING_LAYOUT } from "@/lib/ease";
import { cn } from "@/lib/utils";
import { plural } from "../app/format";
import { goBack, goForward, navigate, type Page, processingAttention, setInspectorOpen, setNotificationsOpen, updateCollection, useApp } from "../app/store";
import { ActivityIndicator } from "./Activity";
import { Skeleton } from "./Loading";
import { IconButton } from "./primitives";

const NAV: { page: Page; label: string; icon: ReactNode }[] = [
  { page: "home", label: "Home", icon: <House className="size-5" strokeWidth={1.75} /> },
  { page: "collections", label: "Collections", icon: <LayoutGrid className="size-5" strokeWidth={1.75} /> },
  { page: "processing", label: "Asset processing", icon: <Workflow className="size-5" strokeWidth={1.75} /> },
];

function RailItem({ page, label, icon, dot }: { page: Page; label: string; icon: ReactNode; dot?: boolean }) {
  const current = useApp((s) => s.history[s.historyIndex].page);
  const active = current === page || (page === "settings" && current === "source") || (page === "collections" && current === "collection");
  return (
    <Tooltip content={label} side="right" delay={250}>
      <button
        type="button"
        id={`nav-${page}`}
        aria-label={label + (dot ? ", needs attention" : "")}
        aria-current={active ? "page" : undefined}
        onClick={() => navigate(page === "settings" ? { page, tab: "general" } : { page })}
        className={cn("relative grid size-11 place-items-center rounded-xl transition-colors", active ? "text-accent-soft-foreground" : "text-foreground/80 hover:bg-surface-2/70 hover:text-foreground")}
      >
        {active && <motion.span layoutId="rail-active" transition={SPRING_LAYOUT} className="absolute inset-0 rounded-xl bg-accent-soft" />}
        <span className="relative">{icon}</span>
        {dot && <span className="absolute top-2 right-2 size-2 rounded-full bg-primary ring-2 ring-rail" aria-hidden />}
      </button>
    </Tooltip>
  );
}

export function Rail() {
  const canBack = useApp((s) => s.historyIndex > 0);
  const canForward = useApp((s) => s.historyIndex < s.history.length - 1);
  const attention = useApp(processingAttention);
  return (
    <nav aria-label="Main" className="flex w-24 shrink-0 flex-col items-center bg-rail pt-4 pb-5">
      <div className="flex gap-1">
        <IconButton label="Back" onClick={goBack} disabled={!canBack} side="right" className="size-8 rounded-lg text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-4" />
        </IconButton>
        <IconButton label="Forward" onClick={goForward} disabled={!canForward} side="right" className="size-8 rounded-lg text-muted-foreground hover:text-foreground">
          <ArrowRight className="size-4" />
        </IconButton>
      </div>
      <div className="mt-8 flex flex-col items-center gap-4">
        {NAV.map((item) => <RailItem key={item.page} {...item} dot={item.page === "processing" && attention} />)}
      </div>
      <div className="mt-auto">
        <RailItem page="settings" label="Settings" icon={<Settings className="size-5" strokeWidth={1.75} />} />
      </div>
    </nav>
  );
}

/** Empty, or the open collection's name with a pencil that renames it in place. */
function TopTitle() {
  const page = useApp((s) => s.history[s.historyIndex].page);
  const view = useApp((s) => s.collectionView);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => setEditing(false), [view.id, page]);
  useEffect(() => {
    if (editing) input.current?.select();
  }, [editing]);
  if (page !== "collection") return <span />;
  if (!view.name && view.loading) return <Skeleton className="ghost-enter h-7 w-56 rounded-lg" />;
  const finish = () => {
    setEditing(false);
    requestAnimationFrame(() => document.getElementById("rename-collection")?.focus());
  };
  const save = async () => {
    const name = draft.trim();
    if (!name || name === view.name) return finish();
    setBusy(true);
    try {
      await updateCollection(view.id!, { name });
      finish();
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  };
  if (editing)
    return (
      <form className="flex min-w-0 items-center gap-2" onSubmit={(event) => { event.preventDefault(); void save(); }}>
        <label htmlFor="collection-rename" className="sr">Collection name</label>
        <input
          id="collection-rename"
          ref={input}
          value={draft}
          maxLength={80}
          disabled={busy}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? "collection-rename-error" : undefined}
          onChange={(event) => { setDraft(event.target.value); setError(null); }}
          onBlur={() => !error && void save()}
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              event.preventDefault();
              event.stopPropagation();
              setError(null);
              finish();
            }
          }}
          className="h-10 w-[min(440px,50vw)] min-w-0 rounded-xl border border-primary bg-surface px-3 text-[22px] font-semibold text-foreground outline-none ring-2 ring-ring/25"
        />
        {error && <span id="collection-rename-error" role="alert" className="truncate text-[12px] text-fault">{error}</span>}
      </form>
    );
  return (
    <div className="flex min-w-0 items-center gap-1">
      <h1 id="collection-title" className="truncate text-[24px] font-semibold text-foreground" title={view.name}>{view.name || "Collection"}</h1>
      <IconButton id="rename-collection" label="Rename collection" disabled={!view.name} onClick={() => { setDraft(view.name); setError(null); setEditing(true); }} className="size-8 shrink-0 rounded-lg text-muted-foreground">
        <Pencil className="size-4" />
      </IconButton>
    </div>
  );
}

export function TopBar() {
  const unread = useApp((s) => s.notifications.filter((item) => !item.read).length);
  const notificationsOpen = useApp((s) => s.notificationsOpen);
  const inspectorOpen = useApp((s) => s.inspector.open);
  const label = `Notifications${unread ? ", " + plural(unread, "unread", "unread") : ""}`;
  return (
    <header className="flex h-[76px] shrink-0 items-center justify-between pr-4 pl-6">
      <TopTitle />
      <div className="flex items-center gap-3">
        <ActivityIndicator />
        <IconButton
          id="open-notifications"
          label={label}
          aria-haspopup="dialog"
          aria-expanded={notificationsOpen}
          aria-controls="notifications-panel"
          active={notificationsOpen}
          onClick={() => setNotificationsOpen(!notificationsOpen)}
          data-notifications-anchor=""
        >
          <Bell className="size-5" strokeWidth={1.75} />
          {unread > 0 && <span id="notifications-count" data-count={unread} className="absolute top-1.5 right-2 size-2 rounded-full bg-primary ring-2 ring-background" aria-hidden />}
        </IconButton>
        <IconButton id="toggle-inspector" label={inspectorOpen ? "Hide asset inspection" : "Show asset inspection"} aria-pressed={inspectorOpen} aria-controls="inspector" active={inspectorOpen} onClick={() => setInspectorOpen(!inspectorOpen)}>
          <PanelRight className="size-5" strokeWidth={1.75} />
        </IconButton>
      </div>
    </header>
  );
}
