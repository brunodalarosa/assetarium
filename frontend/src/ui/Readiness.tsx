import { Check, CircleAlert, Play } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import type { Json } from "../app/api";
import { searchCheck } from "../app/store";
import { CommandBlock, Reason } from "./CommandBlock";
import { Button, Spinner } from "./primitives";

/** Run check (design principle P3): the app runs the search check on built-in samples instead of asking for a command. */
export function SearchCheckButton({ onReady }: { onReady?: () => void }) {
  const [check, setCheck] = useState<Json>({ status: "missing" });
  const timer = useRef<ReturnType<typeof setInterval>>(undefined);
  const poll = () => {
    clearInterval(timer.current);
    timer.current = setInterval(async () => {
      const now = await searchCheck("status");
      setCheck(now);
      if (now.status !== "running") {
        clearInterval(timer.current);
        if (now.status === "ready") onReady?.();
      }
    }, 1500);
  };
  useEffect(() => {
    void searchCheck("status").then((now) => { setCheck(now); if (now.status === "running") poll(); });
    return () => clearInterval(timer.current);
  }, []);
  const run = async () => {
    const started = await searchCheck("start");
    setCheck(started.status === "faulty" ? { status: "failed", reason: started.reason } : { status: "running", phase: "Starting the search check" });
    if (started.status !== "faulty") poll();
  };
  return (
    <div className="search-check grid gap-1.5" data-state={check.status}>
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="secondary" className="h-8 px-3 text-[12px]" data-action="run-search-check" disabled={check.status === "running"} tooltip="Runs search on built-in sample assets to confirm it works on this computer; your assets are not used" onClick={() => void run()}>
          {check.status === "running" ? <Spinner /> : <Play className="size-3.5" aria-hidden />}{check.status === "failed" ? "Run check again" : "Run check"}
        </Button>
        {check.status === "running" && <span role="status" className="text-[12px] text-muted-foreground">{check.phase || "Running…"}</span>}
      </div>
      {check.status === "failed" && <Reason text={check.reason} className="text-[12px] text-fault" />}
    </div>
  );
}

/** One checklist of what is installed, with the command for anything missing. */
export function ReadinessList({ id, items, onChanged }: { id: string; items?: Json[]; onChanged?: () => void }) {
  if (!items) return <p className="flex items-center gap-2 text-[13px] text-muted-foreground" role="status"><Spinner />Checking what is installed…</p>;
  return (
    <ul id={id} className="grid gap-3" aria-label="Readiness">
      {items.map((item: Json) => (
        <li key={item.id} className="grid gap-1.5" data-item={item.id} data-ready={item.ready}>
          <span className="flex items-center gap-2 text-[13px]">
            <span className={cn("grid size-5 place-items-center rounded-full", item.ready ? "bg-success-bg text-success" : "bg-surface-2 text-muted-foreground")}>
              {item.ready ? <Check className="size-3" aria-hidden /> : <CircleAlert className="size-3" aria-hidden />}
            </span>
            <span className="font-medium">{item.label}</span>
            <span className="text-muted-foreground">{item.ready ? "Ready" : "Missing"}</span>
          </span>
          {!item.ready && item.detail && <span className="pl-7 text-[12px] text-muted-foreground">{item.detail}</span>}
          {item.command && <div className="pl-7"><CommandBlock command={item.command} /></div>}
          {item.action === "search_check" && onChanged && <div className="pl-7"><SearchCheckButton onReady={onChanged} /></div>}
        </li>
      ))}
    </ul>
  );
}
