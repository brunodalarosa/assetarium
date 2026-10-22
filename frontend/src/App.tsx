import { useEffect } from "react";
import { TooltipProvider } from "@/components/beui/tooltip";
import { getState, navigate, setInspectorOpen, useApp } from "./app/store";
import { Home } from "./pages/Home";
import { Placeholder } from "./pages/Placeholder";
import { Processing } from "./pages/Processing";
import { Settings } from "./pages/Settings";
import { SourceBrowser } from "./pages/SourceBrowser";
import { Inspector } from "./ui/Inspector";
import { NotificationsPanel, RunReport, Toasts } from "./ui/Notifications";
import { Rail, TopBar } from "./ui/Shell";

function Page() {
  const current = useApp((s) => s.history[s.historyIndex]);
  switch (current.page) {
    case "library":
    case "collections":
      return <Placeholder page={current.page} />;
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

function useGlobalKeys() {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
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
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
}

export function App() {
  useGlobalKeys();
  return (
    <TooltipProvider>
      <div className="flex h-full bg-background text-foreground">
        <Rail />
        <div className="flex min-w-0 flex-1 flex-col">
          <TopBar />
          <div className="relative flex min-h-0 flex-1">
            <main className="min-w-0 flex-1">
              <Page />
            </main>
            <Inspector />
          </div>
        </div>
      </div>
      <NotificationsPanel />
      <Toasts />
      <RunReport />
    </TooltipProvider>
  );
}
