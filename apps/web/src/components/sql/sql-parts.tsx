"use client";

import { ArrowDownUp, Check, ChevronRight, Copy, Lock, Table2 } from "lucide-react";
import { Fragment, useMemo, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { GlossaryOption, GlossaryTerm, SqlTable } from "@/lib/api/sql";

const KEYWORDS = new Set(
  (
    "select from where join inner left right full outer on group by order having limit offset as " +
    "with and or not in is null case when then else end distinct union all intersect except " +
    "count sum avg min max cast date interval desc asc between like ilike exists over partition"
  ).split(" "),
);

/** Minimal, safe SQL highlighter: tokens become spans; nothing is injected as HTML. */
function highlight(sql: string): ReactNode[] {
  return sql.split(/('(?:[^']|'')*'|\b\d+(?:\.\d+)?\b|\b[A-Za-z_]+\b)/g).map((part, i) => {
    if (!part) return null;
    if (part.startsWith("'")) {
      return (
        <span key={i} className="text-success">
          {part}
        </span>
      );
    }
    if (/^\d/.test(part)) {
      return (
        <span key={i} className="text-info">
          {part}
        </span>
      );
    }
    if (KEYWORDS.has(part.toLowerCase())) {
      return (
        <span key={i} className="font-semibold text-primary">
          {part}
        </span>
      );
    }
    return <Fragment key={i}>{part}</Fragment>;
  });
}

/** Line breaks before major clauses so long one-line SQL stays readable. */
export function formatSql(sql: string): string {
  return sql
    .replace(
      /\s+(FROM|WHERE|GROUP BY|ORDER BY|HAVING|LIMIT|JOIN|LEFT JOIN|INNER JOIN|UNION)\b/g,
      "\n$1",
    )
    .replace(/\), (\w+ AS \()/g, "),\n$1");
}

/** DRD §7.4 / §8 code block: syntax highlighted, read-only label, copy action. */
export function SqlCodeBlock({ sql, database }: { sql: string; database: string | null }) {
  const [copied, setCopied] = useState(false);
  const formatted = useMemo(() => formatSql(sql), [sql]);
  return (
    <figure className="rounded-lg border bg-background">
      <figcaption className="flex flex-wrap items-center justify-between gap-2 border-b px-3 py-2 text-[12px]">
        <span className="inline-flex items-center gap-1.5 font-medium">
          <Lock aria-hidden="true" className="size-3.5 text-primary" />
          Read-only SQL
          {database && (
            <>
              {" "}
              on <span className="font-mono">{database}</span>
            </>
          )}
        </span>
        <Button
          variant="ghost"
          size="xs"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(sql);
              setCopied(true);
              window.setTimeout(() => setCopied(false), 1500);
            } catch {
              /* clipboard unavailable: the text is still selectable */
            }
          }}
        >
          {copied ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}
          {copied ? "Copied" : "Copy SQL"}
        </Button>
      </figcaption>
      <pre className="max-h-80 overflow-auto p-3 font-mono text-[12.5px] leading-relaxed whitespace-pre-wrap">
        <code>{highlight(formatted)}</code>
      </pre>
    </figure>
  );
}

/** DRD §8 clarification panel: question, 2-4 choices, optional own definition, explicit confirm. */
export function ClarificationPanel({
  term,
  question,
  options,
  onConfirm,
  busy,
}: {
  term: string;
  question: string;
  options: GlossaryOption[];
  onConfirm: (choice: { option_id?: string; custom_definition?: string }) => void;
  busy: boolean;
}) {
  const [selected, setSelected] = useState<string | null>(null);
  const [custom, setCustom] = useState("");
  const ready = selected === "__custom" ? custom.trim().length > 3 : selected !== null;
  return (
    <section
      aria-labelledby="clarify"
      className="rounded-xl border-2 border-primary/40 bg-card px-5 py-4"
    >
      <h3 id="clarify" className="text-[16px] font-semibold">
        Clarification needed
      </h3>
      <p className="mt-1 text-[14px]">
        {question} Nothing has been run yet; KnowFlow waits for your choice.
      </p>
      <fieldset className="mt-3">
        <legend className="sr-only">Meaning of “{term}”</legend>
        <div className="flex flex-col gap-2">
          {options.map((o) => (
            <label
              key={o.id}
              className="flex cursor-pointer gap-3 rounded-lg border p-3 has-[:checked]:border-primary has-[:checked]:bg-accent"
            >
              <input
                type="radio"
                name="clarification"
                value={o.id}
                checked={selected === o.id}
                onChange={() => setSelected(o.id)}
                className="mt-1 accent-primary"
              />
              <span>
                <span className="block text-[14px] font-medium">{o.label}</span>
                <span className="block text-[13px] text-muted-foreground">{o.definition}</span>
              </span>
            </label>
          ))}
          <label className="flex cursor-pointer gap-3 rounded-lg border p-3 has-[:checked]:border-primary has-[:checked]:bg-accent">
            <input
              type="radio"
              name="clarification"
              value="__custom"
              checked={selected === "__custom"}
              onChange={() => setSelected("__custom")}
              className="mt-1 accent-primary"
            />
            <span className="flex-1">
              <span className="block text-[14px] font-medium">Define it myself</span>
              {selected === "__custom" && (
                <span className="mt-2 flex flex-col gap-1">
                  <Label htmlFor="custom-definition" className="text-[12px]">
                    What does “{term}” mean here?
                  </Label>
                  <Input
                    id="custom-definition"
                    value={custom}
                    maxLength={500}
                    onChange={(e) => setCustom(e.target.value)}
                    placeholder="e.g. most orders with a refund"
                  />
                </span>
              )}
            </span>
          </label>
        </div>
      </fieldset>
      <Button
        className="mt-3"
        disabled={!ready || busy}
        onClick={() =>
          onConfirm(
            selected === "__custom"
              ? { custom_definition: custom.trim() }
              : { option_id: selected! },
          )
        }
      >
        Use this meaning and continue
      </Button>
    </section>
  );
}

