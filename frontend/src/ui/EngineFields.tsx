import { useState } from "react";
import { cn } from "@/lib/utils";
import type { Json } from "../app/api";
import { ENGINE_NOTE, plural } from "../app/format";
import { checkServer } from "../app/store";
import { Badge, Button, RadioCards, TextField } from "./primitives";

/** How descriptions are generated: the engines setup_core lists, plus a local server's address and model (Settings and setup). */
export function EngineFields({ engine, onEngine, url, onUrl, model, onModel, disabled, engines, idPrefix }: {
  engine: string; onEngine: (value: string) => void; url: string; onUrl: (value: string) => void; model: string; onModel: (value: string) => void;
  disabled?: boolean; engines: Json[]; idPrefix: string;
}) {
  const [probe, setProbe] = useState<Json | null>(null);
  const [testing, setTesting] = useState(false);
  const test = async () => {
    setTesting(true);
    setProbe(await checkServer(url, model));
    setTesting(false);
  };
  const connected = probe?.status === "connected";
  return (
    <div className="grid gap-4">
      <RadioCards
        id={`${idPrefix}-engine`}
        label="How descriptions are generated"
        value={engine}
        onChange={onEngine}
        disabled={disabled}
        options={engines.map((item) => ({
          value: item.id,
          title: item.id === "builtin" ? `${item.label} — ${item.name}` : `${item.label} (experimental)`,
          detail: item.summary,
          badge: <Badge tone={item.status === "tested" ? "success" : "warning"}>{item.status === "tested" ? "Tested" : "Experimental"}</Badge>,
        }))}
      />
      {engine === "local-server" && (
        <div className="grid gap-3 rounded-2xl bg-surface-2 p-4">
          <div className="flex flex-wrap items-end gap-3">
            <TextField id={`${idPrefix}-server-url`} label="Server address" value={url} disabled={disabled} spellCheck={false} onChange={(e) => { onUrl(e.target.value); setProbe(null); }} className="min-w-[240px] flex-1" />
            <TextField id={`${idPrefix}-server-model`} label="Model name" value={model} disabled={disabled} spellCheck={false} onChange={(e) => { onModel(e.target.value); setProbe(null); }} className="min-w-[200px] flex-1" />
            <Button type="button" variant="secondary" id={`${idPrefix}-test-server`} disabled={disabled || testing || !url.trim()} onClick={() => void test()}>{testing ? "Testing…" : "Test connection"}</Button>
          </div>
          <p id={`${idPrefix}-server-result`} role="status" aria-live="polite" className={cn("text-[12.5px] leading-relaxed", probe && !connected ? "text-fault" : "text-muted-foreground")}>
            {!probe ? "Only addresses on this computer are accepted. Test connection only lists the server’s models; it never generates text."
              : connected ? `Connected · ${probe.models.length ? `${plural(probe.models.length, "model", "models")}: ${probe.models.join(", ")}` : "the server lists no models"}${probe.model_found === false ? `. “${model}” is not among them.` : ""}`
              : probe.reason}
          </p>
          {connected && probe.models.length > 0 && !probe.models.includes(model) && (
            <div className="flex flex-wrap gap-2">
              {probe.models.slice(0, 6).map((name: string) => (
                <Button key={name} type="button" variant="quiet" className="h-8 px-3 text-[12px]" onClick={() => onModel(name)}>Use “{name}”</Button>
              ))}
            </div>
          )}
        </div>
      )}
      <p className="hint text-[12px] leading-relaxed text-muted-foreground">{ENGINE_NOTE}</p>
    </div>
  );
}

/** Where search by description and by image runs (decision 0018): the devices setup_core lists. */
export function SearchDeviceField({ value, onChange, devices, disabled, idPrefix }: {
  value: string; onChange: (value: string) => void; devices: Json[]; disabled?: boolean; idPrefix: string;
}) {
  return (
    <RadioCards
      id={`${idPrefix}-search-device`}
      label="Where search runs"
      value={value}
      onChange={onChange}
      disabled={disabled}
      options={devices.map((item) => ({ value: item.id, title: item.label, detail: item.summary }))}
    />
  );
}
