import { CheckCircle2, MinusCircle } from "lucide-react";

import { StatusBadge } from "@/components/ui/status-badge";
import type { CaseResult } from "@/lib/api/evaluation";

function location(p: {
  page_start: number | null;
  page_end: number | null;
  section_path: string | null;
}) {
  const page =
    p.page_start === null
      ? null
      : p.page_end !== null && p.page_end !== p.page_start
        ? `pages ${p.page_start}–${p.page_end}`
        : `page ${p.page_start}`;
  return [page, p.section_path].filter(Boolean).join(" · ");
}

/** DRD §7.5 per-case split view: question + reference + expected evidence vs retrieved + answer. */
export function CaseInspector({ result: r }: { result: CaseResult }) {
  return (
    <div className="flex flex-col gap-4 rounded-lg border p-4" aria-label={`Case ${r.externalId}`}>
      <div>
        <p className="font-mono text-[12px] text-muted-foreground">
          {r.externalId} · {r.split} · {r.tags.join(", ")}
        </p>
        <p className="mt-1 text-[15px] font-medium">{r.question}</p>
        {r.referenceAnswer && (
          <p className="mt-1 text-[14px]">
            <span className="text-muted-foreground">Reference: </span>
            {r.referenceAnswer}
          </p>
        )}
        {r.failureCategory && (
          <StatusBadge tone="danger">{r.failureCategory.replaceAll("_", " ")}</StatusBadge>
        )}
        {r.error && <p className="mt-1 text-[13px] text-danger">{r.error}</p>}
      </div>

      <div>
        <p className="text-[12px] font-medium tracking-wide text-muted-foreground uppercase">
          Expected evidence
        </p>
        {r.answerable ? (
          <ul className="mt-1 flex flex-col gap-1 text-[13px]">
            {r.expectedEvidence.map((e, i) => (
              <li key={i}>
                <span className="font-medium">{e.document}</span>
                {e.page ? ` · page ${e.page}` : ""}
                {e.quote && <span className="text-muted-foreground"> — “{e.quote}”</span>}
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-1 text-[13px]">None: this question is unanswerable from the corpus.</p>
        )}
      </div>

      <div>
        <p className="text-[12px] font-medium tracking-wide text-muted-foreground uppercase">
          Retrieved passages
        </p>
        <ol className="mt-1 flex flex-col gap-2">
          {r.retrieved.map((p, i) => (
            <li
              key={p.chunk_id}
              className={`rounded-md border p-2.5 text-[13px] ${p.relevant ? "border-success/50" : ""}`}
            >
              <p className="flex items-center gap-1.5 text-[12px] text-muted-foreground">
                {p.relevant ? (
                  <CheckCircle2 aria-hidden="true" className="size-3.5 text-success" />
                ) : (
                  <MinusCircle aria-hidden="true" className="size-3.5" />
                )}
                <span className="sr-only">{p.relevant ? "Relevant." : "Not relevant."}</span>
                <span className="font-mono">#{i + 1}</span>
                <span className="font-medium text-foreground">{p.document_name}</span>
                {location(p) && <span>· {location(p)}</span>}
                <span className="ml-auto font-mono">
                  {Object.entries(p.ranks)
                    .map(([k, v]) => `${k} ${v}`)
                    .join(" · ")}
                </span>
              </p>
              <p className="mt-1 line-clamp-4 whitespace-pre-wrap">{p.excerpt}</p>
            </li>
          ))}
          {r.retrieved.length === 0 && (
            <li className="text-[13px] text-muted-foreground">Nothing retrieved.</li>
          )}
        </ol>
      </div>

      {r.answer !== null && (
        <div>
          <p className="text-[12px] font-medium tracking-wide text-muted-foreground uppercase">
            Generated answer {r.metrics.abstained === true && "(abstained)"}
          </p>
          <p className="mt-1 text-[14px] whitespace-pre-wrap">{r.answer}</p>
        </div>
      )}
    </div>
  );
}
