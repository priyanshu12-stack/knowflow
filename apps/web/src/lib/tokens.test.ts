/**
 * DES-01 / DES-14: tokens match DRD §2 exactly, and the colour pairs we actually use
 * meet WCAG 2.2 AA (4.5:1 text, 3:1 non-text icons).
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const css = readFileSync(join(__dirname, "../app/globals.css"), "utf8");

function token(name: string): string {
  const m = css.match(new RegExp(`--kf-${name}:\\s*(#[0-9a-fA-F]{6})`));
  if (!m) throw new Error(`token --kf-${name} not found`);
  return m[1].toLowerCase();
}

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

describe("DRD §2 tokens", () => {
  it.each([
    ["canvas", "#f6f5f1"],
    ["surface", "#ffffff"],
    ["ink", "#202b33"],
    ["ink-secondary", "#65717a"],
    ["teal", "#245b57"],
    ["teal-tint", "#e8f0ed"],
    ["border", "#e3e6e3"],
    ["success", "#287a55"],
    ["warning", "#a66a1f"],
    ["danger", "#b54742"],
    ["info", "#496d8c"],
  ])("--kf-%s is %s", (name, value) => {
    expect(token(name)).toBe(value);
  });

  it("uses no gradients (DRD §2, §15)", () => {
    expect(css).not.toMatch(/gradient\(/);
  });
});

describe("WCAG AA contrast for pairs used in the UI", () => {
  const backgrounds = ["surface", "canvas"] as const;

  it.each(backgrounds)("body and secondary text on %s ≥ 4.5:1", (bg) => {
    expect(contrast(token("ink"), token(bg))).toBeGreaterThanOrEqual(4.5);
    expect(contrast(token("ink-secondary"), token(bg))).toBeGreaterThanOrEqual(4.5);
  });

  it("teal text on surface, canvas and active-nav tint ≥ 4.5:1", () => {
    for (const bg of ["surface", "canvas", "teal-tint"]) {
      expect(contrast(token("teal"), token(bg))).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("white on primary teal ≥ 4.5:1", () => {
    expect(contrast("#ffffff", token("teal"))).toBeGreaterThanOrEqual(4.5);
  });

  // Status colours are used for icons only; labels stay in ink (see docs/design-system.md).
  it.each(["success", "warning", "danger", "info"])("%s icon on surface/canvas ≥ 3:1", (c) => {
    for (const bg of backgrounds) {
      expect(contrast(token(c), token(bg))).toBeGreaterThanOrEqual(3);
    }
  });
});
