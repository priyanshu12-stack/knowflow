import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TooltipProvider } from "@/components/ui/tooltip";

import { pageTitle } from "./nav-items";
import { SidebarNav } from "./sidebar-nav";

vi.mock("next/navigation", () => ({ usePathname: () => "/" }));

describe("SidebarNav", () => {
  it("marks the current page and links only to pages that exist", () => {
    render(
      <TooltipProvider>
        <SidebarNav />
      </TooltipProvider>,
    );
    const overview = screen.getByRole("link", { name: "Overview" });
    expect(overview).toHaveAttribute("aria-current", "page");
    expect(overview).toHaveAttribute("href", "/");

    const library = screen.getByRole("link", { name: "Knowledge Library" });
    expect(library).toHaveAttribute("href", "/library");
    expect(library).not.toHaveAttribute("aria-current");

    // Unbuilt pages are disabled with an explanation, never a dead link (DRD §13, §15).
    const ask = screen.getByRole("link", { name: /Ask KnowFlow/ });
    expect(ask).toHaveAttribute("aria-disabled", "true");
    expect(ask).not.toHaveAttribute("href");
    expect(ask).toHaveTextContent("ships in milestone M4");
  });
});

describe("pageTitle", () => {
  it.each([
    ["/", "Overview"],
    ["/library/abc", "Knowledge Library"],
    ["/unknown", "KnowFlow"],
  ])("%s → %s", (path, title) => {
    expect(pageTitle(path)).toBe(title);
  });
});
