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
    expect(screen.getByRole("link", { name: "Ask KnowFlow" })).toHaveAttribute("href", "/ask");
    expect(screen.getByRole("link", { name: "SQL Analyst" })).toHaveAttribute("href", "/sql");
    // Every page now exists: no item is disabled.
    for (const name of ["Activity", "Help", "Models & Settings", "Evaluation Lab"]) {
      expect(screen.getByRole("link", { name })).toHaveAttribute("href");
    }
    expect(document.querySelector("[aria-disabled=true]")).toBeNull();
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
