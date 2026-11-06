"use client";

import { Database, Loader2, Plus, SendHorizontal, Wrench } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { CopyCommand } from "@/components/ui/copy-command";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/ui/status-badge";
import { ApiError } from "@/lib/api/client";
import {
  addConnection,
  askSql,
  fetchConnections,
  fetchSchema,
  type Choice,
  type SchemaInfo,
  type SqlAnswer,
  type SqlConnection,
} from "@/lib/api/sql";

import { ClarificationPanel, ResultsTable, SchemaBrowser, SqlCodeBlock } from "./sql-parts";

function asApiError(err: unknown) {
  return err instanceof ApiError
    ? err
    : new ApiError("unexpected", "Something went wrong.", null, null);
}

const seconds = (ms: number | null) =>
  ms === null ? "" : `${(ms / 1000).toFixed(ms < 10_000 ? 1 : 0)} s`;

function AddConnectionDialog({
  open,
  onClose,
  onAdded,
}: {
  open: boolean;
  onClose: () => void;
  onAdded: (c: SqlConnection) => void;
}) {
  const [form, setForm] = useState({
    display_name: "",
    host: "localhost",
    port: "5432",
    database_name: "",
    username: "",
    password: "",
    schemas: "public",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm({ ...form, [k]: e.target.value });

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const c = await addConnection({
        display_name: form.display_name,
        host: form.host,
        port: Number(form.port),
        database_name: form.database_name,
        username: form.username,
        password: form.password,
        allowed_schemas: form.schemas
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
      });
      setForm({ ...form, password: "" });
      onAdded(c);
    } catch (err) {
      setError(asApiError(err).message);
    } finally {
      setBusy(false);
    }
  };

  const field = (k: keyof typeof form, label: string, type = "text") => (
    <div className="flex flex-col gap-1">
      <Label htmlFor={`conn-${k}`}>{label}</Label>
      <Input
        id={`conn-${k}`}
        type={type}
        value={form[k]}
        onChange={set(k)}
        required
        autoComplete={type === "password" ? "new-password" : "off"}
      />
    </div>
  );

  return (
    <AlertDialog open={open} onOpenChange={(o) => !o && onClose()}>
      <AlertDialogContent className="max-w-lg">
        <form onSubmit={submit}>
          <AlertDialogHeader>
            <AlertDialogTitle>Connect a PostgreSQL database</AlertDialogTitle>
            <AlertDialogDescription>
              Use a login role that can only SELECT. KnowFlow tests the connection, refuses
              superusers and roles with write access, and stores the password encrypted. It is never
              shown again.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="my-4 grid gap-3 sm:grid-cols-2">
            {field("display_name", "Name")}
            {field("database_name", "Database")}
            {field("host", "Host")}
            {field("port", "Port")}
            {field("username", "User")}
            {field("password", "Password", "password")}
            <div className="sm:col-span-2">
              {field("schemas", "Allowed schemas (comma-separated)")}
            </div>
          </div>
          {error && (
            <p role="alert" className="mb-3 text-[14px] text-danger">
              {error}
            </p>
          )}
          <AlertDialogFooter>
            <AlertDialogCancel type="button">Cancel</AlertDialogCancel>
            <Button type="submit" disabled={busy}>
              {busy && <Loader2 aria-hidden="true" className="animate-spin" />}
              Test and save
            </Button>
          </AlertDialogFooter>
        </form>
      </AlertDialogContent>
    </AlertDialog>
  );
}

