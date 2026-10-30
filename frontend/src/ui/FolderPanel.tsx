import { Boxes, Copy, Folder, FolderSearch, HardDrive, Package, RefreshCw, Trash2 } from "lucide-react";
import { useState } from "react";
import { Checkbox } from "@/components/beui/checkbox";
import { Switch } from "@/components/beui/switch";
import type { Json } from "../app/api";
import { nearMissText, operationActive, plural } from "../app/format";
import { confirmRemoveSource, folderAction, pathAction, sourceAction, sourceFolders, useApp } from "../app/store";
import { Badge, Banner, Button, RadioCards, TextField } from "./primitives";

const where = (anchor: string) => (anchor ? `In ${anchor}` : "At the top of this library folder");

/** Models that could not find their textures: choose a folder by exact file name (decision 0021). */
function TextureChoice({ source, busy }: { source: Json; busy: boolean }) {
  const found: Json | null = source.texture_suggestion || null;
  const chosen: Json | null = source.texture_folder || null;
  const options: Json[] = found?.folders || [];
  const [folder, setFolder] = useState<string>("");
  const [single, setSingle] = useState(true);
  const [working, setWorking] = useState(false);
  const selected = folder || options[0]?.folder || "";
  const disabled = busy || working;
  const run = async (undo: boolean) => {
    setWorking(true);
    await sourceFolders(undo ? "textures-undo" : "textures", source.key, undo ? null : selected || null, single ? "single" : "");
    setWorking(false);
  };
  if (!found && !chosen) return null;
  const option = options.find((o) => o.folder === selected);
  const fixes = option ? (single ? option.fixes : option.fixes_without_single_copies) : single ? found?.single_copies_only.fixes : 0;
  const left = (found?.assets || 0) - (fixes || 0);
  return (
    <div className="texture-choice grid gap-3 rounded-2xl bg-surface-2 p-4">
      {chosen && (
        <p className="texture-chosen flex flex-wrap items-center gap-2 text-[12.5px] text-muted-foreground">
          <span>Textures from {chosen.folder || "no folder"}{chosen.single_copies ? " and single copies" : ""}. Repaired models wait for Process assets; originals are not changed.</span>
          <button type="button" className="font-medium text-primary hover:underline disabled:opacity-50" disabled={disabled} data-action="textures-undo" onClick={() => void run(true)}>Undo</button>
        </p>
      )}
      {found && (
        <>
          <p className="text-[13px] font-medium">Textures not found</p>
          <p className="text-[12.5px] leading-relaxed text-muted-foreground">
            {found.assets.toLocaleString()} {found.assets === 1 ? "model can’t" : "models can’t"} find {found.assets === 1 ? "its" : "their"} textures (for example {found.examples.slice(0, 3).join(", ")}).
            {options.length ? " Some textures exist in several folders, one per render pipeline. Choose which to use; matches are by exact file name." : ""}
          </p>
          {options.length > 0 && (
            <RadioCards id={`textures-${source.id}`} label="Use textures from" value={selected} onChange={setFolder} disabled={disabled}
              options={options.map((o) => ({ value: o.folder, title: o.folder, detail: `Fixes ${(single ? o.fixes : o.fixes_without_single_copies).toLocaleString()} of ${found.assets.toLocaleString()}` }))} />
          )}
          <Checkbox label="Also use textures that have only one version in this source" checked={single} disabled={disabled} onCheckedChange={setSingle}
            description="A file with that exact name exists once (or as identical copies), so there is no choice to make." />
          <p className="texture-total text-[12.5px] text-foreground">
            {(fixes || 0).toLocaleString()} fixed{left > 0 ? ` · ${left.toLocaleString()} ${left === 1 ? "stays" : "stay"} failed with ${left === 1 ? "its" : "their"} recorded ${left === 1 ? "reason" : "reasons"}` : " · none left unresolved"}
          </p>
          <div className="flex flex-wrap gap-2">
            <Button className="h-9 px-4" disabled={disabled || !fixes} data-action="textures-apply" onClick={() => void run(false)}>Apply</Button>
          </div>
          <p className="hint text-[11.5px] leading-relaxed text-subtle">Applying records your choice with each repaired model and scans again. Nothing is rendered until you click Process assets, and original files are never changed. Undo removes the choice.</p>
        </>
      )}
    </div>
  );
}

