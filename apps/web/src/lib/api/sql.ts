import { requestJson } from "./client";
import { arr, bool, int, nullableStr, obj, str } from "./validate";

export interface SqlConnection {
  id: string;
  displayName: string;
  host: string;
  port: number;
  databaseName: string;
  username: string;
  allowedSchemas: string[];
  isDemo: boolean;
}

export interface SqlColumn {
  name: string;
  dataType: string;
  nullable: boolean;
  description: string | null;
}

export interface SqlTable {
  schema: string;
  name: string;
  description: string | null;
  columns: SqlColumn[];
}

export interface GlossaryOption {
  id: string;
  label: string;
  definition: string;
}

export interface GlossaryTerm {
  term: string;
  kind: "definition" | "ambiguous";
  definition: string | null;
  synonyms: string[];
  options: GlossaryOption[];
}

export interface SchemaInfo {
  tables: SqlTable[];
  glossary: GlossaryTerm[];
  maxRows: number;
  statementTimeoutMs: number;
}

export type SqlStatus =
  "clarification_required" | "executed" | "rejected" | "failed" | "unsupported";

export interface SqlAnswer {
  queryId: string;
  status: SqlStatus;
  question: string;
  clarification: {
    term: string;
    question: string;
    options: GlossaryOption[];
    source: "glossary" | "model";
  } | null;
  sql: string | null;
  explanation: string | null;
  assumptions: string[];
  definitionsUsed: { term: string; definition: string }[];
  columns: string[];
  rows: unknown[][];
  rowCount: number | null;
  truncated: boolean;
  durationMs: number | null;
  generationMs: number | null;
  message: string | null;
  repairable: boolean;
  model: string | null;
  database: string | null;
}

export interface Choice {
  term: string;
  option_id?: string;
  custom_definition?: string;
}

const STATUSES = [
  "clarification_required",
  "executed",
  "rejected",
  "failed",
  "unsupported",
] as const;

function parseOption(raw: unknown, p: string): GlossaryOption {
  const o = obj(raw, p);
  return { id: str(o, "id", p), label: str(o, "label", p), definition: str(o, "definition", p) };
}

function parseConnection(raw: unknown, p = "connection"): SqlConnection {
  const o = obj(raw, p);
  return {
    id: str(o, "id", p),
    displayName: str(o, "display_name", p),
    host: str(o, "host", p),
    port: int(o, "port", p),
    databaseName: str(o, "database_name", p),
    username: str(o, "username", p),
    allowedSchemas: arr(o, "allowed_schemas", p, (x) => String(x)),
    isDemo: bool(o, "is_demo", p),
  };
}

export function parseSchema(raw: unknown): SchemaInfo {
  const o = obj(raw, "schema");
  return {
    tables: arr(o, "tables", "schema", (t, p) => {
      const to = obj(t, p);
      return {
        schema: str(to, "schema_name", p),
        name: str(to, "name", p),
        description: nullableStr(to, "description", p),
        columns: arr(to, "columns", p, (c, cp) => {
          const co = obj(c, cp);
          return {
            name: str(co, "name", cp),
            dataType: str(co, "data_type", cp),
            nullable: bool(co, "nullable", cp),
            description: nullableStr(co, "description", cp),
          };
        }),
      };
    }),
    glossary: arr(o, "glossary", "schema", (g, p) => {
      const go = obj(g, p);
      return {
        term: str(go, "term", p),
        kind: str(go, "kind", p) === "ambiguous" ? "ambiguous" : "definition",
        definition: nullableStr(go, "definition", p),
        synonyms: arr(go, "synonyms", p, (x) => String(x)),
        options: arr(go, "options", p, parseOption),
      };
    }),
    maxRows: int(o, "max_rows", "schema"),
    statementTimeoutMs: int(o, "statement_timeout_ms", "schema"),
  };
}

export function parseAnswer(raw: unknown): SqlAnswer {
  const o = obj(raw, "sql");
  const status = str(o, "status", "sql");
  const c = o.clarification ? obj(o.clarification, "clarification") : null;
  return {
    queryId: str(o, "query_id", "sql"),
    status: (STATUSES as readonly string[]).includes(status) ? (status as SqlStatus) : "failed",
    question: str(o, "question", "sql"),
    clarification: c
      ? {
          term: str(c, "term", "clarification"),
          question: str(c, "question", "clarification"),
          options: arr(c, "options", "clarification", parseOption),
          source: str(c, "source", "clarification") === "model" ? "model" : "glossary",
        }
      : null,
    sql: nullableStr(o, "sql", "sql"),
    explanation: nullableStr(o, "explanation", "sql"),
    assumptions: arr(o, "assumptions", "sql", (x) => String(x)),
    definitionsUsed: arr(o, "definitions_used", "sql", (d, p) => {
      const dobj = obj(d, p);
      return { term: str(dobj, "term", p), definition: str(dobj, "definition", p) };
    }),
    columns: arr(o, "columns", "sql", (x) => String(x)),
    rows: Array.isArray(o.rows) ? (o.rows as unknown[][]) : [],
    rowCount: typeof o.row_count === "number" ? o.row_count : null,
    truncated: o.truncated === true,
    durationMs: typeof o.duration_ms === "number" ? o.duration_ms : null,
    generationMs: typeof o.generation_ms === "number" ? o.generation_ms : null,
    message: nullableStr(o, "message", "sql"),
    repairable: o.repairable === true,
    model: nullableStr(o, "model", "sql"),
    database: nullableStr(o, "database", "sql"),
  };
}

export async function fetchConnections(signal?: AbortSignal) {
  return (
    await requestJson(
      "/api/v1/sql/connections",
      (raw) =>
        Array.isArray(raw) ? raw.map((c, i) => parseConnection(c, `connections[${i}]`)) : [],
      { signal, timeoutMs: 15_000 },
    )
  ).data;
}

export async function fetchSchema(id: string, signal?: AbortSignal) {
  return (
    await requestJson(`/api/v1/sql/schema/${encodeURIComponent(id)}`, parseSchema, {
      signal,
      timeoutMs: 15_000,
    })
  ).data;
}

export async function askSql(
  body: {
    connectionId: string;
    question: string;
    choices: Choice[];
    repair?: { sql: string; error: string } | null;
  },
  signal?: AbortSignal,
) {
  return (
    await requestJson("/api/v1/sql/query", parseAnswer, {
      method: "POST",
      json: {
        connection_id: body.connectionId,
        question: body.question,
        clarification_context: body.choices,
        repair: body.repair ?? null,
      },
      timeoutMs: 600_000,
      signal,
    })
  ).data;
}

export async function addConnection(body: {
  display_name: string;
  host: string;
  port: number;
  database_name: string;
  username: string;
  password: string;
  allowed_schemas: string[];
}) {
  return (
    await requestJson("/api/v1/sql/connections/test", (r) => parseConnection(r), {
      method: "POST",
      json: body,
      timeoutMs: 30_000,
    })
  ).data;
}

export async function removeConnection(id: string) {
  await requestJson(`/api/v1/sql/connections/${encodeURIComponent(id)}`, () => undefined, {
    method: "DELETE",
  });
}
