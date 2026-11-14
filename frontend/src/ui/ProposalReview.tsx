import { Check, X } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useMemo, useState } from "react";
import { SPRING_LAYOUT } from "@/lib/ease";
import { cn } from "@/lib/utils";
import type { Json } from "../app/api";
import { plural } from "../app/format";
import { commitStaged, previewStaged, type RuleChoice, stagedDecisions, stageRules, useApp } from "../app/store";
import { ruleText } from "./FolderPanel";
import { Button, Hint, Pressable } from "./primitives";

type Member = { id: string; index: number; pack: string; note?: string };
type Group = { key: string; rule: Json; members: Member[] };

// Same kind, same folders inside the pack, same target: the same decision, whatever the pack (design principle P1).
const signature = (rule: Json) => JSON.stringify(Object.keys(rule).filter((k) => k !== "note").sort().map((k) => [k, rule[k]]));
const packName = (p: Json) => p.pack || p.library_folder;

function groups(proposals: Json[]): Group[] {
  const found = new Map<string, Group>();
  for (const p of proposals)
    (p.rules || []).forEach((rule: Json, index: number) => {
      const key = signature(rule);
      if (!found.has(key)) found.set(key, { key, rule, members: [] });
      found.get(key)!.members.push({ id: p.id, index, pack: packName(p), note: rule.note });
    });
  // Shared rules first (the decisions worth making once), then each pack's own.
  return [...found.values()].sort((a, b) => b.members.length - a.members.length);
}

function choiceOf(members: Member[], staged: Record<string, Record<number, RuleChoice>>): RuleChoice | "mixed" | null {
  const seen = new Set(members.map((m) => staged[m.id]?.[m.index] ?? null));
  return seen.size === 1 ? [...seen][0] : "mixed";
}

/** Accept / Reject as a pair of toggles; pressing the chosen one again clears it. */
function Choice({ value, onChange, label, small }: { value: RuleChoice | "mixed" | null; onChange: (c: RuleChoice | null) => void; label: string; small?: boolean }) {
  const item = (choice: RuleChoice, Icon: typeof Check, text: string) => (
    <Pressable aria-pressed={value === choice} aria-label={`${text}: ${label}`} data-choice={choice}
      tooltip={value === choice ? "Clears this choice" : choice === "accept" ? "Stages this rule to apply; nothing changes until you apply" : "Stages this rule to be turned down; nothing changes until you apply"}
      onClick={() => onChange(value === choice ? null : choice)}
      className={cn("flex items-center gap-1 rounded-full font-medium transition-colors", small ? "h-7 px-2.5 text-[11.5px]" : "h-8 px-3 text-[12px]",
        value === choice ? (choice === "accept" ? "bg-primary text-primary-foreground" : "bg-surface-2 text-foreground ring-1 ring-border-strong")
          : "text-muted-foreground hover:bg-surface-2 hover:text-foreground")}>
      <Icon className="size-3.5" aria-hidden />{text}
    </Pressable>
  );
  return <div role="group" aria-label={label} className="flex shrink-0 gap-1">{item("accept", Check, "Accept")}{item("reject", X, "Reject")}</div>;
}

function RuleGroup({ group }: { group: Group }) {
  const staged = useApp((s) => s.agent.staged);
  const value = choiceOf(group.members, staged);
  const text = ruleText(group.rule);
  const shared = group.members.length > 1;
  return (
    <motion.li layout transition={SPRING_LAYOUT} className="proposal-group grid gap-2 rounded-xl border border-border bg-surface px-3 py-2.5"
      data-state={value ?? "undecided"} data-packs={group.members.length}>
      <div className="flex items-start gap-3">
        <div className="grid min-w-0 flex-1 gap-0.5">
          <p className="text-[12.5px] break-words">{text}</p>
          <p className="text-[11.5px] text-muted-foreground">
            {shared ? `In ${plural(group.members.length, "pack", "packs")}` : `Only in ${group.members[0].pack}`}{!shared && group.members[0].note ? ` · ${group.members[0].note}` : ""}
          </p>
        </div>
        <Choice value={value} label={text} onChange={(c) => stageRules(group.members, c)} />
      </div>
      {shared && (
        <details className="text-[12px]">
          <summary className="cursor-pointer text-muted-foreground">{value === "mixed" ? "Decided per pack" : "Choose per pack"}</summary>
          <ul className="mt-1.5 grid gap-1">
            {group.members.map((m) => (
              <li key={m.id} className="flex items-center gap-2">
                <Hint content={m.note ? `${m.pack} · ${m.note}` : m.pack}><span className="min-w-0 flex-1 truncate">{m.pack}</span></Hint>
                <Choice small value={staged[m.id]?.[m.index] ?? null} label={`${text} in ${m.pack}`} onChange={(c) => stageRules([m], c)} />
              </li>
            ))}
          </ul>
        </details>
      )}
    </motion.li>
  );
}

