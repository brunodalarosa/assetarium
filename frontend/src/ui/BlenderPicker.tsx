import { Check, CircleAlert, Copy, FolderOpen, TriangleAlert } from "lucide-react";
import { Checkbox } from "@/components/beui/checkbox";
import { cn } from "@/lib/utils";
import type { Json } from "../app/api";
import { plural } from "../app/format";
import { copyText } from "../app/store";
import { Banner, Button, RadioCards, Spinner } from "./primitives";

const CHECK_STATUS: Record<string, string> = { passed: "Ready.", warning: "Works, with a warning.", failed: "This executable can’t be used.", cancelled: "Check cancelled." };

/** One line per check (name, version, headless start, importers). */
export function BlenderChecks({ check, idPrefix = "settings" }: { check: Json; idPrefix?: string }) {
  return (
    <ul id={`${idPrefix}-blender-checks`} className="grid gap-2" aria-label="Blender checks">
      {check.checks.map((item: Json) => (
        <li key={item.id} className="grid grid-cols-[auto_minmax(0,1fr)] items-start gap-2.5 text-[13px]" data-check={item.id} data-status={item.status}>
          <span className={cn("mt-0.5 grid size-5 place-items-center rounded-full", item.status === "passed" ? "bg-success-bg text-success" : item.status === "warning" ? "bg-warning-bg text-warning" : "bg-fault-bg text-fault")}>
            {item.status === "passed" ? <Check className="size-3" aria-hidden /> : item.status === "warning" ? <TriangleAlert className="size-3" aria-hidden /> : <CircleAlert className="size-3" aria-hidden />}
          </span>
          <span className="min-w-0 break-words">
            <span className="font-medium">{item.label}</span>
            <span className="sr"> — {item.status}</span>
            {item.detail && <span className="text-muted-foreground"> · {item.detail}</span>}
          </span>
        </li>
      ))}
    </ul>
  );
}

export interface BlenderPickerProps {
  idPrefix: string;
  /** setup_core.blender_report; null while it loads. */
  report: Json | null;
  path: string;
  check: Json | null;
  checking: boolean;
  confirmRerender: boolean;
  /** What saving does, after a usable check that would write. */
  saveNote: string;
  onPath: (path: string) => void;
  onConfirm: (checked: boolean) => void;
  onCheck: () => void;
  onCancel: () => void;
  onChoose: () => void;
}

/** Choose and check a Blender executable (decision 0014); shared by the setup wizard and Settings → General. */
export function BlenderPicker({ idPrefix, report, path, check, checking, confirmRerender, saveNote, onPath, onConfirm, onCheck, onCancel, onChoose }: BlenderPickerProps) {
  if (!report) return <p className="flex items-center gap-2 text-[13px] text-muted-foreground" role="status"><Spinner />Looking for Blender (nothing is run yet)…</p>;
  const paths: string[] = report.candidates.map((c: Json) => c.path);
  const options = report.candidates.map((c: Json) => ({ value: c.path, title: c.path, detail: c.origin }));
  if (path && !paths.includes(path)) options.push({ value: path, title: path, detail: "chosen by you" });
  const current = check && check.path === path ? check : null;
  const usable = current && ["passed", "warning"].includes(current.status);
  return (
    <>
      {report.configured && !report.configured_exists && (
        <Banner tone="warning" role="status">The configured Blender ({report.configured}, in {report.config_file}) no longer exists. Choose one that does, then check it.</Banner>
      )}
      {options.length ? (
        <RadioCards id={`${idPrefix}-blender-choice`} label="Blender executable" value={path} onChange={onPath} options={options} />
      ) : (
        <Banner tone="info" role="status">
          No Blender was found. Install Blender {report.tested_version} from the address below, then choose its {navigator.platform.startsWith("Win") ? "blender.exe" : "blender"} here.
          <span className="mt-2 flex min-w-0 items-center gap-2 rounded-xl bg-surface-2 py-1.5 pr-1.5 pl-3">
            <code className="min-w-0 flex-1 break-all font-mono text-[11.5px] text-foreground select-text">{report.download_url}</code>
            <Button variant="quiet" className="h-8 shrink-0 px-3 text-[12px]" onClick={() => void copyText(report.download_url, "Address copied.")}><Copy className="size-3.5" aria-hidden />Copy</Button>
          </span>
        </Banner>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="secondary" id={`${idPrefix}-choose-blender`} disabled={checking} onClick={onChoose}><FolderOpen className="size-4" aria-hidden />Choose executable…</Button>
        {checking ? (
          <Button variant="secondary" id={`${idPrefix}-cancel-blender`} onClick={onCancel}>Cancel check</Button>
        ) : (
          <Button id={`${idPrefix}-check-blender`} disabled={!path} onClick={onCheck}>Check Blender</Button>
        )}
        <p role="status" aria-live="polite" className="flex items-center gap-2 text-[12.5px] text-muted-foreground">
          {checking ? <><Spinner />Checking… (up to about 2 minutes)</> : current ? CHECK_STATUS[current.status as string] : path ? "Not checked yet." : ""}
        </p>
      </div>
      {current && <BlenderChecks check={current} idPrefix={idPrefix} />}
      {usable && current.change === "unchanged" && <p className="text-[12.5px] text-muted-foreground">This is the Blender saved in the configuration; saving writes nothing.</p>}
      {usable && current.change === "write" && <p className="text-[12.5px] text-muted-foreground">{saveNote}</p>}
      {usable && current.change === "write" && current.rerender > 0 && (
        <Banner tone="warning" role="status" className="grid gap-3">
          <span>Changing Blender marks {plural(current.rerender, "finished 3D inspection", "finished 3D inspections")} as needing processing again (the Blender path is part of each result’s fingerprint). Current previews stay visible until Process assets renders them again.</span>
          <Checkbox id={`${idPrefix}-confirm-rerender`} label="I understand; render them again with this Blender" checked={confirmRerender} onCheckedChange={onConfirm} />
        </Banner>
      )}
    </>
  );
}
