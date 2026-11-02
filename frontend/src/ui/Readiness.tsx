import { Check, CircleAlert } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Json } from "../app/api";
import { CommandBlock } from "./CommandBlock";
import { Spinner } from "./primitives";

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
          {item.command && <div className="pl-7"><CommandBlock command={item.command} /></div>}
        </li>
      ))}
    </ul>
  );
}