/** One library folder's waiting proposals as grouped rules, decided together and applied with one scan. */
function FolderReview({ folder, proposals }: { folder: string; proposals: Json[] }) {
  const staged = useApp((s) => s.agent.staged);
  const committing = useApp((s) => s.agent.committing);
  const list = useMemo(() => groups(proposals), [proposals]);
  const decisions = stagedDecisions(proposals, staged);
  const key = JSON.stringify(decisions);
  const [preview, setPreview] = useState<Json>(null);
  useEffect(() => {
    if (!decisions.length) return setPreview(null);
    let live = true;
    const timer = setTimeout(() => void previewStaged(decisions).then((r) => live && setPreview(r)), 250);
    return () => { live = false; clearTimeout(timer); };
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps
  const all = proposals.flatMap((p) => (p.rules || []).map((_: Json, index: number) => ({ id: p.id, index })));
  const undecided = proposals.length - decisions.length;
  const applies = decisions.filter((d) => d.decision === "apply").length;
  const faulty = (preview?.packs || []).filter((p: Json) => p.status === "faulty");
  return (
    <section className="proposal-review grid gap-2.5 rounded-2xl border border-border bg-surface-2/60 p-4" data-folder={folder}>
      <div className="flex flex-wrap items-center gap-2">
        <div className="grid min-w-0 flex-1 gap-0.5">
          <p className="text-[13px] font-semibold">{folder.startsWith("agent-practice-") ? "Practice packs" : folder}</p>
          <p className="text-[11.5px] text-muted-foreground">{plural(proposals.length, "pack", "packs")} · {plural(list.length, "different rule", "different rules")}</p>
        </div>
        <Button variant="quiet" className="h-8 px-3 text-[12px]" data-action="accept-all" tooltip="Stages every rule here to apply; nothing changes until you apply" onClick={() => stageRules(all, "accept")}>Accept all</Button>
      </div>
      <ul className="grid gap-1.5">{list.map((g) => <RuleGroup key={g.key} group={g} />)}</ul>
      <details className="text-[12px] text-muted-foreground">
        <summary className="cursor-pointer">What the agent said</summary>
        <ul className="mt-1.5 grid gap-1.5">
          {proposals.map((p) => (
            <li key={p.id}><span className="font-medium text-foreground">{packName(p)}</span> · {p.origin?.agent || "Your agent"}{p.origin?.note ? ` · “${p.origin.note}”` : ""}</li>
          ))}
        </ul>
      </details>
      <div className="proposal-commit grid gap-2 border-t border-border pt-2.5">
        <p className="proposal-preview text-[12px] whitespace-pre-line" aria-live="polite">
          {!decisions.length ? "Accept or reject the rules above, then apply them together."
            : !preview ? "Measuring…"
            : preview.status === "faulty" ? preview.reason
            : [preview.excluded_files ? `→ ${plural(preview.excluded_files, "file", "files")} skipped (nothing is deleted)` : "",
               preview.restored_files ? `→ ${plural(preview.restored_files, "file", "files")} included again` : "",
               ...(preview.packs || []).filter((p: Json) => p.status === "ready").flatMap((p: Json) => p.lines.filter((l: string) => !/files? (skipped|included)/.test(l)).map((l: string) => `→ ${p.pack}: ${l}`))]
              .filter(Boolean).join("\n") || "→ Nothing changes besides the rejected proposals"}
        </p>
        {faulty.map((p: Json) => <p key={p.id} className="text-[12px] text-fault">{p.reason}</p>)}
        <div className="flex flex-wrap items-center gap-3">
          <Button className="h-9 px-4" data-action="apply-staged" disabled={!decisions.length || committing !== null} disabledReason={decisions.length ? undefined : "Accept or reject a rule first"} tooltip="Saves your accepted and rejected rules together; the arrows above show what changes" onClick={() => void commitStaged(folder, decisions)}>
            {committing === folder ? "Applying…" : decisions.length ? `Apply decisions for ${plural(decisions.length, "pack", "packs")}` : "Apply"}
          </Button>
          <p className="text-[11.5px] text-muted-foreground">
            {applies ? "Scans the library folder once. " : ""}Nothing is rendered, described or written into a pack.{undecided && decisions.length ? ` ${plural(undecided, "pack waits", "packs wait")} for a decision.` : ""}
          </p>
        </div>
      </div>
    </section>
  );
}

export function ProposalReview({ proposals }: { proposals: Json[] }) {
  const folders = [...new Set(proposals.map((p) => p.library_folder))];
  return <>{folders.map((f) => <FolderReview key={f} folder={f} proposals={proposals.filter((p) => p.library_folder === f)} />)}</>;
}
