import { ArrowLeft, ArrowRight, Bell, House, LayoutGrid, LibraryBig, PanelRight, Settings, Workflow } from "lucide-react";
import { motion } from "motion/react";
import type { ReactNode } from "react";
import { Tooltip } from "@/components/beui/tooltip";
import { SPRING_LAYOUT } from "@/lib/ease";
import { cn } from "@/lib/utils";
import { plural } from "../app/format";
import { goBack, goForward, navigate, type Page, processingAttention, runningDescriptions, setInspectorOpen, setNotificationsOpen, useApp } from "../app/store";
import { IconButton } from "./primitives";

const NAV: { page: Page; label: string; icon: ReactNode }[] = [
  { page: "home", label: "Home", icon: <House className="size-5" strokeWidth={1.75} /> },
  { page: "library", label: "Library", icon: <LibraryBig className="size-5" strokeWidth={1.75} /> },
  { page: "collections", label: "Collections", icon: <LayoutGrid className="size-5" strokeWidth={1.75} /> },
  { page: "processing", label: "Asset processing", icon: <Workflow className="size-5" strokeWidth={1.75} /> },
];

function RailItem({ page, label, icon, dot }: { page: Page; label: string; icon: ReactNode; dot?: boolean }) {
  const current = useApp((s) => s.history[s.historyIndex].page);
  const active = current === page || (page === "settings" && current === "source");
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

export function TopBar() {
  const unread = useApp((s) => s.notifications.filter((item) => !item.read).length);
  const running = useApp((s) => runningDescriptions(s).length > 0);
  const notificationsOpen = useApp((s) => s.notificationsOpen);
  const inspectorOpen = useApp((s) => s.inspector.open);
  const label = `Notifications${unread ? ", " + plural(unread, "unread", "unread") : ""}${running ? ", description run in progress" : ""}`;
  return (
    <header className="flex h-[76px] shrink-0 items-center justify-between pr-4 pl-6">
      <span className="text-[13px] text-muted-foreground">Assetarium</span>
      <div className="flex items-center gap-3">
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
          {(unread > 0 || running) && (
            <span id="notifications-count" data-count={unread} className={cn("absolute top-1.5 right-2 size-2 rounded-full bg-primary ring-2 ring-background", running && !unread && "animate-[pulse-dot_1.6s_ease-in-out_infinite]")} aria-hidden />
          )}
        </IconButton>
        <IconButton id="toggle-inspector" label={inspectorOpen ? "Hide asset inspection" : "Show asset inspection"} aria-pressed={inspectorOpen} aria-controls="inspector" active={inspectorOpen} onClick={() => setInspectorOpen(!inspectorOpen)}>
          <PanelRight className="size-5" strokeWidth={1.75} />
        </IconButton>
      </div>
    </header>
  );
}
