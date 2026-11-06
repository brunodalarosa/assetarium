import { Bot, CircleSlash, Clock, Eye, MessageSquare, PencilLine, X } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, useRef } from "react";
import { SPRING_LAYOUT, SPRING_PANEL } from "@/lib/ease";
import { cn } from "@/lib/utils";
import type { Json } from "../app/api";
import { plural } from "../app/format";
import { decideAgentProposal, setAgentOpen, useApp } from "../app/store";
import { IconButton } from "./primitives";
import { ProposalReview } from "./ProposalReview";

const KIND = {
  read: { icon: Eye, tone: "text-muted-foreground" }, change: { icon: PencilLine, tone: "text-primary" },
  waiting: { icon: Clock, tone: "text-warning" }, say: { icon: MessageSquare, tone: "text-foreground" }, refused: { icon: CircleSlash, tone: "text-fault" },
} as const;

const time = (utc: string) => new Date(utc).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
const who = (connected: Json[]) => connected.map((c) => c.name).filter(Boolean).join(", ") || "an agent";

/** The top bar's agent button: a breathing dot while an agent works, a count of proposals waiting for you. */
export function AgentButton() {
  const agent = useApp((s) => s.agent);
  const waiting = agent.proposals.length;
  const last = agent.entries[agent.entries.length - 1];
  const label = `Agent activity${agent.working ? ", an agent is working" : ""}${waiting ? `, ${plural(waiting, "proposal", "proposals")} waiting` : ""}`;
  return (
    <button id="open-agent-activity" type="button" aria-label={label} aria-haspopup="dialog" aria-expanded={agent.open} aria-controls="agent-activity-panel"
      data-agent-anchor="" data-working={agent.working ? "true" : "false"} onClick={() => setAgentOpen(!agent.open)}
      className={cn("relative flex h-10 max-w-[280px] items-center gap-2 rounded-full border px-3 text-[12.5px] transition-colors",
        agent.open ? "border-primary bg-accent-soft text-accent-soft-foreground" : "border-border bg-surface text-muted-foreground hover:text-foreground")}>
      <span className="relative grid place-items-center">
        <Bot className="size-4.5" strokeWidth={1.75} aria-hidden />
        {agent.working && <span aria-hidden className="agent-pulse absolute -top-0.5 -right-0.5 size-2 rounded-full bg-primary" />}
      </span>
      {agent.working && last ? <span className="hidden truncate md:inline">{last.text}</span> : <span className="hidden md:inline">Agent</span>}
      {waiting > 0 && <span id="agent-waiting-count" className="grid h-5 min-w-5 place-items-center rounded-full bg-primary px-1.5 text-[11px] font-semibold text-primary-foreground">{waiting}</span>}
    </button>
  );
}

