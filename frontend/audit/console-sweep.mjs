import { chromium } from "playwright";
const BASE = "http://localhost:3000";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const EMAIL = process.env.AUDIT_EMAIL;
const PASS = process.env.AUDIT_PASS;

const PUBLIC = ["/", "/auth/signin", "/auth/signup", "/triage/start"];
const AUTHED = ["/dashboard", "/history", "/patients", "/analytics", "/admin", "/admin/audit-logs", "/settings"];

async function sweep(page, path) {
  const errs = [];
  const warns = [];
  const onC = (m) => {
    const t = m.type();
    if (t === "error") errs.push(m.text());
    else if (t === "warning" && /hydrat|did not match|key prop|each child/i.test(m.text())) warns.push(m.text());
  };
  const onPE = (e) => errs.push("PAGEERROR: " + e.message);
  page.on("console", onC);
  page.on("pageerror", onPE);
  await page.goto(`${BASE}${path}`, { waitUntil: "networkidle", timeout: 30000 }).catch(() => {});
  await sleep(1800);
  page.off("console", onC);
  page.off("pageerror", onPE);
  // ignore benign favicon 404
  const realErrs = errs.filter((e) => !/favicon/i.test(e));
  const tag = (realErrs.length || warns.length) ? "ERRORS" : "clean";
  console.log(`  [${tag}] ${path}`);
  realErrs.forEach((e) => console.log(`      ERR: ${e.slice(0, 150)}`));
  warns.forEach((w) => console.log(`      WARN: ${w.slice(0, 150)}`));
  return realErrs.length + warns.length;
}

const run = async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  let total = 0;

  console.log("PUBLIC PAGES (no auth):");
  for (const p of PUBLIC) total += await sweep(page, p);

  // login
  await page.goto(`${BASE}/auth/signin`, { waitUntil: "networkidle" });
  await sleep(600);
  const inputs = page.locator("input");
  await inputs.nth(0).fill(EMAIL);
  await inputs.nth(1).fill(PASS);
  await page.click('button[type="submit"]');
  await page.waitForURL("**/dashboard", { timeout: 12000 }).catch(() => {});
  await sleep(1000);

  console.log("\nAUTHENTICATED PAGES:");
  for (const p of AUTHED) total += await sweep(page, p);

  await browser.close();
  console.log(`\n===== TOTAL console errors/relevant-warnings: ${total} =====`);
  process.exit(total === 0 ? 0 : 1);
};
run().catch((e) => { console.error("FATAL", e); process.exit(1); });
