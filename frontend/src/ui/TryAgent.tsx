import { Bot } from "lucide-react";
import { useEffect, useState } from "react";
import { getState, goToSetupStep, loadAgentActivity, openSetup, SETUP_STEPS, startAgentPractice, useApp } from "../app/store";
import { Banner, Button, Card } from "./primitives";

export const TRY_AGENT_HELP = "Try your connected agent on a few generated practice packs using the Library import and review flow. Practice files and test data are removed when you finish or cancel.";

export function TryAgent({ id = "try-agent" }: { id?: string }) {
  const connected = useApp((s) => s.agent.connected);
  const open = useApp((s) => s.addFolder.open);
  const [starting, setStarting] = useState(false);
  const [reason, setReason] = useState<string | null>(null);
  useEffect(() => {
    void loadAgentActivity();
    void getState().api?.practice_action("available").then((r) => setReason(r.reason || null));
    const timer = setInterval(() => void loadAgentActivity(), 3000);
    return () => clearInterval(timer);
  }, []);
  return <div id={id} className="grid gap-3">
    {reason && <Banner tone="warning"><span>{reason} Starting again will attempt abandoned-session cleanup.</span></Banner>}
    <p className="text-[13px] text-muted-foreground">{connected.length
      ? `${connected.map((c: { name?: string }) => c.name).filter(Boolean).join(", ") || "Your agent"} is connected. You’ll paste a prompt into it and review its proposals here.`
      : "Connect your agent, then return here to try a practice import."}</p>
    <div className="flex flex-wrap gap-2"><Button id={id + "-start"} disabled={!connected.length || open || starting} tooltip="Adds small practice packs to a temporary library for your agent to organize; everything is removed when you finish" onClick={async () => {
      setStarting(true);
      try { await startAgentPractice(); } finally { setStarting(false); }
    }}><Bot className="size-4" aria-hidden />{starting ? "Preparing practice packs…" : "Try your agent"}</Button>
      {!connected.length && <Button variant="secondary" tooltip="Opens setup at the step that connects your AI agent" onClick={async () => {
        if (!getState().setup.open) await openSetup();
        goToSetupStep(SETUP_STEPS.indexOf("agent"));
      }}>Connect your agent</Button>}</div>
    <p className="text-[12px] text-muted-foreground">Checks pack organization and import review. No rendering, descriptions or model-server setup.</p>
  </div>;
}

export function TryAgentCard() {
  return <Card id="try-agent-card" title="Try your agent" help={TRY_AGENT_HELP}><TryAgent /></Card>;
}
