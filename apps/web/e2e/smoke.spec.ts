import { expect, test } from "@playwright/test";

import { mockApi } from "./mock-api";

const PAGES: [string, string][] = [
  ["/", "Workspace overview"],
  ["/library", "Knowledge Library"],
  ["/ask", "Ask KnowFlow"],
  ["/sql", "SQL Analyst"],
  ["/evaluation", "Evaluation Lab"],
  ["/settings", "Models & Settings"],
  ["/activity", "Activity"],
  ["/help", "Help"],
];

const VIEWPORTS = [
  { name: "mobile", width: 390, height: 844 },
  { name: "tablet", width: 820, height: 1180 },
  { name: "desktop", width: 1440, height: 900 },
];

for (const vp of VIEWPORTS) {
  test.describe(`${vp.name} ${vp.width}px`, () => {
    test.use({ viewport: { width: vp.width, height: vp.height } });

    for (const [path, title] of PAGES) {
      test(`${path} renders without errors or horizontal overflow`, async ({ page }) => {
        const errors: string[] = [];
        page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
        page.on("pageerror", (e) => errors.push(e.message));
        await mockApi(page);
        await page.goto(path);
        await expect(page.getByRole("heading", { level: 1, name: title })).toBeVisible();
        await page.waitForLoadState("networkidle");
        const overflow = await page.evaluate(
          () => document.documentElement.scrollWidth - window.innerWidth,
        );
        expect(overflow, "horizontal overflow in px").toBeLessThanOrEqual(0);
        expect(errors).toEqual([]);
      });
    }
  });
}

test("unknown pages show a way back instead of a dead end", async ({ page }) => {
  await mockApi(page);
  await page.goto("/does-not-exist");
  await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();
  await page.getByRole("link", { name: "Back to overview" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Workspace overview" })).toBeVisible();
});

test("keyboard: skip link moves focus to the main content", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: "Skip to content" });
  await expect(skip).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/#main$/);
});

test("Journey A: ask, read the cited answer and open the source drawer", async ({ page }) => {
  await mockApi(page);
  await page.goto("/ask");
  const box = page.getByLabel("Your question");
  const ask = page.getByRole("button", { name: "Ask", exact: true });
  await expect(async () => {
    await box.fill("What is the hotel cap per night?");
    await expect(ask).toBeEnabled({ timeout: 1000 });
  }).toPass();
  await ask.click();
  const answer = page.getByRole("article", { name: "Answer" });
  await expect(answer).toContainText("Hotels are capped at 150 EUR per night");
  await answer
    .getByRole("button", { name: /^Source 1/ })
    .first()
    .click();
  const drawer = page.getByRole("dialog");
  await expect(drawer).toContainText("Hotels are capped at 150 EUR per night in most cities.");
  await expect(drawer.getByRole("link", { name: /Open document in Library/ })).toHaveAttribute(
    "href",
    "/library?document=d1",
  );
  await page.keyboard.press("Escape");
  await expect(drawer).toBeHidden();
});

test("navigation reaches every page from the sidebar", async ({ page }) => {
  await mockApi(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  for (const [path, title] of PAGES.slice(1)) {
    await page.getByRole("navigation").getByRole("link", { name: title }).first().click();
    await expect(page).toHaveURL(new RegExp(`${path}$`));
    await expect(page.getByRole("heading", { level: 1, name: title })).toBeVisible();
  }
});