/** ", including N names that would not be grouped" when excluding a near-miss folder drops models of its own. */
function excludedOnly(s: Json) {
  if (!s.near) return "";
  const extra = s.folders.filter((f: string) => f !== s.reference && !s.grouped_folders.includes(f));
  const own = extra.reduce((total: number, f: string) => total + (s.near.only[f] || 0) + (s.near.repeated[f] || 0), 0);
  return own ? `, including ${own} ${own === 1 ? "name" : "names"} that would not be grouped` : "";
}

/** Duplicate export folder suggestions, saved answers and excluded folders for one source (decision 0019). */
export function SourceFolders({ source, busy }: { source: Json; busy: boolean }) {
  const [pattern, setPattern] = useState("");
  const [working, setWorking] = useState(false);
  const exclusions: string[] = source.exclusions || [];
  const excluded: Json[] = source.excluded_folders || [];
  const suggestions: Json[] = source.export_suggestions || [];
  const answers: Json[] = source.export_decisions || [];
  const disabled = busy || working;
  const run = async (change: "exclusions" | "export" | "undo", value: string[] | string, decision = "") => {
    setWorking(true);
    const result = await sourceFolders(change, source.key, value, decision);
    if (change === "exclusions" && result.status !== "faulty") setPattern("");
    setWorking(false);
  };
  const files = excluded.reduce((total, item) => total + (item.files || 0), 0);
  return (
    <div className="source-folders mt-2 grid gap-3">
      <TextureChoice source={source} busy={busy} />
      {suggestions.map((s) => (
        <div key={s.id} className="export-suggestion grid gap-2 rounded-2xl bg-surface-2 p-4" data-suggestion={s.id}>
          <p className="text-[13px] font-medium">Possible duplicate exports</p>
          <p className="text-[12.5px] leading-relaxed text-muted-foreground">
            {where(s.anchor)}, {s.folders.join(", ")} {s.near ? "share" : "have the same"} {s.names.toLocaleString()} model names (for example {s.sample_names.slice(0, 3).join(", ")}).
            {nearMissText(s.near)}
            {s.grouped_folders.length > 1 ? ` ${s.grouped_folders.join(" and ")} are already grouped.` : ""}
          </p>
          <p className="hint text-[11.5px] leading-relaxed text-subtle">
            Grouping makes one asset per model with every folder’s file attached; only the preferred file is rendered. Previews and descriptions are kept and search data is rebuilt. Excluding stops scanning the extra folders ({s.folders.filter((f: string) => f !== s.reference && !s.grouped_folders.includes(f)).join(", ")}){excludedOnly(s)}. Nothing on disk changes either way.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button className="h-9 px-4" disabled={disabled} data-action="group" onClick={() => void run("export", s.id, "group")}>Group as alternate files</Button>
            <Button variant="secondary" className="h-9 px-4" disabled={disabled} data-action="exclude" onClick={() => void run("export", s.id, "exclude")}>Exclude extra folders</Button>
            <Button variant="quiet" className="h-9 px-4" disabled={disabled} data-action="separate" onClick={() => void run("export", s.id, "separate")}>Keep separate</Button>
          </div>
        </div>
      ))}
      {answers.length > 0 && (
        <ul className="export-answers grid gap-1 text-[12px] text-muted-foreground" aria-label="Saved answers about duplicate exports">
          {answers.map((d) => (
            <li key={d.id} className="flex flex-wrap items-center gap-2">
              <span>{d.decision === "group" ? "Grouped" : "Kept separate"}: {d.anchor ? d.anchor + " / " : ""}{d.folders.join(", ")}</span>
              <button type="button" className="font-medium text-primary hover:underline disabled:opacity-50" disabled={disabled} data-action="undo" onClick={() => void run("undo", d.id)}>Undo</button>
            </li>
          ))}
        </ul>
      )}
      <div className="grid gap-2">
        <p className="text-[13px] font-medium">Excluded folders</p>
        {exclusions.length > 0 && (
          <ul className="flex flex-wrap gap-2" aria-label="Excluded folder patterns">
            {exclusions.map((item) => (
              <li key={item} className="flex items-center gap-1.5 rounded-full bg-surface-2 py-1 pl-3 pr-1.5 text-[12px]">
                <span className="font-mono">{item}</span>
                <button type="button" aria-label={"Stop excluding " + item} disabled={disabled} className="grid size-5 place-items-center rounded-full text-muted-foreground hover:bg-surface hover:text-foreground disabled:opacity-50"
                  onClick={() => void run("exclusions", exclusions.filter((p) => p !== item))}>×</button>
              </li>
            ))}
          </ul>
        )}
        <form className="flex flex-wrap items-end gap-2" onSubmit={(event) => { event.preventDefault(); if (pattern.trim()) void run("exclusions", [...exclusions, pattern.trim()]); }}>
          <TextField id={`exclude-${source.id}`} label="Folder name or path" value={pattern} disabled={disabled} spellCheck={false} placeholder="Unity*  or  Models/Unity FBX" onChange={(e) => setPattern(e.target.value)} className="min-w-[220px] flex-1" />
          <Button type="submit" variant="secondary" className="h-10 px-4" disabled={disabled || !pattern.trim()}>Exclude</Button>
        </form>
        <p className="hint text-[11.5px] leading-relaxed text-subtle">
          {exclusions.length ? `${files.toLocaleString()} files in ${excluded.length} excluded ${excluded.length === 1 ? "folder" : "folders"} are not scanned. ` : ""}
          A name matches any folder with that name (* is a wildcard); a path with / matches one folder inside the source. Files in excluded folders can’t be used as textures either. Changing this scans the source again; nothing on disk is deleted.
        </p>
      </div>
    </div>
  );
}


