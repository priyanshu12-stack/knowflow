import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ReadinessPanel } from "./readiness-panel";
import { SystemStatusProvider } from "./system-status-provider";

const DEGRADED = {
  status: "degraded",
  checks: [
    { name: "postgres", state: "ok", required: true, detail: "PostgreSQL 16.15" },
    { name: "ollama", state: "ok", required: true, detail: "Ollama 0.17.1" },
    {
      name: "generation_model",
      state: "missing",
      required: false,
      detail: "qwen3:4b is not installed.",
      remediation: "ollama pull qwen3:4b",
    },
  ],
};

function renderPanel() {
  return render(
    <SystemStatusProvider>
      <ReadinessPanel />
    </SystemStatusProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ReadinessPanel", () => {
  it("shows a loading state, then each dependency with its own status", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Response.json(DEGRADED)),
    );
    renderPanel();
    expect(screen.getByLabelText("Loading dependency checks")).toBeInTheDocument();

    const pg = (await screen.findByText("PostgreSQL")).closest("li")!;
    expect(within(pg).getByText("Ready")).toBeInTheDocument();

    const gen = screen.getByText("Generation model").closest("li")!;
    expect(within(gen).getByText("Needs setup")).toBeInTheDocument();
    expect(within(gen).getByText("ollama pull qwen3:4b")).toBeInTheDocument();
    expect(screen.getByText(/1 model is not installed yet/)).toBeInTheDocument();
  });

  it("reports a required dependency outage from a 503 body", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        Response.json(
          {
            status: "not_ready",
            checks: [{ name: "postgres", state: "unavailable", required: true, detail: "down" }],
          },
          { status: 503 },
        ),
      ),
    );
    renderPanel();
    expect(await screen.findByText(/PostgreSQL is unavailable/)).toBeInTheDocument();
    expect(screen.getByText("Unavailable")).toBeInTheDocument();
  });

  it("explains how to recover when the API is unreachable, and re-checks on demand", async () => {
    const fetchMock = vi.fn<() => Promise<Response>>(async () => {
      throw new TypeError("fetch failed");
    });
    vi.stubGlobal("fetch", fetchMock);
    renderPanel();

    expect(await screen.findByText("The KnowFlow API is not reachable.")).toBeInTheDocument();
    expect(screen.getByText("./scripts/dev.ps1 api")).toBeInTheDocument();

    fetchMock.mockImplementation(async () => Response.json(DEGRADED));
    await userEvent.click(screen.getByRole("button", { name: "Re-check" }));
    expect(await screen.findByText("Generation model")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
