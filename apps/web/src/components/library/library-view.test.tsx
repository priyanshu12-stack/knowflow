import { render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TooltipProvider } from "@/components/ui/tooltip";
import { RAW_DOC, RAW_POLICY } from "@/test/fixtures";

import { LibraryView } from "./library-view";

function stubApi(documents: unknown[], opts: { failDocuments?: boolean } = {}) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("upload-policy")) return Response.json(RAW_POLICY);
      if (opts.failDocuments) {
        return Response.json(
          {
            error: {
              code: "schema_not_migrated",
              message: "The database schema is not up to date.",
              request_id: "req-1",
            },
          },
          { status: 503 },
        );
      }
      const ready = url.includes("status=ready");
      const items = ready ? [] : documents;
      return Response.json({ items, total: items.length, limit: 25, offset: 0 });
    }),
  );
}

const renderView = () =>
  render(
    <TooltipProvider>
      <LibraryView />
    </TooltipProvider>,
  );

afterEach(() => vi.unstubAllGlobals());

describe("LibraryView", () => {
  it("shows an empty state with an upload action", async () => {
    stubApi([]);
    renderView();
    expect(await screen.findByText("No documents yet")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Upload your first document/ })).toBeEnabled();
    expect(screen.getByText(/0 documents · 0 indexed/)).toBeInTheDocument();
  });

  it("lists documents with their status", async () => {
    stubApi([RAW_DOC]);
    renderView();
    const row = (await screen.findByText("Leave Policy.pdf")).closest("tr")!;
    expect(within(row).getByText(/Queued/)).toBeInTheDocument();
    expect(screen.getByText(/1 document · 0 indexed/)).toBeInTheDocument();
  });

  it("shows a recoverable error with the exact fix command", async () => {
    stubApi([], { failDocuments: true });
    renderView();
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText("./scripts/dev.ps1 migrate")).toBeInTheDocument();
    expect(within(alert).getByText(/req-1/)).toBeInTheDocument();
    expect(within(alert).getByRole("button", { name: /Try again/ })).toBeInTheDocument();
  });
});