const KIND_LABEL: Record<string, string> = { library: "Library folder", bundle: "Bundle", pack: "Pack", folder: "Folder" };
const KIND_ICON = { library: HardDrive, bundle: Boxes, pack: Package, folder: Folder } as const;

function PackName({ folderKey, path, name }: { folderKey: string; path: string; name: string }) {
  const [draft, setDraft] = useState<string | null>(null);
  if (draft === null)
    return <button type="button" className="w-fit text-[12px] font-medium text-primary hover:underline" data-action="rename-pack" onClick={() => setDraft(name)}>Rename</button>;
  return (
    <form className="flex items-end gap-2" onSubmit={(event) => { event.preventDefault(); void folderAction("rename_pack", folderKey, path, draft).then(() => setDraft(null)); }}>
      <TextField id="pack-name" label="Pack name" value={draft} maxLength={120} onChange={(e) => setDraft(e.target.value)} className="min-w-0 flex-1" />
      <Button type="submit" variant="secondary" className="h-10 px-4">Save</Button>
      <Button type="button" variant="quiet" className="h-10 px-3" onClick={() => setDraft(null)}>Cancel</Button>
    </form>
  );
}

/** Inspection for a library folder, bundle, pack or folder: what it is, its answers and its actions. */
export function FolderPanel() {
  const view = useApp((s) => s.sourcesView);
  const sources = useApp((s) => s.sources);
  const folder = (view.tree?.folders || []).find((f: Json) => f.key === view.key);
  if (!folder) return <p className="p-6 text-[13px] text-muted-foreground">Choose a folder or pack.</p>;
  const node = (folder.nodes || []).find((n: Json) => n.path === view.path) || { path: "", kind: "library", assets: 0 };
  const kind: string = view.path === "" ? "library" : node.kind;
  const Icon = KIND_ICON[kind as keyof typeof KIND_ICON] || Folder;
  const source = sources.find((s: Json) => s.key === folder.key) || folder;
  const busy = operationActive(source.operation);
  const name = view.path === "" ? folder.name : node.name;
  const license = (node.pack?.markers || []).find((m: Json) => m.kind === "license");
  const full = folder.path + (view.path ? "\\" + view.path.replaceAll("/", "\\") : "");
  return (
    <div id="folder-panel" className="grid gap-5 p-6">
      <header className="grid gap-1.5">
        <p className="flex items-center gap-1.5 text-[12px] text-muted-foreground"><Icon className="size-3.5" aria-hidden />{KIND_LABEL[kind] || "Folder"}</p>
        <h2 id="folder-panel-title" tabIndex={-1} className="text-[20px] font-semibold break-words outline-none">{name}</h2>
        <p className="truncate text-[12px] text-muted-foreground" title={full}>{full}</p>
        {kind === "pack" && <PackName folderKey={folder.key} path={view.path} name={name} />}
      </header>
      {folder.offline && <Banner tone="warning"><span>Offline: this folder can’t be reached (a removed drive?). Its results and collection entries are kept.</span></Banner>}
      <dl className="grid grid-cols-2 gap-3 text-[12.5px]">
        <div><dt className="text-muted-foreground">Assets</dt><dd className="font-medium tabular-nums">{(node.assets || 0).toLocaleString()}</dd></div>
        <div><dt className="text-muted-foreground">With previews</dt><dd className="font-medium tabular-nums">{node.assets ? Math.round((node.coverage || 0) * 100) + "%" : "—"}</dd></div>
        {node.blocked > 0 && <div><dt className="text-muted-foreground">Blocked</dt><dd className="font-medium tabular-nums">{node.blocked.toLocaleString()}</dd></div>}
        {node.failed > 0 && <div><dt className="text-muted-foreground">Recorded failures</dt><dd className="font-medium tabular-nums">{node.failed.toLocaleString()}</dd></div>}
        {kind === "library" && folder.missing > 0 && <div><dt className="text-muted-foreground">Missing</dt><dd className="font-medium tabular-nums">{folder.missing.toLocaleString()}</dd></div>}
      </dl>
      {kind === "pack" && (
        <section className="grid gap-1.5">
          <h3 className="text-[13px] font-medium">License</h3>
          <p className="text-[12.5px] leading-relaxed text-muted-foreground">
            {license ? `Found ${license.evidence} in this pack. ` : "No license file found in this pack. "}
            {node.pack?.basis === "owner" ? "You made this folder a pack." : node.pack?.basis === "markers" ? "Detected from " + (node.pack.markers || []).map((m: Json) => m.evidence).slice(0, 3).join(", ") + "." : "The first folder with assets."}
          </p>
          {license && <Badge tone="neutral" className="w-fit">License file</Badge>}
        </section>
      )}
      <section className="grid gap-2">
        <h3 className="text-[13px] font-medium">Organize</h3>
        <div className="flex flex-wrap gap-2">
          {kind !== "pack" && kind !== "library" && <Button variant="secondary" className="h-9 px-3" data-action="make-pack" disabled={busy} onClick={() => void folderAction("make_pack", folder.key, view.path)}>Make this a pack</Button>}
          {kind === "pack" && view.path !== "" && <Button variant="secondary" className="h-9 px-3" data-action="merge-pack" disabled={busy} onClick={() => void folderAction("merge", folder.key, view.path)}>Merge into parent pack</Button>}
          {node.pack?.basis === "owner" && <Button variant="quiet" className="h-9 px-3" disabled={busy} onClick={() => void folderAction("clear_pack", folder.key, view.path)}>Undo pack choice</Button>}
          <Button variant="secondary" className="h-9 px-3" data-action="images-textures" disabled={busy} onClick={() => void folderAction("image_kind", folder.key, view.path, "texture")}>Treat images here as textures</Button>
          <Button variant="secondary" className="h-9 px-3" data-action="images-2d" disabled={busy} onClick={() => void folderAction("image_kind", folder.key, view.path, "image")}>Treat images here as 2D assets</Button>
          {view.path !== "" && <Button variant="quiet" className="h-9 px-3" data-action="exclude-folder" disabled={busy} onClick={() => void folderAction("exclude", folder.key, view.path)}>Exclude folder</Button>}
        </div>
        <p className="hint text-[11.5px] leading-relaxed text-subtle">Each answer is saved with this folder and the library folder is scanned again. Nothing on disk changes, and nothing is processed until you ask.</p>
      </section>
      <section className="flex flex-wrap gap-2">
        <Button variant="secondary" className="h-9 px-3" onClick={() => void pathAction("reveal", folder.key, view.path)}><FolderSearch className="size-4" aria-hidden />Show in Explorer</Button>
        <Button variant="quiet" className="h-9 px-3" onClick={() => void pathAction("copy", folder.key, view.path)}><Copy className="size-4" aria-hidden />Copy path</Button>
      </section>
      {kind === "library" && (
        <>
          <section className="flex flex-wrap items-center gap-3">
            <Switch checked={source.enabled} onCheckedChange={(checked) => void sourceAction("enabled", folder.key, null, checked)} label="Included in search" ariaLabel={"Include " + folder.name + " in search"} />
            <Button variant="secondary" className="h-9 px-3" data-action="rescan" disabled={busy || folder.offline} onClick={() => void sourceAction("scan", folder.key)}><RefreshCw className="size-4" aria-hidden />Rescan</Button>
            {folder.missing > 0 && <Button variant="secondary" className="h-9 px-3" data-action="forget-missing" onClick={() => void folderAction("forget_missing", folder.key, "")}>Forget {plural(folder.missing, "missing asset", "missing assets")}</Button>}
            <Button variant="danger" className="h-9 px-3" data-action="remove" disabled={busy} onClick={() => confirmRemoveSource(source)}><Trash2 className="size-4" aria-hidden />Remove…</Button>
          </section>
          <SourceFolders source={source} busy={busy} />
        </>
      )}
    </div>
  );
}
