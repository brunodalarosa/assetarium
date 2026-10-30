import { Bot, Check, CircleAlert, Copy, PlugZap, Wrench } from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";
import { Checkbox } from "@/components/beui/checkbox";
import { cn } from "@/lib/utils";
import type { Json } from "../app/api";
import { formatLabel, plural } from "../app/format";
import { copyText, decideProposal, endAgentSetup, leaveAgentSetup, reviewAgentSetup, startAgentSetup, useApp } from "../app/store";
import { Badge, Banner, Button, Card, Spinner } from "./primitives";

/** Re-renders on an interval so the session countdown stays current without polling the backend. */
function useNow(ms: number) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), ms);
    return () => clearInterval(timer);
  }, [ms]);
  return now;
}

export function SetByBadge({ entry }: { entry: Json | undefined }) {
  if (!entry) return null;
  const agent = entry.set_by === "agent";
  return (
    <span className="set-by" data-set-by={agent ? "agent" : "user"}>
      <Badge tone={agent ? "info" : "neutral"}>{agent ? (entry.approved_by === "user" ? "Proposed by agent · approved by you" : "Set by agent") : "Set by you"}</Badge>
    </span>
  );
}

function PathCard({ icon, title, body, action }: { icon: ReactNode; title: string; body: string; action: ReactNode }) {
  return (
    <section className="grid content-start gap-3 rounded-2xl border border-border bg-surface p-5">
      <span className="grid size-9 place-items-center rounded-xl bg-accent-soft text-accent-soft-foreground" aria-hidden>{icon}</span>
      <h2 className="text-[15px] font-semibold">{title}</h2>
      <p className="text-[13px] leading-relaxed text-muted-foreground">{body}</p>
      <div className="mt-1">{action}</div>
    </section>
  );
}

/** Two equal ways to set up; choosing the agent opens the session (the user gesture the backend requires). */
export function SetupPaths() {
  const busy = useApp((s) => s.setup.agentBusy);
  return (
    <div id="setup-paths" className="grid gap-4 sm:grid-cols-2">
      <PathCard icon={<Bot className="size-4.5" />} title="Set up with your AI agent"
        body="Your agent checks this computer and chooses settings for you. You approve the risky parts, like which Blender to run, here."
        action={<Button id="setup-agent-start" disabled={busy === "open"} onClick={() => void startAgentSetup()}>{busy === "open" ? "Opening…" : "Set up with my agent"}</Button>} />
      <PathCard icon={<Wrench className="size-4.5" />} title="Set it up yourself"
        body="Answer a few questions about Blender, formats, storage and descriptions. It takes about two minutes."
        action={<Button variant="secondary" id="setup-manual" onClick={() => leaveAgentSetup()}>Start setup</Button>} />
    </div>
  );
}

function Snippets({ snippets }: { snippets: Json[] }) {
  const [client, setClient] = useState(snippets[0]?.id);
  const current = snippets.find((item) => item.id === client) || snippets[0];
  return (
    <div className="grid gap-3">
      <div role="tablist" aria-label="Agent" id="agent-snippet-tabs" className="flex flex-wrap gap-2">
        {snippets.map((item) => (
          <button key={item.id} type="button" role="tab" aria-selected={item.id === current.id} data-client={item.id} onClick={() => setClient(item.id)}
            className={cn("h-9 rounded-full border px-4 text-[12.5px] font-medium transition-colors", item.id === current.id ? "border-primary bg-accent-soft text-accent-soft-foreground" : "border-border bg-surface text-foreground hover:bg-surface-2")}>
            {item.label}
          </button>
        ))}
      </div>
      <p className="text-[12.5px] text-muted-foreground">{current.where}</p>
      <div className="grid gap-2 rounded-xl bg-surface-2 p-3">
        <pre id="agent-snippet" data-client={current.id} className="max-h-56 overflow-auto font-mono text-[11.5px] leading-relaxed whitespace-pre-wrap break-all text-foreground select-text scroll-thin">{current.text}</pre>
        <div><Button variant="quiet" id="agent-copy-snippet" className="h-8 px-3 text-[12px]" onClick={() => void copyText(current.text, `${current.label} configuration copied. Restart your agent after adding it.`)}><Copy className="size-3.5" aria-hidden />Copy</Button></div>
      </div>
    </div>
  );
}