function compare(a: unknown, b: unknown): number {
  if (a === b) return 0;
  if (a === null || a === undefined) return 1;
  if (b === null || b === undefined) return -1;
  if (typeof a === "number" && typeof b === "number") return a - b;
  return String(a).localeCompare(String(b), undefined, { numeric: true });
}

/** DRD §7.4 results: horizontal scroll, sticky header, sortable columns, row cap disclosed. */
export function ResultsTable({ columns, rows }: { columns: string[]; rows: unknown[][] }) {
  const [sort, setSort] = useState<{ col: number; dir: 1 | -1 } | null>(null);
  const sorted = useMemo(() => {
    if (!sort) return rows;
    return [...rows].sort((x, y) => sort.dir * compare(x[sort.col], y[sort.col]));
  }, [rows, sort]);
  if (rows.length === 0) {
    return (
      <p className="rounded-lg border p-4 text-muted-foreground">The query returned no rows.</p>
    );
  }
  return (
    <div className="max-h-[480px] overflow-auto rounded-lg border">
      <table className="w-full text-[13px]">
        <caption className="sr-only">Query results</caption>
        <thead className="sticky top-0 z-10 bg-card shadow-[0_1px_0_var(--border)]">
          <tr>
            {columns.map((c, i) => (
              <th
                key={c + i}
                scope="col"
                className="px-3 py-2 text-left font-medium whitespace-nowrap"
              >
                <button
                  type="button"
                  className="inline-flex items-center gap-1 hover:text-primary"
                  onClick={() =>
                    setSort((s) =>
                      s?.col === i ? { col: i, dir: s.dir === 1 ? -1 : 1 } : { col: i, dir: 1 },
                    )
                  }
                  aria-label={`Sort by ${c}`}
                >
                  {c}
                  <ArrowDownUp aria-hidden="true" className="size-3 text-muted-foreground" />
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, ri) => (
            <tr key={ri} className="border-t">
              {row.map((v, ci) => (
                <td
                  key={ci}
                  className={`px-3 py-1.5 whitespace-nowrap ${typeof v === "number" ? "text-right font-mono tabular-nums" : ""}`}
                >
                  {v === null ? <span className="text-muted-foreground">NULL</span> : String(v)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** DRD §7.4 schema browser: allowed schemas, tables, columns and types, expand/collapse. */
export function SchemaBrowser({
  tables,
  glossary,
}: {
  tables: SqlTable[];
  glossary: GlossaryTerm[];
}) {
  return (
    <div className="flex flex-col gap-4">
      <div>
        <p className="text-[12px] font-medium tracking-wide text-muted-foreground uppercase">
          Allowed tables
        </p>
        <ul className="mt-2 flex flex-col gap-1">
          {tables.map((t) => (
            <li key={`${t.schema}.${t.name}`}>
              <details className="group rounded-md">
                <summary className="flex cursor-pointer list-none items-center gap-1.5 rounded-md px-1.5 py-1 text-[14px] hover:bg-muted">
                  <ChevronRight
                    aria-hidden="true"
                    className="size-3.5 transition-transform group-open:rotate-90"
                  />
                  <Table2 aria-hidden="true" className="size-3.5 text-muted-foreground" />
                  <span className="font-mono text-[13px]">
                    {t.schema}.{t.name}
                  </span>
                </summary>
                {t.description && (
                  <p className="mt-1 ml-7 text-[12px] text-muted-foreground">{t.description}</p>
                )}
                <ul className="mt-1 ml-7 flex flex-col gap-0.5 pb-1">
                  {t.columns.map((c) => (
                    <li key={c.name} className="text-[12px]" title={c.description ?? undefined}>
                      <span className="font-mono">{c.name}</span>{" "}
                      <span className="text-muted-foreground">
                        {c.dataType}
                        {c.nullable ? ", nullable" : ""}
                      </span>
                    </li>
                  ))}
                </ul>
              </details>
            </li>
          ))}
        </ul>
      </div>
      <div>
        <p className="text-[12px] font-medium tracking-wide text-muted-foreground uppercase">
          Glossary
        </p>
        <dl className="mt-2 flex flex-col gap-2 text-[13px]">
          {glossary.map((g) => (
            <div key={g.term}>
              <dt className="font-medium">
                {g.term}
                {g.kind === "ambiguous" && (
                  <span className="ml-1.5 rounded bg-muted px-1 text-[11px] font-normal">
                    asks you
                  </span>
                )}
              </dt>
              <dd className="text-muted-foreground">
                {g.kind === "ambiguous" ? g.options.map((o) => o.label).join(" · ") : g.definition}
              </dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  );
}
