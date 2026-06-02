import { chromium } from "playwright";
const BASE = "http://localhost:3000";
const API = "http://localhost:8000";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const EMAIL = process.env.AUDIT_EMAIL;
const PASS = process.env.AUDIT_PASS;

const PAGES = [
  "/dashboard", "/history", "/patients", "/analytics",
  "/admin", "/admin/audit-logs", "/settings",
];

async function auditPages(page, label) {
  console.log(`\n########## ${label} ##########`);
  for (const path of PAGES) {
    const errs = [];
    const pageErrs = [];
    const bad = [];
    const onConsole = (m) => { if (m.type() === "error") errs.push(m.text()); };
    const onPageErr = (e) => pageErrs.push(e.message);
    const onResp = (r) => { if (r.status() >= 400 && r.url().includes("/api/")) bad.push(`${r.status()} ${r.url().replace(API,"")}`); };
    page.on("console", onConsole);
    page.on("pageerror", onPageErr);
    page.on("response", onResp);

    await page.goto(`${BASE}${path}`, { waitUntil: "networkidle", timeout: 30000 }).catch(() => {});
    await sleep(1800);

    const info = await page.evaluate(() => {
      const bg = getComputedStyle(document.body).backgroundColor;
      const txt = document.body.innerText.trim();
      return {
        url: location.pathname,
        bg,
        theme: document.documentElement.className,
        contentLen: txt.length,
        snippet: txt.slice(0, 60).replace(/\n/g, " "),
        hasSkeleton: !!document.querySelector(".skeleton"),
      };
    });

    page.off("console", onConsole);
    page.off("pageerror", onPageErr);
    page.off("response", onResp);

    const status = (pageErrs.length || errs.length) ? "ISSUES" : "clean";
    console.log(`\n  [${status}] ${path}  -> ${info.url}`);
    console.log(`     bg=${info.bg} theme=${info.theme} contentLen=${info.contentLen}`);
    console.log(`     "${info.snippet}"`);
    if (pageErrs.length) pageErrs.slice(0,4).forEach((e) => console.log(`     ! RUNTIME: ${e.slice(0,140)}`));
    if (errs.length) errs.slice(0,4).forEach((e) => console.log(`     - console: ${e.slice(0,140)}`));
    if (bad.length) bad.slice(0,4).forEach((b) => console.log(`     > api: ${b.slice(0,140)}`));
  }
}

const run = async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext();
  const page = await ctx.newPage();

  // Log in through the UI
  await page.goto(`${BASE}/auth/signin`, { waitUntil: "networkidle" });
  await sleep(800);
  const inputs = page.locator("input");
  await inputs.nth(0).fill(EMAIL);
  await inputs.nth(1).fill(PASS);
  await page.click('button[type="submit"]');
  await page.waitForURL("**/dashboard", { timeout: 15000 }).catch(() => {});
  await sleep(1500);
  console.log("Logged in, URL:", page.url());
  const tokenSet = await page.evaluate(() => !!localStorage.getItem("access_token"));
  console.log("access_token in localStorage:", tokenSet);

  // Audit all pages in current (dark default) theme
  await page.evaluate(() => localStorage.removeItem("theme"));
  await auditPages(page, "AUTHENTICATED PAGES — DEFAULT (dark) THEME");

  // Now force light theme and re-audit to scope the theme bug
  await page.evaluate(() => localStorage.setItem("theme", "light"));
  await auditPages(page, "AUTHENTICATED PAGES — LIGHT THEME");

  await browser.close();
  console.log("\n===== AUTHED AUDIT COMPLETE =====");
};
run().catch((e) => { console.error("FATAL", e); process.exit(1); });
