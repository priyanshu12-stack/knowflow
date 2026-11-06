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

    // Unbuilt pages are disabled with an explanation, never a dead link (DRD §13, §15).
    const library = screen.getByRole("link", { name: /Knowledge Library/ });
    expect(library).toHaveAttribute("aria-disabled", "true");
    expect(library).not.toHaveAttribute("href");
    expect(library).toHaveTextContent("ships in milestone M1");
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
