import { chromium } from "playwright";
const BASE = "http://localhost:3000";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const run = async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext();
  const page = await ctx.newPage();

  page.on("console", (m) => { if (m.type()==="error") console.log("CONSOLE.ERR:", m.text().slice(0,200)); });
  page.on("pageerror", (e) => console.log("PAGE.ERR:", e.message.slice(0,200)));

  // Capture the register request + response bodies
  page.on("request", (r) => {
    if (r.url().includes("/auth/register")) {
      console.log("\n>>> REGISTER REQUEST");
      console.log("    method:", r.method());
      console.log("    postData:", r.postData());
    }
  });
  page.on("response", async (resp) => {
    if (resp.url().includes("/auth/register")) {
      console.log("<<< REGISTER RESPONSE");
      console.log("    status:", resp.status());
      try { console.log("    body:", (await resp.text()).slice(0, 300)); } catch {}
    }
  });

  await page.goto(`${BASE}/auth/signup`, { waitUntil: "networkidle" });
  await sleep(1000);

  // Inspect the actual form field placeholders present
  const fields = await page.evaluate(() =>
    Array.from(document.querySelectorAll("input")).map((i) => ({
      type: i.type, placeholder: i.placeholder, name: i.name,
    }))
  );
  console.log("FORM FIELDS:", JSON.stringify(fields, null, 0));

  const uid = Math.random().toString(36).slice(2, 8);
  const email = `signup_${uid}@neuralhub-test.com`;

  // Fill by index to be robust
  const inputs = page.locator("input");
  await inputs.nth(0).fill("Signup");        // first name
  await inputs.nth(1).fill("Test");          // last name
  await inputs.nth(2).fill(`Clinic ${uid}`); // org
  await inputs.nth(3).fill(email);           // email
  await inputs.nth(4).fill("SignupPass123!");// password
  await inputs.nth(5).fill("SignupPass123!");// confirm
  await sleep(300);

  console.log("\nClicking submit...");
  await page.click('button[type="submit"]');
  await sleep(5000);

  console.log("URL after submit:", page.url());
  const bodyText = await page.evaluate(() => document.body.innerText);
  const msg = bodyText.match(/(Failed[^\n]*|already exists[^\n]*|Welcome[^\n]*|created[^\n]*|required[^\n]*|valid[^\n]*|match[^\n]*)/i);
  console.log("Visible message:", msg ? msg[0] : "(none)");
  console.log("EMAIL_USED=" + email);

  await browser.close();
};
run().catch((e) => { console.error("FATAL", e); process.exit(1); });