/** App-wide Agent activity (decision 0024): who is connected, proposals waiting for you and everything agents did. */
export function AgentActivityPanel() {
  const agent = useApp((s) => s.agent);
  const panelRef = useRef<HTMLElement>(null);
  const listRef = useRef<HTMLOListElement>(null);
  const reduce = useReducedMotion();
  useEffect(() => {
    if (!agent.open) return;
    document.getElementById("agent-activity-title")?.focus();
    const onPointer = (event: PointerEvent) => {
      const target = event.target as Element;
      if (!panelRef.current?.contains(target) && !target.closest("[data-agent-anchor]") && !target.closest("#toasts")) setAgentOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      event.stopImmediatePropagation();
      setAgentOpen(false);
      document.getElementById("open-agent-activity")?.focus();
    };
    window.addEventListener("pointerdown", onPointer);
    window.addEventListener("keydown", onKey, true);
    return () => {
      window.removeEventListener("pointerdown", onPointer);
      window.removeEventListener("keydown", onKey, true);
    };
  }, [agent.open]);
  useEffect(() => {
    listRef.current?.lastElementChild?.scrollIntoView({ block: "nearest", behavior: reduce ? "auto" : "smooth" });
  }, [agent.entries.length, agent.open, reduce]);
  const entries = agent.entries.slice(-80);
  return (
    <AnimatePresence>
      {agent.open && (
        <motion.section ref={panelRef} id="agent-activity-panel" role="dialog" aria-labelledby="agent-activity-title"
          initial={reduce ? { opacity: 0 } : { opacity: 0, y: -10, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={reduce ? { opacity: 0 } : { opacity: 0, y: -8, scale: 0.97, transition: { duration: 0.14 } }} transition={SPRING_PANEL}
          style={{ transformOrigin: "top right" }}
          className="fixed top-[72px] right-[110px] z-40 flex max-h-[min(80vh,780px)] w-[min(460px,calc(100vw-32px))] flex-col overflow-hidden rounded-[24px] border border-border bg-surface shadow-panel">
          <div className="flex items-center justify-between px-6 pt-5 pb-2">
            <h2 id="agent-activity-title" tabIndex={-1} className="text-[15px] font-semibold outline-none">Agent activity</h2>
            <IconButton label="Close agent activity" onClick={() => setAgentOpen(false)} className="size-9"><X className="size-4" /></IconButton>
          </div>
          <p id="agent-connection" role="status" className="flex items-center gap-2 px-6 pb-3 text-[12.5px] text-muted-foreground">
            <span aria-hidden className={cn("size-2 rounded-full", agent.connected.length ? (agent.working ? "agent-pulse bg-primary" : "bg-success") : "bg-border-strong")} />
            {agent.connected.length ? `${who(agent.connected)} ${agent.working ? "is working" : "is connected"}` : "No agent connected. Agents connect through Assetarium’s MCP server."}
          </p>
          <div className="min-h-0 overflow-y-auto overscroll-contain px-4 pb-4 scroll-thin">
            {agent.proposals.length > 0 && (
              <section aria-labelledby="agent-proposals-title" className="mb-4 grid gap-2.5">
                <h3 id="agent-proposals-title" className="px-2 text-[12.5px] font-semibold">Waiting for you</h3>
                <div id="agent-proposals" className="grid gap-2.5"><ProposalReview proposals={agent.proposals} /></div>
              </section>
            )}
            <h3 className="px-2 pb-1.5 text-[12.5px] font-semibold">What agents did</h3>
            {entries.length ? (
              <ol id="agent-feed" ref={listRef} aria-live="polite" className="grid gap-0.5">
                {entries.map((entry: Json) => {
                  const { icon: Icon, tone } = KIND[entry.kind as keyof typeof KIND] || KIND.read;
                  return (
                    <motion.li key={entry.utc + entry.run} initial={reduce ? false : { opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={SPRING_LAYOUT}
                      className={cn("agent-entry flex items-start gap-2.5 rounded-xl px-2 py-1.5 text-[12.5px]", entry.kind === "say" && "bg-surface-2/70")} data-kind={entry.kind}>
                      <Icon className={cn("mt-0.5 size-3.5 shrink-0", tone)} aria-hidden />
                      <span className="min-w-0 flex-1 break-words">{entry.text}</span>
                      <time className="shrink-0 text-[11px] text-subtle tabular-nums" dateTime={entry.utc}>{time(entry.utc)}</time>
                      {entry.kind === "change" && entry.proposal_id && (
                        <button type="button" className="shrink-0 text-[11.5px] font-medium text-primary hover:underline" onClick={() => void decideAgentProposal(entry.proposal_id, "undo")}>Undo</button>
                      )}
                    </motion.li>
                  );
                })}
              </ol>
            ) : (
              <p id="agent-feed-empty" className="py-10 text-center text-[13px] text-muted-foreground">Nothing yet. What agents read, change and propose shows up here as it happens.</p>
            )}
          </div>
        </motion.section>
      )}
    </AnimatePresence>
  );
}
