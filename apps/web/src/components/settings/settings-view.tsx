"use client";

import { AlertTriangle, CheckCircle2, CircleX, Loader2, MinusCircle, RotateCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { CopyCommand } from "@/components/ui/copy-command";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/ui/status-badge";
import { useSystemStatus } from "@/components/system-status/system-status-provider";
import { ApiError } from "@/lib/api/client";
import { formatBytes } from "@/lib/api/documents";
import {
  fetchModelSettings,
  reindexAll,
  saveModels,
  validateModels,
  type ModelSettings,
  type ValidationResult,
} from "@/lib/api/settings";

type State =
  | { kind: "loading" }
  | { kind: "error"; error: ApiError }
  | { kind: "loaded"; data: ModelSettings };

const CHECK_LABEL: Record<string, string> = {
  runtime: "Ollama runtime",
  embedding_model: "Embedding model",
  generation_model: "Generation model",
};

function asApiError(err: unknown) {
  return err instanceof ApiError
    ? err
    : new ApiError("unexpected", "Something went wrong.", null, null);
}

function Section({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  const id = title.toLowerCase().replace(/\W+/g, "-");
  return (
    <section aria-labelledby={id} className="rounded-xl border bg-card px-5 py-5">
      <h2 id={id} className="text-[18px] font-semibold tracking-tight">
        {title}
      </h2>
      {description && (
        <p className="mt-1 max-w-prose text-[14px] text-muted-foreground">{description}</p>
      )}
      <div className="mt-4">{children}</div>
    </section>
  );
}

function ModelSelect({
  id,
  label,
  value,
  options,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
}) {
  const all = options.includes(value) ? options : [value, ...options];
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-9 rounded-lg border bg-background px-3 font-mono text-[13px] focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
      >
        {all.map((m) => (
          <option key={m} value={m}>
            {m}
            {!options.includes(m) ? " (not installed)" : ""}
          </option>
        ))}
      </select>
    </div>
  );
}

function CheckIcon({ state }: { state: "ok" | "failed" | "skipped" }) {
  if (state === "ok") return <CheckCircle2 aria-hidden="true" className="size-4 text-success" />;
  if (state === "failed") return <CircleX aria-hidden="true" className="size-4 text-danger" />;
  return <MinusCircle aria-hidden="true" className="size-4 text-muted-foreground" />;
}

/** DRD §7.6 Models & Settings: local runtime only, no provider cards or API-key fields. */
export function SettingsView() {
  const [state, setState] = useState<State>({ kind: "loading" });
  const [generation, setGeneration] = useState("");
  const [embedding, setEmbedding] = useState("");
  const [reranker, setReranker] = useState(false);
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [busy, setBusy] = useState<"validate" | "save" | "reindex" | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const { recheck } = useSystemStatus();

  useEffect(() => {
    const ctrl = new AbortController();
    fetchModelSettings(ctrl.signal).then(
      (data) => {
        setState({ kind: "loaded", data });
        setGeneration(data.generationModel);
        setEmbedding(data.embeddingModel);
        setReranker(data.reranker.enabled);
      },
      (err: unknown) => !ctrl.signal.aborted && setState({ kind: "error", error: asApiError(err) }),
    );
    return () => ctrl.abort();
  }, [reloadKey]);

  const reload = useCallback(() => setReloadKey((k) => k + 1), []);

  if (state.kind === "loading") {
    return (
      <div className="flex flex-col gap-4" aria-label="Loading model settings">
        <Skeleton className="h-28 w-full" />
        <Skeleton className="h-56 w-full" />
      </div>
    );
  }
  if (state.kind === "error") {
    return (
      <div role="alert" className="rounded-xl border bg-card p-5">
        <StatusBadge tone="danger">Settings unavailable</StatusBadge>
        <p className="mt-2 text-muted-foreground">{state.error.message}</p>
        <Button className="mt-4" variant="outline" size="sm" onClick={reload}>
          <RotateCw aria-hidden="true" />
          Try again
        </Button>
      </div>
    );
  }

  const data = state.data;
  const generationOptions = data.installed.filter((m) => m.kind !== "embedding").map((m) => m.name);
  const embeddingOptions = data.installed.filter((m) => m.kind !== "generation").map((m) => m.name);
  const selection = { generationModel: generation, embeddingModel: embedding };
  const embeddingChanged =
    data.activeEmbedding !== null && embedding !== data.activeEmbedding.model;
  const dirty =
    generation !== data.generationModel ||
    embedding !== data.embeddingModel ||
    reranker !== data.reranker.enabled;

  const run = async (probeGeneration: boolean) => {
    setBusy("validate");
    try {
      setValidation(await validateModels(selection, probeGeneration));
    } catch (err) {
      toast.error(asApiError(err).message);
    } finally {
      setBusy(null);
    }
  };

  const save = async () => {
    setBusy("save");
    try {
      const res = await saveModels(selection, reranker);
      setState({ kind: "loaded", data: res.settings });
      setValidation(null);
      recheck();
      toast.success(
        res.reembedRequired
          ? "Saved. Existing documents must be re-indexed with the new embedding model."
          : "Model settings saved.",
      );
    } catch (err) {
      toast.error(asApiError(err).message);
    } finally {
      setBusy(null);
    }
  };

  const reindex = async () => {
    setBusy("reindex");
    try {
      const queued = await reindexAll();
      toast.success(`Queued ${queued} document${queued === 1 ? "" : "s"} for re-indexing.`);
      reload();
    } catch (err) {
      toast.error(asApiError(err).message);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-[26px] leading-tight font-semibold tracking-tight">
          Models &amp; Settings
        </h1>
        <p className="mt-1 max-w-prose text-[15px] text-muted-foreground">
          KnowFlow only uses models running on this machine through Ollama. Nothing is sent to a
          hosted provider and no API key is needed.
        </p>
      </header>

      <Section title="Local runtime">
        <div className="flex flex-wrap items-center gap-3">
          {data.runtime.reachable ? (
            <StatusBadge tone="ok">Ollama {data.runtime.version}</StatusBadge>
          ) : (
            <StatusBadge tone="danger">Ollama unreachable</StatusBadge>
          )}
          <span className="font-mono text-[13px] text-muted-foreground">
            {data.runtime.baseUrl}
          </span>
        </div>
        {!data.runtime.reachable && (
          <>
            <p className="mt-2">{data.runtime.error}</p>
            <CopyCommand command="ollama serve" />
          </>
        )}
        {data.installed.length > 0 && (
          <div className="relative mt-4 overflow-x-auto">
            <table className="w-full min-w-[560px] text-[14px]">
              <caption className="sr-only">Installed local models</caption>
              <thead>
                <tr className="border-b text-left text-[13px] text-muted-foreground">
                  <th className="py-2 font-medium">Model</th>
                  <th className="py-2 font-medium">Role</th>
                  <th className="py-2 font-medium">Size</th>
                  <th className="py-2 font-medium">Parameters</th>
                  <th className="py-2 font-medium">Quantization</th>
                </tr>
              </thead>
              <tbody>
                {data.installed.map((m) => (
                  <tr key={m.name} className="border-b last:border-0">
                    <td className="py-2 font-mono text-[13px]">{m.name}</td>
                    <td className="py-2 capitalize">{m.kind}</td>
                    <td className="py-2 tabular-nums">{formatBytes(m.sizeBytes)}</td>
                    <td className="py-2">{m.parameterSize ?? "—"}</td>
                    <td className="py-2">{m.quantization ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data.setupCommands.length > 0 && (
          <div className="mt-4">
            <p className="text-[14px] font-medium">Setup commands</p>
            {data.setupCommands.map((c) => (
              <CopyCommand key={c} command={c} />
            ))}
          </div>
        )}
      </Section>

      <Section
        title="Model selection"
        description="Choose from models installed locally. Validate before saving: KnowFlow calls each model once to check it works."
      >
        <div className="grid gap-4 md:grid-cols-2">
          <ModelSelect
            id="generation-model"
            label="Generation model (answers, SQL)"
            value={generation}
            options={generationOptions}
            onChange={(v) => {
              setGeneration(v);
              setValidation(null);
            }}
          />
          <ModelSelect
            id="embedding-model"
            label="Embedding model (indexing, search)"
            value={embedding}
            options={embeddingOptions}
            onChange={(v) => {
              setEmbedding(v);
              setValidation(null);
            }}
          />
        </div>

        {embeddingChanged && (
          <div role="alert" className="mt-4 flex gap-2.5 rounded-lg border border-warning/40 p-3">
            <AlertTriangle aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-warning" />
            <p className="text-[14px]">
              Changing the embedding model makes every existing vector unusable. After saving, all
              documents must be re-indexed before semantic search works again.
            </p>
          </div>
        )}

        <div className="mt-4 rounded-lg border p-3">
          <div className="flex items-start gap-3">
            <input
              id="reranker"
              type="checkbox"
              className="mt-1 size-4 accent-primary"
              checked={reranker}
              disabled={!data.reranker.available}
              onChange={(e) => setReranker(e.target.checked)}
            />
            <div>
              <Label htmlFor="reranker">Reranker ({data.reranker.model})</Label>
              <p className="text-[13px] text-muted-foreground">{data.reranker.note}</p>
            </div>
          </div>
        </div>

        <div className="mt-5 flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => void run(true)} disabled={busy !== null}>
            {busy === "validate" && <Loader2 aria-hidden="true" className="animate-spin" />}
            Validate configuration
          </Button>
          <Button variant="ghost" onClick={() => void run(false)} disabled={busy !== null}>
            Quick check (skip generation)
          </Button>
          <Button onClick={() => void save()} disabled={busy !== null || !dirty}>
            {busy === "save" && <Loader2 aria-hidden="true" className="animate-spin" />}
            Save
          </Button>
        </div>
        {busy === "validate" && (
          <p className="mt-2 text-[13px] text-muted-foreground" role="status">
            Calling the models… the first call loads the model into memory and can take a minute on
            CPU.
          </p>
        )}

        {validation && (
          <div className="mt-4" aria-live="polite">
            <StatusBadge tone={validation.ok ? "ok" : "danger"}>
              {validation.ok ? "Configuration works" : "Configuration has problems"}
            </StatusBadge>
            <ul className="mt-2 divide-y rounded-lg border">
              {validation.checks.map((c) => (
                <li key={c.name} className="flex items-start gap-2.5 px-3 py-2 text-[14px]">
                  <span className="mt-0.5">
                    <CheckIcon state={c.state} />
                  </span>
                  <span className="flex-1">
                    <span className="font-medium">{CHECK_LABEL[c.name] ?? c.name}: </span>
                    {c.detail}
                  </span>
                  {c.latencyMs !== null && (
                    <span className="font-mono text-[12px] text-muted-foreground tabular-nums">
                      {c.latencyMs} ms
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
      </Section>

      <Section
        title="Embedding index"
        description="Vectors from different embedding models are never mixed. The active embedding space is recorded with its measured dimension."
      >
        {data.activeEmbedding ? (
          <dl className="grid gap-x-8 gap-y-1 text-[14px] sm:grid-cols-[auto_1fr]">
            <dt className="text-muted-foreground">Model</dt>
            <dd className="font-mono text-[13px]">{data.activeEmbedding.model}</dd>
            <dt className="text-muted-foreground">Dimension</dt>
            <dd className="tabular-nums">{data.activeEmbedding.dimension}</dd>
            <dt className="text-muted-foreground">Digest</dt>
            <dd className="font-mono text-[12px] break-all">{data.activeEmbedding.digest}</dd>
          </dl>
        ) : (
          <p className="text-muted-foreground">
            Nothing has been embedded yet. The embedding space is created when the first document is
            indexed.
          </p>
        )}
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <p className="text-[14px] tabular-nums">
            {data.documentsNeedingReindex === 0
              ? "All ready documents use the active embedding model."
              : `${data.documentsNeedingReindex} document${data.documentsNeedingReindex === 1 ? "" : "s"} need re-indexing.`}
          </p>
          <Button
            variant={data.documentsNeedingReindex > 0 ? "default" : "outline"}
            size="sm"
            onClick={() => void reindex()}
            disabled={busy !== null}
          >
            {busy === "reindex" ? (
              <Loader2 aria-hidden="true" className="animate-spin" />
            ) : (
              <RotateCw aria-hidden="true" />
            )}
            Re-index all documents
          </Button>
        </div>
      </Section>
    </div>
  );
}