/** DRD §7.4 SQL Analyst: schema browser left; question → clarification → SQL → result right. */
export function SqlView() {
  const [connections, setConnections] = useState<SqlConnection[] | null>(null);
  const [connectionId, setConnectionId] = useState<string | null>(null);
  const [schema, setSchema] = useState<SchemaInfo | null>(null);
  const [loadError, setLoadError] = useState<ApiError | null>(null);
  const [question, setQuestion] = useState("");
  const [asked, setAsked] = useState<string | null>(null);
  const [choices, setChoices] = useState<Choice[]>([]);
  const [answer, setAnswer] = useState<SqlAnswer | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [pending, setPending] = useState<number | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [adding, setAdding] = useState(false);
  const [recent, setRecent] = useState<string[]>([]);

  useEffect(() => {
    const ctrl = new AbortController();
    fetchConnections(ctrl.signal).then(
      (cs) => {
        setConnections(cs);
        setConnectionId((cur) => cur ?? cs[0]?.id ?? null);
      },
      (err: unknown) => !ctrl.signal.aborted && setLoadError(asApiError(err)),
    );
    return () => ctrl.abort();
  }, []);

  useEffect(() => {
    if (!connectionId) return;
    const ctrl = new AbortController();
    fetchSchema(connectionId, ctrl.signal).then(setSchema, (err: unknown) => {
      if (!ctrl.signal.aborted) setLoadError(asApiError(err));
    });
    return () => ctrl.abort();
  }, [connectionId]);

  useEffect(() => {
    if (pending === null) return;
    const id = window.setInterval(() => setElapsed(Date.now() - pending), 500);
    return () => window.clearInterval(id);
  }, [pending]);

  const run = async (q: string, nextChoices: Choice[], repair?: { sql: string; error: string }) => {
    if (!connectionId || !q.trim()) return;
    setPending(Date.now());
    setElapsed(0);
    setError(null);
    setAsked(q);
    setChoices(nextChoices);
    try {
      const a = await askSql({ connectionId, question: q, choices: nextChoices, repair });
      setAnswer(a);
      setRecent((r) => [q, ...r.filter((x) => x !== q)].slice(0, 8));
    } catch (err) {
      setError(asApiError(err));
      setAnswer(null);
    } finally {
      setPending(null);
    }
  };

  const connection = connections?.find((c) => c.id === connectionId) ?? null;
  const demoMissing = connections !== null && !connections.some((c) => c.isDemo);

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[26px] leading-tight font-semibold tracking-tight">SQL Analyst</h1>
          <p className="mt-1 max-w-prose text-[15px] text-muted-foreground">
            Ask questions about a connected database. KnowFlow asks before guessing what a business
            term means, shows the SQL it generated, validates it as a single read-only SELECT and
            runs it with a read-only role, a time limit and a row cap.
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          {connections && connections.length > 0 && (
            <div className="flex flex-col gap-1">
              <Label htmlFor="connection">Database</Label>
              <select
                id="connection"
                value={connectionId ?? ""}
                onChange={(e) => {
                  setConnectionId(e.target.value);
                  setSchema(null);
                  setAnswer(null);
                }}
                className="h-9 rounded-lg border bg-background px-3 text-[14px]"
              >
                {connections.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.displayName}
                  </option>
                ))}
              </select>
            </div>
          )}
          <Button variant="outline" onClick={() => setAdding(true)}>
            <Plus aria-hidden="true" />
            Connect a database
          </Button>
        </div>
      </header>

      {loadError && (
        <div role="alert" className="rounded-xl border bg-card p-5">
          <StatusBadge tone="danger">Database unavailable</StatusBadge>
          <p className="mt-2 text-muted-foreground">{loadError.message}</p>
        </div>
      )}
      {demoMissing && (
        <div role="status" className="rounded-xl border bg-card p-5">
          <StatusBadge tone="warning">Demo database not set up</StatusBadge>
          <p className="mt-2 text-[14px]">
            Set <code className="font-mono">DEMO_DB_READER_PASSWORD</code> in{" "}
            <code className="font-mono">.env</code>, then create the synthetic sales database and
            its read-only role, and restart the API:
          </p>
          <CopyCommand command="./scripts/dev.ps1 seed-demo" />
        </div>
      )}

      {connection && (
        <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
          <aside
            className="flex flex-col gap-4 rounded-xl border bg-card p-4 lg:self-start"
            aria-label="Schema"
          >
            <p className="flex items-center gap-2 text-[14px] font-medium">
              <Database aria-hidden="true" className="size-4 text-primary" />
              <span className="font-mono">{connection.databaseName}</span>
              <StatusBadge tone="ok">Read-only</StatusBadge>
            </p>
            {schema ? (
              <SchemaBrowser tables={schema.tables} glossary={schema.glossary} />
            ) : (
              <Skeleton className="h-48 w-full" />
            )}
            {recent.length > 0 && (
              <div>
                <p className="text-[12px] font-medium tracking-wide text-muted-foreground uppercase">
                  This session
                </p>
                <ul className="mt-1 flex flex-col">
                  {recent.map((q) => (
                    <li key={q}>
                      <button
                        type="button"
                        className="w-full truncate rounded px-1.5 py-1 text-left text-[13px] hover:bg-muted"
                        onClick={() => setQuestion(q)}
                        title={q}
                      >
                        {q}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </aside>

          <div className="flex min-w-0 flex-col gap-4">
            <form
              className="rounded-xl border bg-card p-3"
              onSubmit={(e) => {
                e.preventDefault();
                void run(question, []);
              }}
            >
              <Label htmlFor="sql-question" className="text-[13px]">
                Your question
              </Label>
              <textarea
                id="sql-question"
                value={question}
                rows={2}
                maxLength={1000}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
                    e.preventDefault();
                    void run(question, []);
                  }
                }}
                placeholder="e.g. Show me our best customers last month."
                className="mt-1.5 w-full resize-y rounded-lg border bg-background px-3 py-2 text-[15px] focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
              />
              <div className="mt-2 flex items-center justify-between gap-2">
                <p className="text-[12px] text-muted-foreground">
                  {schema
                    ? `At most ${schema.maxRows} rows · ${schema.statementTimeoutMs / 1000} s limit · `
                    : ""}
                  Ctrl+Enter to send
                </p>
                <Button type="submit" disabled={!question.trim() || pending !== null}>
                  {pending !== null ? (
                    <Loader2 aria-hidden="true" className="animate-spin" />
                  ) : (
                    <SendHorizontal aria-hidden="true" />
                  )}
                  Ask
                </Button>
              </div>
            </form>

            {pending !== null && (
              <div role="status" className="rounded-xl border bg-card px-5 py-4">
                <p className="flex items-center gap-2">
                  <Loader2 aria-hidden="true" className="size-4 animate-spin text-primary" />
                  Checking the question, writing SQL and validating it…
                </p>
                <p className="mt-1 text-[13px] text-muted-foreground tabular-nums">
                  {Math.floor(elapsed / 1000)} s elapsed. SQL generation runs on this machine&apos;s
                  CPU and usually takes 20–90 seconds.
                </p>
              </div>
            )}

            {error && (
              <div role="alert" className="rounded-xl border bg-card px-5 py-4">
                <StatusBadge tone="danger">The question failed</StatusBadge>
                <p className="mt-2">{error.message}</p>
                {error.requestId && (
                  <p className="mt-1 font-mono text-[12px] text-muted-foreground">
                    Request ID: {error.requestId}
                  </p>
                )}
              </div>
            )}

            {answer && pending === null && (
              <>
                {answer.status === "clarification_required" && answer.clarification && (
                  <ClarificationPanel
                    term={answer.clarification.term}
                    question={answer.clarification.question}
                    options={answer.clarification.options}
                    busy={pending !== null}
                    onConfirm={(c) =>
                      void run(asked ?? question, [
                        ...choices,
                        { term: answer.clarification!.term, ...c },
                      ])
                    }
                  />
                )}

                {answer.status !== "clarification_required" && (
                  <section
                    aria-label="Answer"
                    className="flex flex-col gap-3 rounded-xl border bg-card px-5 py-4"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      {answer.status === "executed" && (
                        <StatusBadge tone="ok">Ran read-only</StatusBadge>
                      )}
                      {answer.status === "rejected" && (
                        <StatusBadge tone="danger">Rejected, not run</StatusBadge>
                      )}
                      {answer.status === "failed" && (
                        <StatusBadge tone="danger">Query failed</StatusBadge>
                      )}
                      {answer.status === "unsupported" && (
                        <StatusBadge tone="warning">
                          Can&apos;t answer from this database
                        </StatusBadge>
                      )}
                      <span className="text-[13px] text-muted-foreground tabular-nums">
                        {answer.generationMs !== null &&
                          `SQL written in ${seconds(answer.generationMs)}`}
                        {answer.durationMs !== null && ` · executed in ${answer.durationMs} ms`}
                        {answer.model && ` · ${answer.model}`}
                      </span>
                    </div>
                    {answer.message && <p className="text-[14px]">{answer.message}</p>}
                    {answer.repairable && answer.sql && answer.message && (
                      <div>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() =>
                            void run(asked ?? question, choices, {
                              sql: answer.sql!,
                              error: answer.message!,
                            })
                          }
                        >
                          <Wrench aria-hidden="true" />
                          Ask the model to fix this query
                        </Button>
                        <p className="mt-1 text-[12px] text-muted-foreground">
                          Sends the database error back to the model once. The fix is validated
                          again before it runs.
                        </p>
                      </div>
                    )}
                    {answer.definitionsUsed.length > 0 && (
                      <p className="text-[13px]">
                        <span className="font-medium">Definitions used: </span>
                        {answer.definitionsUsed
                          .map((d) => `${d.term} = ${d.definition}`)
                          .join("; ")}
                      </p>
                    )}
                    {answer.sql && <SqlCodeBlock sql={answer.sql} database={answer.database} />}
                    {(answer.explanation || answer.assumptions.length > 0) && (
                      <div className="rounded-lg bg-muted/50 p-3 text-[14px]">
                        <p className="text-[12px] font-medium tracking-wide text-muted-foreground uppercase">
                          Model&apos;s interpretation (not a database fact)
                        </p>
                        {answer.explanation && <p className="mt-1">{answer.explanation}</p>}
                        {answer.assumptions.length > 0 && (
                          <ul className="mt-1 list-disc pl-5">
                            {answer.assumptions.map((a) => (
                              <li key={a}>{a}</li>
                            ))}
                          </ul>
                        )}
                      </div>
                    )}
                    {answer.status === "executed" && (
                      <>
                        <p className="text-[13px] tabular-nums">
                          <span className="font-medium">Result from the database:</span>{" "}
                          {answer.rowCount} row
                          {answer.rowCount === 1 ? "" : "s"}
                          {answer.truncated &&
                            ` (showing the first ${answer.rowCount}; more rows exist)`}
                        </p>
                        <ResultsTable columns={answer.columns} rows={answer.rows} />
                      </>
                    )}
                  </section>
                )}
              </>
            )}

            {!answer && pending === null && !error && (
              <div className="rounded-xl border border-dashed px-5 py-8 text-center text-muted-foreground">
                Ask about{" "}
                {connection.isDemo
                  ? "the synthetic sales data: customers, orders, products and payments"
                  : connection.databaseName}
                .
              </div>
            )}
          </div>
        </div>
      )}

      <AddConnectionDialog
        open={adding}
        onClose={() => setAdding(false)}
        onAdded={(c) => {
          setAdding(false);
          setConnections((cs) => [...(cs ?? []), c]);
          setConnectionId(c.id);
          toast.success(`Connected “${c.displayName}” (read-only verified).`);
        }}
      />
    </div>
  );
}
