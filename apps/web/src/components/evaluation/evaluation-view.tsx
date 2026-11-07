"use client";

import {
  CheckCircle2,
  CircleX,
  Download,
  FlaskConical,
  Loader2,
  Play,
  Trash2,
  Upload,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/ui/status-badge";
import { ApiError } from "@/lib/api/client";
import {
  createDataset,
  deleteRun,
  exportUrl,
  fetchDatasets,
  fetchRun,
  fetchRuns,
  importCases,
  loadSample,
  startRun,
  type Aggregate,
  type Dataset,
  type Run,
  type RunConfig,
  type RunDetail,
} from "@/lib/api/evaluation";
import { fetchModelSettings } from "@/lib/api/settings";

import { CaseInspector } from "./case-inspector";

function asApiError(err: unknown) {
  return err instanceof ApiError
    ? err
    : new ApiError("unexpected", "Something went wrong.", null, null);
}

const PRESETS: { id: RunConfig["preset"]; title: string; detail: string }[] = [
  { id: "S1", title: "S1 · Fixed + dense", detail: "Fixed-size chunks, vector search (baseline)" },
  { id: "S2", title: "S2 · Recursive + dense", detail: "Structure-aware chunks, vector search" },
  { id: "S3", title: "S3 · Hybrid", detail: "Recursive chunks, vector + keyword fused with RRF" },
  { id: "S4", title: "S4 · Hybrid + reranker", detail: "S3 followed by the local CrossEncoder" },
];

/** Metric definitions shown as tooltips/captions (DRD §7.5: label, value, sample count, definition). */
export const METRICS: {
  key: keyof Aggregate;
  label: string;
  definition: string;
  n?: keyof Aggregate;
}[] = [
  {
    key: "recall_at_k",
    label: "Recall@K",
    definition: "Share of expected evidence found in the top K passages.",
    n: "retrieval_cases",
  },
  {
    key: "precision_at_k",
    label: "Precision@K",
    definition: "Share of the top K passages that are relevant.",
    n: "retrieval_cases",
  },
  {
    key: "mrr",
    label: "MRR",
    definition: "1 / rank of the first relevant passage, averaged.",
    n: "retrieval_cases",
  },
  {
    key: "ndcg_at_k",
    label: "nDCG@K",
    definition: "Ranking quality; each evidence item counts once.",
    n: "retrieval_cases",
  },
  {
    key: "abstention_correct",
    label: "Abstention",
    definition: "Answered answerable questions and abstained on unanswerable ones.",
    n: "abstention_correct_n",
  },
  {
    key: "citation_precision",
    label: "Citation precision",
    definition: "Share of cited passages that contain the expected evidence.",
    n: "citation_precision_n",
  },
];

const fmt = (v: number | null | undefined) => (v === null || v === undefined ? "—" : v.toFixed(3));
const ms = (v: number | null | undefined) =>
  v === null || v === undefined
    ? "—"
    : v >= 1000
      ? `${(v / 1000).toFixed(1)} s`
      : `${Math.round(v)} ms`;

function RunStatusBadge({ run }: { run: Run }) {
  if (run.status === "succeeded") return <StatusBadge tone="ok">Done</StatusBadge>;
  if (run.status === "failed") return <StatusBadge tone="danger">Failed</StatusBadge>;
  if (run.status === "queued") return <StatusBadge tone="neutral">Queued</StatusBadge>;
  return (
    <StatusBadge tone="pending">
      {run.progress}/{run.total}
    </StatusBadge>
  );
}

function DatasetPanel({
  datasets,
  selected,
  onSelect,
  onChanged,
}: {
  datasets: Dataset[];
  selected: Dataset | null;
  onSelect: (id: string) => void;
  onChanged: (selectId?: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState("");
  const [version, setVersion] = useState("v1");
  const fileRef = useRef<HTMLInputElement>(null);
  const [importErrors, setImportErrors] = useState<{ row: number; message: string }[]>([]);

  const sample = async () => {
    setBusy(true);
    try {
      const r = await loadSample();
      toast.success(
        r.queued > 0
          ? `Loaded the sample set. ${r.queued} sample documents are being indexed.`
          : "Sample set ready; its documents were already in the library.",
      );
      onChanged(r.datasetId);
    } catch (err) {
      toast.error(asApiError(err).message);
    } finally {
      setBusy(false);
    }
  };

  const createAndImport = async (file: File) => {
    setBusy(true);
    setImportErrors([]);
    try {
      const ds = await createDataset(name.trim(), version.trim() || "v1");
      const summary = await importCases(ds.id, file);
      setImportErrors(summary.errors);
      toast[summary.imported ? "success" : "error"](
        `Imported ${summary.imported} case${summary.imported === 1 ? "" : "s"}` +
          (summary.errors.length ? `; ${summary.errors.length} rows rejected.` : "."),
      );
      setName("");
      onChanged(ds.id);
    } catch (err) {
      toast.error(asApiError(err).message);
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  return (
    <section aria-labelledby="datasets" className="rounded-xl border bg-card px-5 py-5">
      <h2 id="datasets" className="text-[18px] font-semibold tracking-tight">
        Dataset
      </h2>
      {datasets.length === 0 ? (
        <div className="mt-2">
          <p className="max-w-prose text-[14px] text-muted-foreground">
            An evaluation dataset is a fixed list of questions with the passages that answer them.
            Start with the bundled synthetic set, or import your own CSV/JSONL.
          </p>
        </div>
      ) : (
        <div className="mt-3 flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="dataset">Dataset version</Label>
            <select
              id="dataset"
              value={selected?.id ?? ""}
              onChange={(e) => onSelect(e.target.value)}
              className="h-9 min-w-64 rounded-lg border bg-background px-3 text-[14px] focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
            >
              {datasets.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name} · {d.version}
                </option>
              ))}
            </select>
          </div>
          {selected && (
            <p className="pb-2 text-[14px] text-muted-foreground tabular-nums">
              {selected.cases} cases ({selected.devCases} dev / {selected.testCases} held-out test)
              · {selected.runs} run{selected.runs === 1 ? "" : "s"}
            </p>
          )}
        </div>
      )}
      {selected?.description && (
        <p className="mt-2 max-w-prose text-[13px] text-muted-foreground">{selected.description}</p>
      )}
      {selected && selected.missingDocuments.length > 0 && (
        <div role="status" className="mt-3 rounded-lg border p-3 text-[14px]">
          <StatusBadge tone="warning">Documents not indexed</StatusBadge>
          <p className="mt-1.5">
            These documents are named in the evidence but aren&apos;t ready in the library, so their
            cases will score zero: {selected.missingDocuments.join(", ")}.{" "}
            <Link href="/library" className="text-primary underline">
              Open the library
            </Link>
          </p>
        </div>
      )}

      <details className="mt-4">
        <summary className="cursor-pointer text-[14px] font-medium">Add a dataset</summary>
        <div className="mt-3 flex flex-col gap-4">
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="outline"
              onClick={() => void sample()}
              disabled={busy}
              className="h-auto min-h-9 max-w-full py-2 whitespace-normal"
            >
              <FlaskConical aria-hidden="true" />
              Load sample documents and gold set
            </Button>
            <span className="text-[13px] text-muted-foreground">
              5 synthetic documents and 50 labelled questions
            </span>
          </div>
          <div className="flex flex-wrap items-end gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ds-name">Name</Label>
              <Input
                id="ds-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Policies QA"
              />
            </div>
            <div className="flex w-24 flex-col gap-1.5">
              <Label htmlFor="ds-version">Version</Label>
              <Input id="ds-version" value={version} onChange={(e) => setVersion(e.target.value)} />
            </div>
            <input
              ref={fileRef}
              type="file"
              accept=".jsonl,.ndjson,.csv"
              className="sr-only"
              id="ds-file"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) void createAndImport(f);
              }}
            />
            <Button
              disabled={busy || !name.trim()}
              onClick={() => fileRef.current?.click()}
              title={name.trim() ? undefined : "Enter a dataset name first"}
            >
              <Upload aria-hidden="true" />
              Import CSV or JSONL…
            </Button>
          </div>
          <p className="text-[13px] text-muted-foreground">
            Columns: <code className="font-mono">question</code>, optional{" "}
            <code className="font-mono">
              id, split (dev|test), reference_answer, answerable, tags
            </code>{" "}
            and evidence as <code className="font-mono">expected_evidence</code> (JSON) or{" "}
            <code className="font-mono">evidence_document, evidence_quote, evidence_page</code>.
          </p>
          {importErrors.length > 0 && (
            <div role="alert" className="rounded-lg border p-3 text-[13px]">
              <p className="font-medium">Rejected rows</p>
              <ul className="mt-1 max-h-40 overflow-y-auto">
                {importErrors.map((e) => (
                  <li key={`${e.row}-${e.message}`}>
                    Row {e.row}: {e.message}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </details>
    </section>
  );
}

function ConfigPanel({
  dataset,
  rerankerAvailable,
  onStarted,
}: {
  dataset: Dataset;
  rerankerAvailable: boolean;
  onStarted: () => void;
}) {
  const [preset, setPreset] = useState<RunConfig["preset"]>("S2");
  const [topK, setTopK] = useState(5);
  const [split, setSplit] = useState<RunConfig["split"]>("all");
  const [answers, setAnswers] = useState(false);
  const [busy, setBusy] = useState(false);
  const cases =
    split === "all" ? dataset.cases : split === "dev" ? dataset.devCases : dataset.testCases;

  const run = async () => {
    setBusy(true);
    try {
      await startRun(dataset.id, { preset, top_k: topK, split, generate_answers: answers });
      toast.success("Run queued. It runs in the background; you can leave this page.");
      onStarted();
    } catch (err) {
      toast.error(asApiError(err).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section aria-labelledby="config" className="rounded-xl border bg-card px-5 py-5">
      <h2 id="config" className="text-[18px] font-semibold tracking-tight">
        Configuration
      </h2>
      <fieldset className="mt-3">
        <legend className="text-[14px] font-medium">Retrieval strategy</legend>
        <div className="mt-2 grid gap-2 sm:grid-cols-2">
          {PRESETS.map((p) => {
            const disabled = p.id === "S4" && !rerankerAvailable;
            return (
              <label
                key={p.id}
                className={`flex cursor-pointer gap-3 rounded-lg border p-3 has-[:checked]:border-primary has-[:checked]:bg-accent ${disabled ? "cursor-not-allowed opacity-60" : ""}`}
              >
                <input
                  type="radio"
                  name="preset"
                  value={p.id}
                  checked={preset === p.id}
                  disabled={disabled}
                  onChange={() => setPreset(p.id)}
                  className="mt-1 accent-primary"
                />
                <span>
                  <span className="block text-[14px] font-medium">{p.title}</span>
                  <span className="block text-[13px] text-muted-foreground">
                    {disabled ? "Needs the optional reranker (see Models & Settings)" : p.detail}
                  </span>
                </span>
              </label>
            );
          })}
        </div>
      </fieldset>
      <div className="mt-4 flex flex-wrap items-end gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="topk">Top K</Label>
          <select
            id="topk"
            value={topK}
            onChange={(e) => setTopK(Number(e.target.value))}
            className="h-9 rounded-lg border bg-background px-3 text-[14px]"
          >
            {[3, 5, 10].map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="split">Cases</Label>
          <select
            id="split"
            value={split}
            onChange={(e) => setSplit(e.target.value as RunConfig["split"])}
            className="h-9 rounded-lg border bg-background px-3 text-[14px]"
          >
            <option value="all">All ({dataset.cases})</option>
            <option value="dev">Development ({dataset.devCases})</option>
            <option value="test">Held-out test ({dataset.testCases})</option>
          </select>
        </div>
        <label className="flex items-center gap-2 pb-2 text-[14px]">
          <input
            type="checkbox"
            className="size-4 accent-primary"
            checked={answers}
            onChange={(e) => setAnswers(e.target.checked)}
          />
          Also generate answers
        </label>
        <Button onClick={() => void run()} disabled={busy || cases === 0} className="ml-auto">
          {busy ? (
            <Loader2 aria-hidden="true" className="animate-spin" />
          ) : (
            <Play aria-hidden="true" />
          )}
          Run evaluation
        </Button>
      </div>
      {answers && (
        <p className="mt-2 text-[13px] text-muted-foreground" role="note">
          Answer generation measures abstention and citation precision, but takes roughly 30–90
          seconds per case on CPU, so {cases} cases can take{" "}
          {Math.max(1, Math.round((cases * 45) / 60))} minutes or more.
        </p>
      )}
    </section>
  );
}

/** DRD §7.5 Evaluation Lab: the comparison table is the primary artifact; no fake charts. */
export function EvaluationView() {
  const [datasets, setDatasets] = useState<Dataset[] | null>(null);
  const [datasetId, setDatasetId] = useState<string | null>(null);
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [rerankerAvailable, setRerankerAvailable] = useState(false);
  const [openRun, setOpenRun] = useState<RunDetail | null>(null);
  const [tick, setTick] = useState(0);

  const refresh = useCallback((selectId?: string) => {
    if (selectId) setDatasetId(selectId);
    setTick((t) => t + 1);
  }, []);

  useEffect(() => {
    const ctrl = new AbortController();
    fetchDatasets(ctrl.signal).then(
      (ds) => {
        setDatasets(ds);
        setDatasetId((cur) => (cur && ds.some((d) => d.id === cur) ? cur : (ds[0]?.id ?? null)));
      },
      (err: unknown) => !ctrl.signal.aborted && setError(asApiError(err)),
    );
    fetchModelSettings(ctrl.signal).then(
      (s) => setRerankerAvailable(s.reranker.available),
      () => undefined,
    );
    return () => ctrl.abort();
  }, [tick]);

  useEffect(() => {
    if (!datasetId) return;
    const ctrl = new AbortController();
    fetchRuns(datasetId, ctrl.signal).then(setRuns, () => undefined);
    return () => ctrl.abort();
  }, [datasetId, tick]);

  const active = runs?.some((r) => r.status === "queued" || r.status === "running") ?? false;
  useEffect(() => {
    if (!active) return;
    const id = window.setTimeout(() => setTick((t) => t + 1), 3000);
    return () => window.clearTimeout(id);
  }, [active, tick]);

  const open = async (run: Run) => {
    try {
      setOpenRun(await fetchRun(run.id));
    } catch (err) {
      toast.error(asApiError(err).message);
    }
  };

  const remove = async (run: Run) => {
    try {
      await deleteRun(run.id);
      if (openRun?.id === run.id) setOpenRun(null);
      refresh();
    } catch (err) {
      toast.error(asApiError(err).message);
    }
  };

  const dataset = datasets?.find((d) => d.id === datasetId) ?? null;

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-[26px] leading-tight font-semibold tracking-tight">Evaluation Lab</h1>
        <p className="mt-1 max-w-prose text-[15px] text-muted-foreground">
          Compare retrieval and answer configurations on a fixed, labelled dataset. Every run
          records its configuration, models and machine so results can be reproduced. Metrics are
          computed deterministically; no model is used as a judge.
        </p>
      </header>

      {error && (
        <div role="alert" className="rounded-xl border bg-card p-5">
          <StatusBadge tone="danger">Evaluation Lab unavailable</StatusBadge>
          <p className="mt-2 text-muted-foreground">{error.message}</p>
        </div>
      )}
      {!datasets && !error && <Skeleton className="h-40 w-full" />}
      {datasets && (
        <DatasetPanel
          datasets={datasets}
          selected={dataset}
          onSelect={(id) => {
            setDatasetId(id);
            setOpenRun(null);
          }}
          onChanged={refresh}
        />
      )}
      {dataset && (
        <ConfigPanel dataset={dataset} rerankerAvailable={rerankerAvailable} onStarted={refresh} />
      )}

      {dataset && (
        <section aria-labelledby="runs" className="rounded-xl border bg-card">
          <div className="px-5 pt-5">
            <h2 id="runs" className="text-[18px] font-semibold tracking-tight">
              Runs
            </h2>
            <p className="mt-1 text-[13px] text-muted-foreground">
              K is each run&apos;s top-K. Retrieval metrics cover answerable cases; answer metrics
              appear only for runs that generated answers. The sample count is shown under each
              value.
            </p>
          </div>
          {runs === null && <Skeleton className="m-5 h-24" />}
          {runs?.length === 0 && (
            <p className="px-5 py-6 text-muted-foreground">
              No runs yet. Pick a strategy above and run it; compare at least S1–S3 on the same
              dataset version.
            </p>
          )}
          {runs && runs.length > 0 && (
            <div className="relative mt-3 overflow-x-auto">
              <table className="w-full min-w-[980px] text-[14px]">
                <caption className="sr-only">Evaluation runs and their metrics</caption>
                <thead>
                  <tr className="border-y bg-muted/40 text-left text-[12px] text-muted-foreground">
                    <th className="px-5 py-2 font-medium">Run</th>
                    <th className="py-2 font-medium">Status</th>
                    {METRICS.map((m) => (
                      <th key={m.key} className="py-2 text-right font-medium" title={m.definition}>
                        {m.label}
                      </th>
                    ))}
                    <th
                      className="py-2 text-right font-medium"
                      title="Retrieval latency per question, median / 95th percentile"
                    >
                      Retrieval p50 / p95
                    </th>
                    <th className="px-5 py-2">
                      <span className="sr-only">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((run) => {
                    const a = run.aggregate;
                    const k = (run.config.top_k as number | undefined) ?? "?";
                    return (
                      <tr key={run.id} className="border-b last:border-0 hover:bg-muted/30">
                        <td className="px-5 py-2.5">
                          <button
                            type="button"
                            className="text-left font-medium hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                            onClick={() => void open(run)}
                            disabled={run.status !== "succeeded"}
                          >
                            {run.label}
                          </button>
                          <p className="text-[12px] text-muted-foreground tabular-nums">
                            K={k} · {String(run.config.split ?? "all")} ·{" "}
                            {new Date(run.createdAt).toLocaleString()}
                          </p>
                          {run.error && <p className="text-[12px] text-danger">{run.error}</p>}
                        </td>
                        <td className="py-2.5">
                          <RunStatusBadge run={run} />
                        </td>
                        {METRICS.map((m) => (
                          <td
                            key={m.key}
                            className="py-2.5 text-right font-mono text-[13px] tabular-nums"
                          >
                            {fmt(a[m.key] as number | null | undefined)}
                            {m.n && typeof a[m.n] === "number" && (a[m.key] ?? null) !== null && (
                              <span className="block text-[11px] text-muted-foreground">
                                n={a[m.n] as number}
                              </span>
                            )}
                          </td>
                        ))}
                        <td className="py-2.5 text-right font-mono text-[13px] tabular-nums">
                          {ms(a.retrieval_ms_p50)} / {ms(a.retrieval_ms_p95)}
                        </td>
                        <td className="px-5 py-2.5">
                          <div className="flex justify-end gap-1">
                            {run.status === "succeeded" && (
                              <>
                                <Button
                                  asChild
                                  variant="ghost"
                                  size="icon-sm"
                                  aria-label={`Export ${run.label} as CSV`}
                                >
                                  <a href={exportUrl(run.id, "csv")} download>
                                    <Download aria-hidden="true" />
                                  </a>
                                </Button>
                                <Button
                                  asChild
                                  variant="ghost"
                                  size="sm"
                                  aria-label={`Export ${run.label} as JSON`}
                                >
                                  <a href={exportUrl(run.id, "json")} download>
                                    JSON
                                  </a>
                                </Button>
                              </>
                            )}
                            {run.status !== "running" && (
                              <Button
                                variant="ghost"
                                size="icon-sm"
                                aria-label={`Delete ${run.label}`}
                                onClick={() => void remove(run)}
                              >
                                <Trash2 aria-hidden="true" />
                              </Button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {openRun && <RunDetailPanel run={openRun} onClose={() => setOpenRun(null)} />}
    </div>
  );
}

function RunDetailPanel({ run, onClose }: { run: RunDetail; onClose: () => void }) {
  const [caseId, setCaseId] = useState<string | null>(null);
  const [onlyFailures, setOnlyFailures] = useState(false);
  const results = onlyFailures ? run.results.filter((r) => r.failureCategory) : run.results;
  const selected = run.results.find((r) => r.caseId === caseId) ?? null;
  const a = run.aggregate;
  const failures = Object.entries(a.failure_categories ?? {});
  const machine = run.config.machine as Record<string, unknown> | undefined;
  const embedding = run.config.embedding as Record<string, unknown> | null | undefined;

  return (
    <section aria-labelledby="run-detail" className="rounded-xl border bg-card px-5 py-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="run-detail" className="text-[18px] font-semibold tracking-tight">
            {run.label}
          </h2>
          <p className="mt-1 text-[13px] text-muted-foreground">
            {embedding && (
              <>
                Embedding <span className="font-mono">{String(embedding.model)}</span> (
                {String(embedding.dimension)}-d) ·{" "}
              </>
            )}
            {machine && (
              <>
                {String(machine.cpu_count)} CPU threads
                {machine.ram_total_gb ? `, ${String(machine.ram_total_gb)} GB RAM` : ""}
              </>
            )}
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={onClose}>
          Close
        </Button>
      </div>

      <dl className="mt-4 grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {METRICS.map((m) => (
          <div key={m.key} className="rounded-lg border bg-background p-3" title={m.definition}>
            <dt className="text-[12px] text-muted-foreground">{m.label}</dt>
            <dd className="mt-1 font-mono text-[20px] font-semibold tabular-nums">
              {fmt(a[m.key] as number | null | undefined)}
            </dd>
            <dd className="text-[11px] text-muted-foreground">
              {m.n && typeof a[m.n] === "number" ? `n = ${a[m.n] as number}` : "not measured"}
            </dd>
          </div>
        ))}
      </dl>

      {failures.length > 0 && (
        <p className="mt-3 text-[13px]">
          <span className="font-medium">Failure categories: </span>
          {failures.map(([k, v]) => `${k.replaceAll("_", " ")} (${v})`).join(", ")}
        </p>
      )}

      <div className="mt-4 flex items-center justify-between">
        <h3 className="text-[15px] font-semibold">Cases</h3>
        <label className="flex items-center gap-2 text-[13px]">
          <input
            type="checkbox"
            className="size-4 accent-primary"
            checked={onlyFailures}
            onChange={(e) => setOnlyFailures(e.target.checked)}
          />
          Only failures
        </label>
      </div>
      <div className="mt-2 grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
        <div className="relative max-h-[560px] overflow-auto rounded-lg border">
          <table className="w-full text-[13px]">
            <caption className="sr-only">Per-case results</caption>
            <thead className="sticky top-0 bg-card">
              <tr className="border-b text-left text-muted-foreground">
                <th className="px-3 py-2 font-medium">Case</th>
                <th className="py-2 font-medium">Question</th>
                <th className="py-2 text-right font-medium">Recall</th>
                <th className="px-3 py-2 text-right font-medium">Result</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r) => (
                <tr
                  key={r.caseId}
                  className="cursor-pointer border-b last:border-0 hover:bg-muted/40 aria-selected:bg-accent"
                  aria-selected={r.caseId === caseId}
                  onClick={() => setCaseId(r.caseId)}
                >
                  <td className="px-3 py-2 font-mono">{r.externalId}</td>
                  <td className="py-2">
                    <button
                      type="button"
                      className="text-left hover:underline"
                      onClick={() => setCaseId(r.caseId)}
                    >
                      {r.question}
                    </button>
                  </td>
                  <td className="py-2 text-right font-mono tabular-nums">
                    {typeof r.metrics.recall_at_k === "number"
                      ? r.metrics.recall_at_k.toFixed(2)
                      : "—"}
                  </td>
                  <td className="px-3 py-2 text-right">
                    {r.failureCategory ? (
                      <span className="inline-flex items-center gap-1 text-danger">
                        <CircleX aria-hidden="true" className="size-3.5" />
                        <span className="sr-only">Failed:</span>
                        {r.failureCategory.replaceAll("_", " ")}
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-success">
                        <CheckCircle2 aria-hidden="true" className="size-3.5" />
                        ok
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {selected ? (
          <CaseInspector result={selected} />
        ) : (
          <p className="rounded-lg border border-dashed p-6 text-center text-muted-foreground">
            Select a case to compare its expected evidence with what was retrieved.
          </p>
        )}
      </div>
    </section>
  );
}
