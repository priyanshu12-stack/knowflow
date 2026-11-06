import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SqlView } from "./sql-view";

const CONN = {
  id: "c1",
  display_name: "Demo sales (synthetic)",
  db_type: "postgresql",
  host: "localhost",
  port: 5432,
  database_name: "knowflow_demo",
  username: "knowflow_reader",
  allowed_schemas: ["sales"],
  is_demo: true,
  created_at: "2026-11-07T00:00:00Z",
};

const SCHEMA = {
  connection: CONN,
  tables: [
    {
      schema_name: "sales",
      name: "customers",
      description: "Synthetic customers.",
      columns: [{ name: "name", data_type: "text", nullable: false, description: null }],
    },
  ],
  glossary: [
    {
      term: "best customer",
      kind: "ambiguous",
      definition: null,
      synonyms: [],
      options: [
        { id: "paid_revenue", label: "Highest paid revenue", definition: "SUM(payments.amount)" },
        { id: "order_count", label: "Most orders", definition: "COUNT(paid orders)" },
      ],
    },
  ],
  max_rows: 500,
  statement_timeout_ms: 5000,
};

const CLARIFY = {
  query_id: "q1",
  status: "clarification_required",
  question: "Show me our best customers last month.",
  clarification: {
    term: "best customer",
    question: "What should “best customer” mean for this question?",
    options: SCHEMA.glossary[0].options,
    source: "glossary",
  },
  sql: null,
  explanation: null,
  assumptions: [],
  definitions_used: [],
  tables: [],
  columns: [],
  rows: [],
  row_count: null,
  truncated: false,
  duration_ms: null,
  generation_ms: null,
  message: null,
  repairable: false,
  model: "qwen3:4b",
  prompt_version: "sql-v3",
  read_only: true,
  database: "knowflow_demo",
};

const EXECUTED = {
  ...CLARIFY,
  query_id: "q2",
  status: "executed",
  clarification: null,
  sql: "SELECT c.name, SUM(p.amount) AS net_revenue FROM sales.customers AS c LIMIT 501",
  explanation: "Ranks customers by net paid revenue in October 2026.",
  assumptions: ["Last month is October 2026."],
  definitions_used: [{ term: "best customer", definition: "SUM(payments.amount)" }],
  columns: ["name", "net_revenue"],
  rows: [
    ["Gita Dubois", 7020],
    ["Fjord Studio", 4206],
  ],
  row_count: 2,
  duration_ms: 41,
  generation_ms: 68969,
};

function stub(answers: unknown[], connections: unknown[] = [CONN]) {
  const queue = [...answers];
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    void init;
    if (url.endsWith("/sql/connections")) return Response.json(connections);
    if (url.includes("/sql/schema/")) return Response.json(SCHEMA);
    if (url.endsWith("/sql/query")) return Response.json(queue.shift());
    return Response.json({});
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => vi.unstubAllGlobals());

describe("SqlView", () => {
  it("shows the allowed schema, read-only badge and glossary", async () => {
    stub([]);
    render(<SqlView />);
    expect(await screen.findByText("sales.customers")).toBeInTheDocument();
    expect(screen.getByText("Read-only")).toBeInTheDocument();
    expect(screen.getByText("best customer")).toBeInTheDocument();
    expect(screen.getByText(/At most 500 rows/)).toBeInTheDocument();
  });

  it("Journey C: asks for clarification, then shows SQL, interpretation and results", async () => {
    const fetchMock = stub([CLARIFY, EXECUTED]);
    render(<SqlView />);
    await userEvent.type(await screen.findByLabelText("Your question"), CLARIFY.question);
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));

    expect(await screen.findByText("Clarification needed")).toBeInTheDocument();
    expect(screen.getByText(/Nothing has been run yet/)).toBeInTheDocument();
    const confirm = screen.getByRole("button", { name: /Use this meaning/ });
    expect(confirm).toBeDisabled();
    await userEvent.click(screen.getByRole("radio", { name: /Highest paid revenue/ }));
    await userEvent.click(confirm);

    const answer = await screen.findByRole("region", { name: "Answer" });
    expect(within(answer).getByText("Ran read-only")).toBeInTheDocument();
    expect(within(answer).getByText(/Read-only SQL/)).toBeInTheDocument();
    expect(within(answer).getByText(/not a database fact/)).toBeInTheDocument();
    const table = within(answer).getByRole("table", { name: "Query results" });
    expect(within(table).getByText("Gita Dubois")).toBeInTheDocument();
    expect(within(answer).getByText(/2 rows/)).toBeInTheDocument();

    const second = fetchMock.mock.calls.filter(([u]) => String(u).endsWith("/sql/query"))[1];
    expect(JSON.parse(String(second[1]!.body)).clarification_context).toEqual([
      { term: "best customer", option_id: "paid_revenue" },
    ]);
  });

  it("sorts results by a column", async () => {
    stub([EXECUTED]);
    render(<SqlView />);
    await userEvent.type(await screen.findByLabelText("Your question"), "x");
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));
    const table = await screen.findByRole("table", { name: "Query results" });
    await userEvent.click(within(table).getByRole("button", { name: "Sort by net_revenue" }));
    const firstCell = within(table).getAllByRole("row")[1].querySelector("td");
    expect(firstCell).toHaveTextContent("Fjord Studio");
  });

  it("explains rejected SQL and offers a fix only for repairable failures", async () => {
    stub([
      {
        ...EXECUTED,
        status: "rejected",
        rows: [],
        columns: [],
        message: "The generated SQL was rejected and not run: DELETE is not allowed.",
      },
      {
        ...EXECUTED,
        status: "failed",
        rows: [],
        columns: [],
        message: 'column "nmae" does not exist',
        repairable: true,
      },
    ]);
    render(<SqlView />);
    await userEvent.type(await screen.findByLabelText("Your question"), "x");
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));
    expect(await screen.findByText("Rejected, not run")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /fix this query/ })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));
    expect(await screen.findByText("Query failed")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /fix this query/ })).toBeInTheDocument();
  });

  it("tells the user how to set up the demo database when it's missing", async () => {
    stub([], []);
    render(<SqlView />);
    expect(await screen.findByText("Demo database not set up")).toBeInTheDocument();
    expect(screen.getByText("./scripts/dev.ps1 seed-demo")).toBeInTheDocument();
  });
});
