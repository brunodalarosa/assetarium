import { Copy } from "lucide-react";
import { Fragment } from "react";
import { cn } from "@/lib/utils";
import { copyText } from "../app/store";
import { Button } from "./primitives";

// Design principle P3 (decision 0025): a command is never typed by hand. A command found in backend text starts with
// a project script or the owner CLI and runs until a word that starts a new sentence ("Then", "Create"…).
// tests/test_command_blocks.py reads this pattern and checks it against every backend message that carries a command.
export const COMMAND_PATTERN = String.raw`(?:\.\\scripts\\|\./scripts/|local-assets )\S*(?: (?![A-Z][a-z])\S+)*`;

/** A command in a monospaced block with Copy; run in a terminal in the Assetarium folder. */
export function CommandBlock({ command, className }: { command: string; className?: string }) {
  return (
    <div className={cn("command-block flex min-w-0 items-center gap-2 rounded-xl bg-surface-2 py-1.5 pr-1.5 pl-3 text-foreground", className)}>
      <code className="min-w-0 flex-1 break-all font-mono text-[11.5px] select-text">{command}</code>
      <Button variant="quiet" className="h-8 shrink-0 px-3 text-[12px]" onClick={() => void copyText(command, "Command copied. Run it in a terminal in the Assetarium folder.")}>
        <Copy className="size-3.5" aria-hidden />Copy
      </Button>
    </div>
  );
}

/** Text and the commands inside it, split so each command gets its own block. */
export function splitCommands(text: string): { text?: string; command?: string }[] {
  const parts: { text?: string; command?: string }[] = [];
  let last = 0;
  for (const match of text.matchAll(new RegExp(COMMAND_PATTERN, "g"))) {
    const command = match[0].replace(/[.,;:]+$/, "");
    if (match.index > last) parts.push({ text: text.slice(last, match.index).trim() });
    parts.push({ command });
    last = match.index + command.length;
  }
  if (last < text.length) parts.push({ text: text.slice(last).replace(/^[.,;:]\s*/, "").trim() });
  return parts.filter((p) => p.command || p.text);
}

/** A backend reason or fix: plain text, with any command in it shown as a CommandBlock. */
export function Reason({ text, className }: { text?: string | null; className?: string }) {
  if (!text) return null;
  const parts = splitCommands(text);
  if (!parts.some((p) => p.command)) return <span className={cn("min-w-0 break-words", className)}>{text}</span>;
  return (
    <div className={cn("grid min-w-0 gap-1.5 break-words", className)}>
      {parts.map((p, i) => <Fragment key={i}>{p.command ? <CommandBlock command={p.command} /> : <span>{p.text}</span>}</Fragment>)}
    </div>
  );
}
