import { useEffect } from "react";
import { TooltipProvider } from "@/components/beui/tooltip";
import { getState, goBack, goForward, navigate, setInspectorOpen, useApp } from "./app/store";
import { Home } from "./pages/Home";
import { Collection } from "./pages/Collection";
import { Collections } from "./pages/Collections";
import { Placeholder } from "./pages/Placeholder";
import { Processing } from "./pages/Processing";
import { Settings } from "./pages/Settings";
import { SourceBrowser } from "./pages/SourceBrowser";
import { Inspector } from "./ui/Inspector";
import { AppMenus, ConfirmDialog, CreateCollectionDialog } from "./ui/Menus";
import { NotificationsPanel, RunReport, Toasts } from "./ui/Notifications";
import { SetupWizard } from "./ui/SetupWizard";
import { Rail, TopBar } from "./ui/Shell";

function Page() {
  const current = useApp((s) => s.history[s.historyIndex]);
  switch (current.page) {
    case "library":
      return <Placeholder page="library" />;
    case "collections":
      return <Collections />;
    case "collection":
      return <Collection key={current.key} collectionId={current.key!} />;
    case "processing":
      return <Processing focus={current.focus} />;
    case "settings":
      return <Settings tab={current.tab} />;
    case "source":
      return <SourceBrowser sourceKey={current.key!} />;
    default:
      return <Home />;
  }
}

/** Each page fades in when it opens; staying on a page (a new search, a refresh) does not replay it. */
function PageFrame() {
  const current = useApp((s) => s.history[s.historyIndex]);
  return (
    <div key={current.page + ":" + (current.key ?? "")} className="page-enter h-full">
      <Page />
    </div>
  );
}

function useGlobalKeys() {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (getState().setup.open) return; // Setup owns the window until it closes.
      const preview = window.LALPreview?.current;
      if (preview?.dialog.open && event.key === "Escape") {
        event.preventDefault();
        if (preview.fullscreen) preview.exitFullscreen();
        else preview.stop();
        return;
      }
      if (preview?.fullscreen) return;
      if (event.ctrlKey && event.key.toLowerCase() === "f") {
        event.preventDefault();
        if (getState().history[getState().historyIndex].page !== "home") navigate({ page: "home" });
        requestAnimationFrame(() => document.getElementById("query")?.focus());
        return;
      }
      // Escape outside any overlay hides inspection; the selection is kept.
      const s = getState();
      const target = event.target as HTMLElement;
      if (event.key === "Escape" && !event.defaultPrevented && s.inspector.open && !s.filtersOpen && !s.notificationsOpen && !s.runReport && !target.closest('[role="listbox"], [aria-haspopup="listbox"], input, textarea, dialog')) {
        setInspectorOpen(false);
        document.getElementById("toggle-inspector")?.focus();
      }
    };
    // Dedicated mouse buttons: 3 is Back, 4 is Forward, same as the rail arrows.
    const onMouse = (event: MouseEvent) => {
      if (event.button !== 3 && event.button !== 4) return;
      event.preventDefault();
      if (getState().setup.open || window.LALPreview?.current?.fullscreen) return;
      if (event.button === 3) goBack();
      else goForward();
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("mouseup", onMouse);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("mouseup", onMouse);
    };
  }, []);
}

export function App() {
  useGlobalKeys();
  const setupOpen = useApp((s) => s.setup.open);
  return (
    <TooltipProvider>
      {/* Setup covers the whole window; the app behind it is inert until setup closes. */}
      <div className="flex h-full bg-background text-foreground" inert={setupOpen || undefined}>
        <Rail />
        <div className="flex min-w-0 flex-1 flex-col">
          <TopBar />
          <div className="relative flex min-h-0 flex-1">
            <main className="min-w-0 flex-1">
              <PageFrame />
            </main>
            <Inspector />
          </div>
        </div>
      </div>
      <NotificationsPanel />
      <SetupWizard />
      <Toasts />
      <RunReport />
      <AppMenus />
      <ConfirmDialog />
      <CreateCollectionDialog />
    </TooltipProvider>
  );
}
