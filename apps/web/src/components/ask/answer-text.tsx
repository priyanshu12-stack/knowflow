"use client";

import { Fragment, type ReactNode } from "react";

import type { Citation } from "@/lib/api/chat";

/**
 * Renders model output as a small, safe Markdown subset: paragraphs, bullet/numbered lists,
 * **bold** and `code`, with [n] turned into citation chips (DRD §7.3). Never uses innerHTML:
 * the model's text is untrusted.
 */

const INLINE = /(\[\d{1,3}\]|\*\*[^*]+\*\*|`[^`]+`)/g;

export function CitationChip({
  citation,
  selected,
  onSelect,
}: {
  citation: Citation;
  selected: boolean;
  onSelect: (c: Citation) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onSelect(citation)}
      aria-label={`Source ${citation.number}: ${citation.documentName}`}
      aria-pressed={selected}
      className="mx-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded-[5px] border border-primary/30 bg-accent px-1 align-[1px] font-mono text-[11px] font-semibold text-primary transition-colors duration-150 hover:border-primary hover:bg-primary hover:text-primary-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none aria-pressed:bg-primary aria-pressed:text-primary-foreground"
    >
      {citation.number}
    </button>
  );
}

function inline(
  text: string,
  citations: Citation[],
  selected: number | null,
  onSelect: (c: Citation) => void,
): ReactNode[] {
  return text.split(INLINE).map((part, i) => {
    const marker = /^\[(\d{1,3})\]$/.exec(part);
    if (marker) {
      const c = citations.find((x) => x.number === Number(marker[1]));
      return c ? (
        <CitationChip key={i} citation={c} selected={selected === c.number} onSelect={onSelect} />
      ) : (
        <Fragment key={i} />
      );
    }
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      return <strong key={i}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith("`") && part.endsWith("`") && part.length > 2) {
      return (
        <code key={i} className="rounded bg-muted px-1 font-mono text-[0.9em]">
          {part.slice(1, -1)}
        </code>
      );
    }
    return <Fragment key={i}>{part}</Fragment>;
  });
}

const BULLET = /^\s*[-*•]\s+/;
const NUMBERED = /^\s*\d+[.)]\s+/;

export function AnswerText({
  text,
  citations,
  selected,
  onSelect,
}: {
  text: string;
  citations: Citation[];
  selected: number | null;
  onSelect: (c: Citation) => void;
}) {
  const blocks = text.split(/\n{2,}/);
  return (
    <div className="flex flex-col gap-3 text-[15px] leading-[1.6]">
      {blocks.map((block, bi) => {
        const lines = block.split("\n").filter((l) => l.trim());
        if (lines.length > 0 && lines.every((l) => BULLET.test(l) || NUMBERED.test(l))) {
          const ordered = lines.every((l) => NUMBERED.test(l));
          const List = ordered ? "ol" : "ul";
          return (
            <List key={bi} className={ordered ? "list-decimal pl-6" : "list-disc pl-6"}>
              {lines.map((l, li) => (
                <li key={li} className="pl-1">
                  {inline(
                    l.replace(ordered ? NUMBERED : BULLET, ""),
                    citations,
                    selected,
                    onSelect,
                  )}
                </li>
              ))}
            </List>
          );
        }
        return (
          <p key={bi}>
            {lines.map((l, li) => (
              <Fragment key={li}>
                {li > 0 && <br />}
                {inline(l, citations, selected, onSelect)}
              </Fragment>
            ))}
          </p>
        );
      })}
    </div>
  );
}
