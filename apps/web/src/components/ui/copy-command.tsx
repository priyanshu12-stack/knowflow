"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";

/** A setup/recovery command the user can copy (DRD §13 "exact setup/check action"). */
export function CopyCommand({ command }: { command: string }) {
  const [copied, setCopied] = useState(false);
  const [failed, setFailed] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(command);
      setCopied(true);
      setFailed(false);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setFailed(true);
    }
  };
  return (
    <div className="mt-2 flex max-w-full items-center gap-1 rounded-lg border bg-background pl-3">
      <code className="min-w-0 flex-1 overflow-x-auto py-1.5 font-mono text-[12.5px] whitespace-nowrap">
        {command}
      </code>
      <Button
        variant="ghost"
        size="icon-sm"
        onClick={copy}
        aria-label={copied ? "Command copied" : `Copy command: ${command}`}
      >
        {copied ? (
          <Check aria-hidden="true" className="text-success" />
        ) : (
          <Copy aria-hidden="true" />
        )}
      </Button>
      <span role="status" className="sr-only">
        {copied ? "Copied to clipboard" : failed ? "Copy failed; select the text instead" : ""}
      </span>
    </div>
  );
}
