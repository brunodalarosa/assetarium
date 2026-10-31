import { Check, Copy, FlaskConical, X } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useState } from "react";
import { SPRING_PANEL } from "@/lib/ease";
import { cn } from "@/lib/utils";
import type { Json } from "../app/api";
import { cancelModelCheck, checkServer, copyText, loadModelCheck, startModelCheck, useApp } from "../app/store";
import { Badge, Button, Card, SelectField, Spinner, TextField } from "./primitives";

const FAMILY: Record<string, string> = {
  engine_copy: "Engine copies", material_folders: "Material folders", oversized: "Big name sets", version_folder: "Version folders",
  image_kind_texture: "Texture folders", image_kind_image: "Sprite folders", fine_variants: "Variants left alone", fine_series: "Series left alone",
};
const TONE: Record<string, "neutral" | "warning" | "fault"> = { good: "neutral", review: "warning", weak: "fault" };
export const MODEL_CHECK_HELP =
  "Your AI agent structures packs through Assetarium's tools. This runs a model on this computer through 8 made-up packs (names only, nothing of yours) and checks what it gets right: engine copies, version folders, texture and sprite folders, and leaving good packs alone. About 5 minutes.";

/** Check my model (decision 0024): pick a local model server and model, run the check, read the verdict. */
export function ModelCheck({ id = "model-check" }: { id?: string }) {
  const check = useApp((s) => s.modelCheck);
  const [url, setUrl] = useState("http://127.0.0.1:1234/v1");
  const [models, setModels] = useState<string[]>([]);
  const [model, setModel] = useState("");
  const [probe, setProbe] = useState<Json | null>(null);
  const [listing, setListing] = useState(false);
  useEffect(() => {
    void loadModelCheck();
  }, []);
  useEffect(() => {
    if (check?.last?.url && url === "http://127.0.0.1:1234/v1") setUrl(check.last.url);
    if (check?.last?.model && !model) setModel(check.last.model);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [check?.last?.url, check?.last?.model]);
  const list = async () => {
    setListing(true);
    const found = await checkServer(url, model);
    setListing(false);
    setProbe(found);
    if (found.status === "connected") {
      setModels(found.models || []);
      if (!model || !(found.models || []).includes(model)) setModel(found.models?.[0] || "");
    }
  };
  const job = check?.job, running = !!check?.running, last: Json | null = job?.report || check?.last || null;
  return (
    <div id={id} className="grid gap-4">
      <div className="flex flex-wrap items-end gap-3">
        <TextField id={id + "-url"} label="Model server on this computer" value={url} onChange={(e) => setUrl(e.target.value)} className="min-w-[260px] flex-1" disabled={running} />
        <Button variant="secondary" className="h-10 px-4" disabled={running || listing} onClick={() => void list()}>{listing ? <Spinner className="size-4" /> : null}List models</Button>
      </div>
      {probe && probe.status !== "connected" && <p className="text-[12.5px] text-fault">{probe.reason}</p>}
      {models.length > 0 && (
        <SelectField id={id + "-model"} label="Model" value={model} onChange={setModel} options={models.map((m): [string, string] => [m, m])} className="w-80" disabled={running} />
      )}
      {running ? (
        <div className="grid gap-2" role="status">
          <div className="h-2 overflow-hidden rounded-full bg-surface-2">
            <motion.div className="h-full rounded-full bg-primary" animate={{ width: `${job.total ? (job.index / job.total) * 100 : 3}%` }} transition={SPRING_PANEL} />
          </div>
          <p className="flex flex-wrap items-center gap-2 text-[12.5px] text-muted-foreground">
            <Spinner className="size-3.5" />{job.total ? `Pack ${job.index + 1} of ${job.total} · ${job.tree}` : "Starting…"} · {job.model}
            <Button variant="quiet" className="h-7 px-2" onClick={() => void cancelModelCheck()}><X className="size-3.5" aria-hidden />Stop</Button>
          </p>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-3">
          <Button id={id + "-start"} disabled={!model} onClick={() => void startModelCheck(url, model)}><FlaskConical className="size-4" aria-hidden />Check my model</Button>
          {!model && <span className="text-[12px] text-muted-foreground">List the server’s models first.</span>}
        </div>
      )}
      {job?.reason && !running && <p className="text-[12.5px] text-fault">{job.reason}</p>}
      {last && !running && (
        <div id={id + "-result"} className="grid gap-2.5 rounded-2xl border border-border bg-surface-2/50 p-4" data-verdict={last.verdict}>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[20px] font-semibold tabular-nums">{last.passed}/{last.total}</span>
            <Badge tone={TONE[last.verdict] || "neutral"}>{last.verdict_text}</Badge>
            <span className="text-[12px] text-muted-foreground">{last.model} · {new Date(last.utc).toLocaleString()}</span>
          </div>
          <ul className="flex flex-wrap gap-1.5">
            {Object.entries(last.families || {}).map(([family, [ok, all]]: [string, any]) => (
              <li key={family} className={cn("inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11.5px]", ok === all ? "border-border" : "border-warning/50 text-warning")}>
                {ok === all ? <Check className="size-3" aria-hidden /> : <X className="size-3" aria-hidden />}{FAMILY[family] || family}
              </li>
            ))}
          </ul>
          <div><Button variant="quiet" className="h-7 px-2 text-[12px]" onClick={() => void copyText(last.report, "Report path copied")}><Copy className="size-3.5" aria-hidden />Copy report path</Button></div>
        </div>
      )}
    </div>
  );
}

export function ModelCheckCard() {
  return <Card id="model-check-card" title="Check my model" help={MODEL_CHECK_HELP}><ModelCheck /></Card>;
}
