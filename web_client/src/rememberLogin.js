/** "Ghi nhớ đăng nhập" on the login page.
 *
 * - The email and the checkbox choice are kept in localStorage per portal so
 *   the login form is pre-filled after a logout.
 * - The password is NEVER written to localStorage: it is handed to the
 *   browser's own password manager (Credential Management API where the
 *   browser has it, otherwise the usual autofill driven by autocomplete
 *   attributes), which stores it encrypted and fills it back in.
 * - Staying signed in is the server's refresh token (HttpOnly cookie); this
 *   module only decides whether login asks for the long-lived one.
 */
const key = (portal) => `eas.login.${portal || "unified"}`;

function storageOrNull(storage) {
  try {
    return storage ?? globalThis.localStorage ?? null;
  } catch {
    return null;
  }
}

export function loadRemembered(portal, storage) {
  try {
    const raw = storageOrNull(storage)?.getItem(key(portal));
    if (!raw) return { remember: true, email: "" };
    const value = JSON.parse(raw);
    return {
      remember: value?.remember !== false,
      email: typeof value?.email === "string" ? value.email : "",
    };
  } catch {
    return { remember: true, email: "" };
  }
}

export function saveRemembered(portal, { remember, email }, storage) {
  try {
    storageOrNull(storage)?.setItem(
      key(portal),
      JSON.stringify({ remember: Boolean(remember), email: remember ? String(email || "") : "" }),
    );
  } catch {
    // Private mode or blocked storage: the form simply starts empty.
  }
}

export function storeBrowserCredential({ email, password, name }, win = globalThis.window) {
  try {
    if (!win?.PasswordCredential || !win.navigator?.credentials?.store) return Promise.resolve(false);
    const credential = new win.PasswordCredential({ id: email, password, name: name || email });
    return win.navigator.credentials.store(credential).then(() => true, () => false);
  } catch {
    return Promise.resolve(false);
  }
}

export async function readBrowserCredential(win = globalThis.window) {
  try {
    if (!win?.PasswordCredential || !win.navigator?.credentials?.get) return null;
    // "silent": never pops a chooser on page load; null when nothing is saved.
    const credential = await win.navigator.credentials.get({ password: true, mediation: "silent" });
    return credential?.type === "password" ? { email: credential.id, password: credential.password } : null;
  } catch {
    return null;
  }
}
