import { chromium } from "playwright";
const BASE = "http://localhost:3000";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const EMAIL = process.env.AUDIT_EMAIL;
const PASS = process.env.AUDIT_PASS;

const run = async () => {
  const browser = await chromium.launch();

  // ---- TEST 1: invalid credentials on signin ----
  {
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    let reloaded = 0;
    page.on("framenavigated", (f) => { if (f === page.mainFrame()) reloaded++; });
    await page.goto(`${BASE}/auth/signin`, { waitUntil: "networkidle" });
    await sleep(600);
    const navBefore = reloaded;
    const inputs = page.locator("input");
    await inputs.nth(0).fill("nobody_wrong@test.com");
    await inputs.nth(1).fill("WrongPass123!");
    await page.click('button[type="submit"]');
    await sleep(3500);
    const navAfter = reloaded;
    const text = await page.evaluate(() => document.body.innerText);
    const errMsg = text.match(/Invalid[^\n]*|incorrect[^\n]*|Failed[^\n]*/i);
    console.log("TEST 1 — Invalid credentials:");
    console.log("  URL:", page.url());
    console.log("  page navigations during submit:", navAfter - navBefore, "(0 = stayed, >0 = hard reload)");
    console.log("  error message shown:", errMsg ? errMsg[0] : "(NONE — bad UX)");
  }

  // ---- TEST 2: valid login + refresh persistence ----
  {
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    await page.goto(`${BASE}/auth/signin`, { waitUntil: "networkidle" });
    await sleep(600);
    const inputs = page.locator("input");
    await inputs.nth(0).fill(EMAIL);
    await inputs.nth(1).fill(PASS);
    await page.click('button[type="submit"]');
    await page.waitForURL("**/dashboard", { timeout: 12000 }).catch(() => {});
    await sleep(1200);
    console.log("\nTEST 2 — Valid login + persistence:");
    console.log("  after login URL:", page.url());
    // hard refresh
    await page.reload({ waitUntil: "networkidle" });
    await sleep(2000);
    console.log("  after hard refresh URL:", page.url(), "(should stay /dashboard)");
    const stillAuthed = !page.url().includes("/auth/");
    console.log("  stayed logged in:", stillAuthed);

    // ---- TEST 3: logout ----
    // click sign out in sidebar
    const signOut = page.locator("text=Sign out").first();
    if (await signOut.count()) {
      await signOut.click();
      await sleep(2500);
      console.log("\nTEST 3 — Logout:");
      console.log("  after logout URL:", page.url(), "(should be /auth/signin)");
      const tokenGone = await page.evaluate(() => !localStorage.getItem("access_token"));
      console.log("  token cleared from localStorage:", tokenGone);
    } else {
      console.log("\nTEST 3 — Logout: sign out button NOT FOUND");
    }
  }

  await browser.close();
  console.log("\n===== AUTH BEHAVIOR AUDIT COMPLETE =====");
};
run().catch((e) => { console.error("FATAL", e); process.exit(1); });
