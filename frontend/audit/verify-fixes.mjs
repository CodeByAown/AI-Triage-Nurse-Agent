import { chromium } from "playwright";
const BASE = "http://localhost:3000";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const EMAIL = process.env.AUDIT_EMAIL;
const PASS = process.env.AUDIT_PASS;

const run = async () => {
  const browser = await chromium.launch();
  let allPass = true;
  const fail = (m) => { allPass = false; console.log("  FAIL:", m); };

  // ---- FIX 1 verify: stale theme=light must STILL render dark ----
  {
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    await page.addInitScript(() => {
      localStorage.setItem("theme", "light");
      localStorage.setItem("access_token", "stale.invalid");
      localStorage.setItem("refresh_token", "stale.invalid");
    });
    await page.goto(BASE, { waitUntil: "networkidle" });
    await sleep(1500);
    const r = await page.evaluate(() => ({
      bg: getComputedStyle(document.body).backgroundColor,
      cls: document.documentElement.className,
    }));
    console.log("FIX 1 (theme forced dark despite stale theme=light):");
    console.log("   body bg:", r.bg, "| html class:", r.cls);
    if (r.bg === "rgb(255, 255, 255)") fail("landing still white with stale theme=light");
    else console.log("   PASS — landing renders dark regardless of stored theme");
  }

  // ---- FIX 2 verify: invalid login shows error, no hard reload ----
  {
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    let navs = 0;
    page.on("framenavigated", (f) => { if (f === page.mainFrame()) navs++; });
    await page.goto(`${BASE}/auth/signin`, { waitUntil: "networkidle" });
    await sleep(600);
    const base = navs;
    const inputs = page.locator("input");
    await inputs.nth(0).fill("wrong_user@test.com");
    await inputs.nth(1).fill("WrongPass123!");
    await page.click('button[type="submit"]');
    await sleep(3500);
    const navsDuring = navs - base;
    const txt = await page.evaluate(() => document.body.innerText);
    const hasErr = /Invalid email or password|incorrect/i.test(txt);
    console.log("\nFIX 2 (invalid login UX):");
    console.log("   navigations during submit:", navsDuring, "| error shown:", hasErr);
    console.log("   URL:", page.url());
    if (navsDuring > 0) fail("still hard-reloads on invalid login");
    if (!hasErr) fail("no error message shown on invalid login");
    if (navsDuring === 0 && hasErr) console.log("   PASS — error toast shown, no reload");
  }

  // ---- FIX 3 verify: settings no hydration error + logout works ----
  {
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    const consoleErrs = [];
    page.on("console", (m) => { if (m.type() === "error") consoleErrs.push(m.text()); });

    // login
    await page.goto(`${BASE}/auth/signin`, { waitUntil: "networkidle" });
    await sleep(600);
    const inputs = page.locator("input");
    await inputs.nth(0).fill(EMAIL);
    await inputs.nth(1).fill(PASS);
    await page.click('button[type="submit"]');
    await page.waitForURL("**/dashboard", { timeout: 12000 }).catch(() => {});
    await sleep(1000);

    // visit settings, watch for hydration error
    consoleErrs.length = 0;
    await page.goto(`${BASE}/settings`, { waitUntil: "networkidle" });
    await sleep(1800);
    const hydErr = consoleErrs.find((e) => /hydrat/i.test(e));
    console.log("\nFIX 3a (settings hydration):");
    console.log("   console errors on /settings:", consoleErrs.length);
    if (hydErr) fail("settings still has hydration error: " + hydErr.slice(0,90));
    else console.log("   PASS — no hydration error on settings");

    // logout
    const signOut = page.locator("text=Sign out").first();
    await signOut.click();
    await page.waitForURL("**/auth/signin", { timeout: 8000 }).catch(() => {});
    await sleep(1500);
    const onSignin = page.url().includes("/auth/signin");
    const tokenGone = await page.evaluate(() => !localStorage.getItem("access_token"));
    console.log("\nFIX 3b (logout):");
    console.log("   URL:", page.url(), "| token cleared:", tokenGone);
    if (!onSignin) fail("logout did not navigate to signin");
    if (!tokenGone) fail("logout did not clear token");
    if (onSignin && tokenGone) console.log("   PASS — logout redirects to signin and clears token");
  }

  await browser.close();
  console.log("\n===== " + (allPass ? "ALL FIXES VERIFIED" : "SOME FIXES FAILED") + " =====");
  process.exit(allPass ? 0 : 1);
};
run().catch((e) => { console.error("FATAL", e); process.exit(1); });