function ConnectionLine({ connections }: { connections: Json[] }) {
  const live = connections.filter((item) => item.mode === "normal");
  const degraded = connections.some((item) => item.mode === "setup_only");
  const name = live.map((item) => item.client?.name).find(Boolean);
  if (live.length)
    return (
      <p id="agent-connection" data-state="connected" role="status" aria-live="polite" className="flex items-center gap-2 text-[13px] text-success">
        <PlugZap className="size-4" aria-hidden />{name ? `${name} is connected.` : "An agent is connected."} Ask it to set up Assetarium for this computer.
      </p>
    );
  return (
    <p id="agent-connection" data-state={degraded ? "setup_only" : "waiting"} role="status" aria-live="polite" className="flex items-center gap-2 text-[13px] text-muted-foreground">
      <Spinner />{degraded ? "An agent is connected, but Assetarium’s configuration does not load; it can read the fault and the fix." : "Waiting for an agent to connect… Agents start Assetarium’s server themselves when they connect, so restart your agent after adding the configuration."}
    </p>
  );
}

function ProposalCard({ proposal }: { proposal: Json }) {
  const busy = useApp((s) => s.setup.agentBusy);
  const [confirmed, setConfirmed] = useState(false);
  const deciding = busy?.startsWith(proposal.id + ":");
  return (
    <div className="agent-proposal grid gap-3 rounded-2xl border border-primary/40 bg-accent-soft/40 p-4" data-proposal={proposal.id} role="group" aria-label="Agent proposal">
      <p className="text-[13px] leading-relaxed">
        <span className="font-medium">Your agent proposes: Blender → </span>
        <span className="break-all font-mono text-[12px]">{proposal.path}</span>
        <span className="text-muted-foreground">, checked as Blender {proposal.version}{proposal.check === "warning" ? " (works; not the tested version)" : ""} with glTF · FBX · OBJ importers.</span>
      </p>
      <p className="text-[12.5px] text-muted-foreground">Apply checks it again on this computer, then saves it to config.local.toml. Make previews uses it from its next run.</p>
      {proposal.rerender > 0 && (
        <Banner tone="warning" role="status" className="grid gap-3">
          <span>Changing Blender marks {plural(proposal.rerender, "finished 3D inspection", "finished 3D inspections")} as needing processing again (the Blender path is part of each result’s fingerprint). Current previews stay visible until Make previews renders them again.</span>
          <Checkbox id={"agent-confirm-" + proposal.id} label="I understand; render them again with this Blender" checked={confirmed} onCheckedChange={setConfirmed} />
        </Banner>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <Button className="agent-apply" disabled={Boolean(busy) || (proposal.rerender > 0 && !confirmed)} onClick={() => void decideProposal(proposal, "apply", confirmed)}>
          {busy === proposal.id + ":apply" ? "Checking again…" : "Apply"}
        </Button>
        <Button variant="secondary" className="agent-reject" disabled={Boolean(busy)} onClick={() => void decideProposal(proposal, "reject")}>Reject</Button>
        {deciding && <span role="status" className="flex items-center gap-2 text-[12.5px] text-muted-foreground"><Spinner />Up to about 2 minutes</span>}
      </div>
    </div>
  );
}

function valueText(key: string, settings: Json, blender: Json) {
  switch (key) {
    case "storage_budget_gib": return `${Number(settings.storage_budget_gib).toLocaleString()} GiB`;
    case "processing_formats": return settings.processing_formats.length ? settings.processing_formats.map(formatLabel).join(", ") : "None (processing paused)";
    case "caption_batch_size": return String(settings.caption_batch_size);
    case "descriptions_enabled": return settings.descriptions_enabled ? "On" : "Off (existing descriptions are kept)";
    case "description_engine": return settings.description_engine === "local-server" ? "Local model server" : "Built in";
    case "description_server": return `${settings.description_server.url}${settings.description_server.model ? " · " + settings.description_server.model : ""}`;
    case "search_device": return settings.search_device === "cpu" ? "CPU" : "NVIDIA GPU";
    case "blender": return blender.configured || "Found automatically";
    default: return "";
  }
}
const VALUE_LABELS: [string, string][] = [
  ["blender", "Blender"], ["processing_formats", "Formats"], ["storage_budget_gib", "Storage budget"], ["descriptions_enabled", "Descriptions"],
  ["description_engine", "Description engine"], ["description_server", "Model server"], ["caption_batch_size", "Batch size"],
  ["search_device", "Search runs on"],
];

function Values({ agent }: { agent: Json }) {
  const setBy = agent.set_by || {};
  const settings = agent.settings;
  if (!settings) return null;
  const shown = VALUE_LABELS.filter(([key]) => setBy[key] && !(key === "description_server" && settings.description_engine !== "local-server"));
  return (
    <dl id="agent-values" className="grid gap-2.5" aria-live="polite">
      {!shown.length && <p className="text-[12.5px] text-muted-foreground">Nothing set yet. Values appear here as your agent sets them.</p>}
      {shown.map(([key, label]) => (
        <div key={key} data-key={key} className="grid grid-cols-[minmax(0,140px)_minmax(0,1fr)_auto] items-center gap-3 border-b border-border pb-2.5 last:border-0 last:pb-0">
          <dt className="text-[12.5px] text-muted-foreground">{label}</dt>
          <dd className="break-words text-[13px]">{valueText(key, settings, agent.blender)}</dd>
          <SetByBadge entry={setBy[key]} />
        </div>
      ))}
    </dl>
  );
}

export function AgentPanel() {
  const agent = useApp((s) => s.setup.agent);
  const busy = useApp((s) => s.setup.agentBusy);
  const now = useNow(15000);
  if (!agent) return <p className="flex items-center gap-2 text-[13px] text-muted-foreground" role="status"><Spinner />Opening agent setup…</p>;
  const expires = agent.session.expires_utc ? Date.parse(agent.session.expires_utc) : 0;
  const open = agent.session.open && expires > now;
  const minutes = Math.max(0, Math.floor((expires - now) / 60000));
  const pending = (agent.proposals || []).filter((item: Json) => item.state === "pending");
  const finished = agent.record?.state === "completed" && agent.record?.by === "agent";
  const anySet = Object.values(agent.set_by || {}).some((entry: Json) => entry.set_by === "agent");
  return (
    <div id="agent-panel" className="grid gap-5" data-session={open ? "open" : "closed"}>
      <h2 id="agent-setup-title" tabIndex={-1} className="sr">Set up with your AI agent</h2>
      <div id="agent-session" role="status" className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-surface-2 px-4 py-2.5 text-[12.5px]">
        {open ? <span><span className="font-medium">Agent setup access is open</span> · {minutes < 1 ? "less than a minute" : plural(minutes, "minute", "minutes")} left</span>
          : <span><span className="font-medium">Agent setup access has ended.</span> Your agent can still read the setup status but can’t change anything.</span>}
        {open ? <Button variant="quiet" id="agent-end" className="h-8 px-3 text-[12px]" disabled={busy === "end"} onClick={() => void endAgentSetup()}>End access</Button>
          : <Button variant="secondary" id="agent-reopen" className="h-8 px-3 text-[12px]" disabled={busy === "open"} onClick={() => void startAgentSetup()}>Open for 60 minutes</Button>}
      </div>
      {pending.map((proposal: Json) => <ProposalCard key={proposal.id} proposal={proposal} />)}
      {finished && (
        <Banner tone="info" role="status" className="flex flex-wrap items-center justify-between gap-3">
          <span className="flex items-center gap-2"><Check className="size-4 text-success" aria-hidden />Your agent finished setup. Review the choices; you can change any of them.</span>
          <Button id="agent-review" onClick={() => void reviewAgentSetup()}>Review choices</Button>
        </Banner>
      )}
      <Card title="1 · Add Assetarium to your agent" help="Generated for this computer’s folders. Assetarium’s server runs only while your agent is connected.">
        <Snippets snippets={agent.snippets} />
      </Card>
      <Card title="2 · Ask it to set up Assetarium">
        <p id="agent-prompt" className="rounded-xl bg-surface-2 p-3 text-[12.5px] leading-relaxed select-text">{agent.prompt}</p>
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="secondary" id="agent-copy-prompt" onClick={() => void copyText(agent.prompt, "Setup prompt copied. Paste it into your agent.")}><Copy className="size-3.5" aria-hidden />Copy setup prompt</Button>
        </div>
        <ConnectionLine connections={agent.connections || []} />
        <p id="agent-privacy" className="flex items-start gap-2 text-[12px] leading-relaxed text-muted-foreground">
          <CircleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden />Your agent’s model receives this computer’s OS, GPU, free space and Blender paths. If that model runs in the cloud, they leave this computer. Your agent runs install commands only with your permission.
        </p>
      </Card>
      <Card title="What your agent has set" help="Every change also raises a notice. You can change anything in the review.">
        <Values agent={agent} />
        {anySet && !finished && <div><Button variant="secondary" id="agent-review-early" onClick={() => void reviewAgentSetup()}>Review choices</Button></div>}
      </Card>
      <p className="text-[12.5px] text-muted-foreground">
        Prefer to answer the questions yourself? <button type="button" id="agent-leave" className="font-medium text-foreground underline underline-offset-2" onClick={() => leaveAgentSetup()}>Set it up yourself</button>
      </p>
    </div>
  );
}
