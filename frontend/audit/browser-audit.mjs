import { chromium } from "playwright";

const BASE = "http://localhost:3000";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function attach(page, bucket) {
  page.on("console", (msg) => {
    const t = msg.type();
    if (t === "error" || t === "warning") {
      bucket.console.push(`[${t}] ${msg.text()}`);
    }
  });
  page.on("pageerror", (err) => bucket.pageErrors.push(err.message));
  page.on("requestfailed", (req) => {
    const f = req.failure();
    bucket.failedReq.push(`${req.method()} ${req.url()} — ${f ? f.errorText : "?"}`);
  });
  page.on("response", (resp) => {
    if (resp.status() >= 400) {
      bucket.badResp.push(`${resp.status()} ${resp.request().method()} ${resp.url()}`);
    }
  });
}

function newBucket() {
  return { console: [], pageErrors: [], failedReq: [], badResp: [] };
}

function report(label, b) {
  console.log(`\n===== ${label} =====`);
  console.log(`  console errors/warnings: ${b.console.length}`);
  b.console.slice(0, 15).forEach((x) => console.log(`    - ${x.slice(0, 160)}`));
  console.log(`  page (runtime) errors  : ${b.pageErrors.length}`);
  b.pageErrors.slice(0, 15).forEach((x) => console.log(`    ! ${x.slice(0, 160)}`));
  console.log(`  failed requests        : ${b.failedReq.length}`);
  b.failedReq.slice(0, 15).forEach((x) => console.log(`    x ${x.slice(0, 160)}`));
  console.log(`  HTTP >=400 responses   : ${b.badResp.length}`);
  b.badResp.slice(0, 15).forEach((x) => console.log(`    > ${x.slice(0, 160)}`));
}

const run = async () => {
  const browser = await chromium.launch();

  // ============ PHASE 1: FRESH LOAD (like incognito) ============
  const ctx1 = await browser.newContext();
  const p1 = await ctx1.newPage();
  const b1 = newBucket();
  attach(p1, b1);
  await p1.goto(BASE, { waitUntil: "networkidle", timeout: 30000 });
  await sleep(1500);

  // Is it actually styled? check computed bg of body + presence of hero
  const styled1 = await p1.evaluate(() => {
    const bg = getComputedStyle(document.body).backgroundColor;
    const htmlClass = document.documentElement.className;
    const hasTailwind = !!document.querySelector("[class*='bg-'],[class*='text-']");
    const heroText = document.body.innerText.includes("AI Triage Nurse");
    return { bg, htmlClass, hasTailwind, heroText };
  });
  report("PHASE 1 — FRESH landing (incognito-equivalent)", b1);
  console.log("  rendering:", JSON.stringify(styled1));
  await p1.screenshot({ path: "audit/p1-fresh-landing.png" });

  // ============ PHASE 4: STALE STATE (like normal browser) ============
  const ctx2 = await browser.newContext();
  const p2 = await ctx2.newPage();
  // Seed stale localStorage BEFORE any app code runs
  await p2.addInitScript(() => {
    localStorage.setItem("access_token", "stale.invalid.token");
    localStorage.setItem("refresh_token", "stale.invalid.refresh");
    localStorage.setItem("theme", "light");
  });
  const b2 = newBucket();
  attach(p2, b2);
  await p2.goto(BASE, { waitUntil: "networkidle", timeout: 30000 });
  await sleep(1500);
  const styled2 = await p2.evaluate(() => {
    const bg = getComputedStyle(document.body).backgroundColor;
    return { bg, htmlClass: document.documentElement.className,
             heroText: document.body.innerText.includes("AI Triage Nurse") };
  });
  report("PHASE 4 — STALE localStorage (normal-browser-equivalent)", b2);
  console.log("  rendering:", JSON.stringify(styled2));
  await p2.screenshot({ path: "audit/p4-stale-landing.png" });

  // Navigate to dashboard with stale token (protected route)
  const b2b = newBucket();
  attach(p2, b2b);
  await p2.goto(`${BASE}/dashboard`, { waitUntil: "networkidle", timeout: 30000 });
  await sleep(2000);
  console.log("  after /dashboard with stale token, URL:", p2.url());
  report("PHASE 4b — /dashboard with stale token", b2b);

  // ============ PHASE 2: SIGNUP FLOW (real form) ============
  const ctx3 = await browser.newContext();
  const p3 = await ctx3.newPage();
  const b3 = newBucket();
  attach(p3, b3);
  await p3.goto(`${BASE}/auth/signup`, { waitUntil: "networkidle", timeout: 30000 });
  await sleep(1000);

  const uid = Math.random().toString(36).slice(2, 8);
  const email = `audit_${uid}@neuralhub-test.com`;
  try {
    await p3.fill('input[placeholder="John"]', "Audit");
    await p3.fill('input[placeholder="Smith"]', "Tester");
    await p3.fill('input[placeholder="City Medical Clinic"]', `Audit Clinic ${uid}`);
    await p3.fill('input[type="email"]', email);
    await p3.fill('input[placeholder="Min 8 characters"]', "AuditPass123!");
    await p3.fill('input[placeholder="••••••••"]', "AuditPass123!");
    await sleep(300);
    await p3.click('button[type="submit"]');
    await sleep(4000);
    console.log(`  signup submitted as ${email}, URL now: ${p3.url()}`);
    const toastText = await p3.evaluate(() => document.body.innerText.match(/(Failed|error|Welcome|created|exists)[^\n]*/i)?.[0] || "no toast text found");
    console.log("  toast/message:", toastText);
  } catch (e) {
    console.log("  SIGNUP INTERACTION ERROR:", e.message.slice(0, 200));
  }
  report("PHASE 2 — Signup flow", b3);
  await p3.screenshot({ path: "audit/p2-after-signup.png" });
  console.log("\n  SIGNUP_RESULT_EMAIL=" + email);

  await browser.close();
  console.log("\n===== AUDIT COMPLETE =====");
};

run().catch((e) => { console.error("FATAL:", e); process.exit(1); });
