import test from "node:test";
import assert from "node:assert/strict";
import { loadRemembered, readBrowserCredential, saveRemembered, storeBrowserCredential } from "../src/rememberLogin.js";

function memoryStorage() {
  const data = new Map();
  return { getItem: (k) => (data.has(k) ? data.get(k) : null), setItem: (k, v) => data.set(k, String(v)), data };
}

test("remember me is on by default and keeps only the email, never the password", () => {
  const storage = memoryStorage();
  assert.deepEqual(loadRemembered("client", storage), { remember: true, email: "" });
  saveRemembered("client", { remember: true, email: "an.do@eas.com", password: "secret" }, storage);
  assert.deepEqual(loadRemembered("client", storage), { remember: true, email: "an.do@eas.com" });
  assert.ok(![...storage.data.values()].some((v) => v.includes("secret")));
});

test("unticking remember me forgets the email; portals are separate", () => {
  const storage = memoryStorage();
  saveRemembered("admin", { remember: true, email: "admin@eas.com" }, storage);
  saveRemembered("client", { remember: false, email: "an.do@eas.com" }, storage);
  assert.deepEqual(loadRemembered("client", storage), { remember: false, email: "" });
  assert.equal(loadRemembered("admin", storage).email, "admin@eas.com");
});

test("broken or blocked storage never breaks the login page", () => {
  const broken = { getItem: () => { throw new Error("blocked"); }, setItem: () => { throw new Error("blocked"); } };
  assert.deepEqual(loadRemembered("client", broken), { remember: true, email: "" });
  saveRemembered("client", { remember: true, email: "x@eas.com" }, broken);
  const corrupt = { getItem: () => "{not json", setItem() {} };
  assert.deepEqual(loadRemembered("client", corrupt), { remember: true, email: "" });
});

test("passwords go to the browser credential store when it exists", async () => {
  const stored = [];
  class PasswordCredential { constructor(data) { Object.assign(this, data, { type: "password" }); } }
  const win = {
    PasswordCredential,
    navigator: {
      credentials: {
        store: async (c) => { stored.push(c); },
        get: async () => stored[0] ?? null,
      },
    },
  };
  assert.equal(await readBrowserCredential(win), null);
  assert.equal(await storeBrowserCredential({ email: "an.do@eas.com", password: "pw", name: "An" }, win), true);
  assert.deepEqual(await readBrowserCredential(win), { email: "an.do@eas.com", password: "pw" });
  assert.equal(await storeBrowserCredential({ email: "a", password: "b" }, {}), false);
  assert.equal(await readBrowserCredential({}), null);
});
