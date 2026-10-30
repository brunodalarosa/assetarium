import { Check, CircleAlert, Copy } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Json } from "../app/api";
import { copyText } from "../app/store";
import { Button, Spinner } from "./primitives";

export function CopyCommand({ command }: { command: string }) {
  return (
    <div className="flex min-w-0 items-center gap-2 rounded-xl bg-surface-2 py-1.5 pr-1.5 pl-3">
      <code className="min-w-0 flex-1 break-all font-mono text-[11.5px] text-foreground select-text">{command}</code>
      <Button variant="quiet" className="h-8 shrink-0 px-3 text-[12px]" onClick={() => void copyText(command, "Command copied. Run it in a terminal in the Assetarium folder.")}>
        <Copy className="size-3.5" aria-hidden />Copy
      </Button>
    </div>
  );
}

/** One checklist of what is installed, with the command for anything missing. */
export function ReadinessList({ id, items }: { id: string; items?: Json[] }) {
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
          {item.command && <div className="pl-7"><CopyCommand command={item.command} /></div>}
        </li>
      ))}
    </ul>
  );
}
