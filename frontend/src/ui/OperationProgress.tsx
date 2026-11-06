import { Tooltip } from "@/components/beui/tooltip";
import type { Json } from "../app/api";
import { progressInfo } from "../app/format";
import { Progress } from "./primitives";

/** One measured value stays visible; phase, remaining work and outcomes are available on hover and focus. */
export function OperationProgress({ operation, label }: { operation: Json; label: string }) {
  const info = progressInfo(operation);
  return <Tooltip content={info.detail}>
    <div tabIndex={0} className="operation-progress grid gap-1.5 rounded-sm outline-none focus-visible:ring-2 focus-visible:ring-primary/40">
      <span className="text-right text-[11.5px] text-muted-foreground tabular-nums">{info.label}</span>
      <Progress value={info.value} label={label} valueText={info.detail} />
    </div>
  </Tooltip>;
}
