import { requestJson } from "./client";
import { arr, bool, int, nullableInt, nullableStr, obj, oneOf, str } from "./validate";

export interface InstalledModel {
  name: string;
  digest: string;
  sizeBytes: number;
  family: string | null;
  parameterSize: string | null;
  quantization: string | null;
  kind: "generation" | "embedding" | "unknown";
}

export interface ModelSettings {
  runtime: { reachable: boolean; version: string | null; baseUrl: string; error: string | null };
  installed: InstalledModel[];
  generationModel: string;
  embeddingModel: string;
  reranker: { enabled: boolean; available: boolean; model: string; note: string };
  activeEmbedding: { model: string; digest: string; dimension: number; createdAt: string } | null;
  documentsNeedingReindex: number;
  setupCommands: string[];
}

export interface ValidationCheck {
  name: string;
  state: "ok" | "failed" | "skipped";
  detail: string;
  latencyMs: number | null;
}

export interface ValidationResult {
  ok: boolean;
  checks: ValidationCheck[];
  embeddingDimension: number | null;
  embeddingModelChanged: boolean;
}

export function parseModelSettings(raw: unknown): ModelSettings {
  const o = obj(raw, "settings");
  const rt = obj(o.runtime, "runtime");
  const rr = obj(o.reranker, "reranker");
  const ae = o.active_embedding ? obj(o.active_embedding, "active_embedding") : null;
  return {
    runtime: {
      reachable: bool(rt, "reachable", "runtime"),
      version: nullableStr(rt, "version", "runtime"),
      baseUrl: str(rt, "base_url", "runtime"),
      error: nullableStr(rt, "error", "runtime"),
    },
    installed: arr(o, "installed", "settings", (m, p) => {
      const mo = obj(m, p);
      return {
        name: str(mo, "name", p),
        digest: str(mo, "digest", p),
        sizeBytes: int(mo, "size_bytes", p),
        family: nullableStr(mo, "family", p),
        parameterSize: nullableStr(mo, "parameter_size", p),
        quantization: nullableStr(mo, "quantization", p),
        kind: oneOf(mo, "kind", ["generation", "embedding", "unknown"] as const, p),
      };
    }),
    generationModel: str(o, "generation_model", "settings"),
    embeddingModel: str(o, "embedding_model", "settings"),
    reranker: {
      enabled: bool(rr, "enabled", "reranker"),
      available: bool(rr, "available", "reranker"),
      model: str(rr, "model", "reranker"),
      note: str(rr, "note", "reranker"),
    },
    activeEmbedding: ae
      ? {
          model: str(ae, "model", "active_embedding"),
          digest: str(ae, "digest", "active_embedding"),
          dimension: int(ae, "dimension", "active_embedding"),
          createdAt: str(ae, "created_at", "active_embedding"),
        }
      : null,
    documentsNeedingReindex: int(o, "documents_needing_reindex", "settings"),
    setupCommands: arr(o, "setup_commands", "settings", (c, p) => {
      if (typeof c !== "string") throw new Error(p);
      return c;
    }),
  };
}

export function parseValidation(raw: unknown): ValidationResult {
  const o = obj(raw, "validation");
  return {
    ok: bool(o, "ok", "validation"),
    checks: arr(o, "checks", "validation", (c, p) => {
      const co = obj(c, p);
      return {
        name: str(co, "name", p),
        state: oneOf(co, "state", ["ok", "failed", "skipped"] as const, p),
        detail: str(co, "detail", p),
        latencyMs: nullableInt(co, "latency_ms", p),
      };
    }),
    embeddingDimension: nullableInt(o, "embedding_dimension", "validation"),
    embeddingModelChanged: bool(o, "embedding_model_changed", "validation"),
  };
}

export interface Selection {
  generationModel: string;
  embeddingModel: string;
}

const body = (s: Selection) => ({
  generation_model: s.generationModel,
  embedding_model: s.embeddingModel,
});

export async function fetchModelSettings(signal?: AbortSignal) {
  return (await requestJson("/api/v1/settings/models", parseModelSettings, { signal })).data;
}

export async function validateModels(selection: Selection, probeGeneration: boolean) {
  return (
    await requestJson("/api/v1/settings/models/validate", parseValidation, {
      method: "POST",
      json: { ...body(selection), probe_generation: probeGeneration },
      // Loading a 4B model on CPU can take a minute the first time.
      timeoutMs: 300_000,
    })
  ).data;
}

export async function saveModels(selection: Selection, rerankerEnabled: boolean) {
  return (
    await requestJson(
      "/api/v1/settings/models",
      (raw) => {
        const o = obj(raw, "save");
        return {
          settings: parseModelSettings(o.settings),
          reembedRequired: bool(o, "reembed_required", "save"),
        };
      },
      {
        method: "PUT",
        json: { ...body(selection), reranker_enabled: rerankerEnabled },
        timeoutMs: 120_000,
      },
    )
  ).data;
}

export async function reindexAll() {
  return (
    await requestJson("/api/v1/settings/reindex", (raw) => int(obj(raw, "r"), "queued", "r"), {
      method: "POST",
    })
  ).data;
}
