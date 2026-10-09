// Connect/lock screen of the Capacitor shell (ADR 023).
// Plain JS, no bundler — native plugins via Capacitor.registerPlugin, which the
// @capacitor/core runtime (loaded in index.html) attaches to window.Capacitor.
//
// Deep links:
//   openavisio://connect?url=https://deployment[&token=INVITE]  → store URL, open /register?token=…
//   openavisio://reset                                          → forget stored URL and lock setting
//
// ponytail: biometric lock gates app *launch* only — resume from background
// stays unlocked (native appStateChange hook in the remote-origin WebView is
// the upgrade path if customers need re-lock on resume).

const URL_KEY = "deploymentUrl";
const LOCK_KEY = "bioLock";

const inWebView = typeof document !== "undefined";
const $ = (id) => document.getElementById(id);
const cap = inWebView ? window.Capacitor : null;
// Guard registerPlugin: if the core runtime is ever missing, degrade to no
// deep links / no biometry instead of throwing here — a throw would leave the
// submit handler below unbound and silently break "Verbinden" entirely.
const reg = cap && typeof cap.registerPlugin === "function" ? cap.registerPlugin.bind(cap) : null;
const App = reg ? reg("App") : null;
const Bio = reg ? reg("BiometricAuth") : null;

function normalize(u) {
  u = u.trim().replace(/\/+$/, "");
  if (!/^https?:\/\//.test(u)) u = "https://" + u;
  return u;
}

function parseDeepLink(raw) {
  let u;
  try { u = new URL(raw); } catch { return null; }
  if (u.protocol !== "openavisio:") return null;
  const action = u.host || u.pathname.replace(/^\/+/, "");
  if (action === "reset") return { action };
  if (action === "connect" && u.searchParams.get("url")) {
    return {
      action,
      url: normalize(u.searchParams.get("url")),
      token: u.searchParams.get("token") || null,
    };
  }
  return null;
}

async function reachable(url) {
  // no-cors: opaque response on success, throws on DNS/network failure
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), 8000);
  try { await fetch(url, { mode: "no-cors", signal: ctl.signal }); return true; }
  catch { return false; }
  finally { clearTimeout(t); }
}

async function biometryAvailable() {
  if (!Bio) return false;
  try { return (await Bio.checkBiometry()).isAvailable; } catch { return false; }
}

async function authenticate() {
  try {
    await Bio.authenticate({
      reason: "OpenAvisio entsperren",
      androidTitle: "OpenAvisio entsperren",
      allowDeviceCredential: true,
    });
    return true;
  } catch { return false; }
}

function fail(msg) {
  $("error").textContent = msg;
  $("go").disabled = false;
}

async function open(url) {
  if (await reachable(url)) location.replace(url);
  else fail("Server nicht erreichbar / server unreachable");
}

async function handleDeepLink(link) {
  if (link.action === "reset") {
    localStorage.removeItem(URL_KEY);
    localStorage.removeItem(LOCK_KEY);
    $("url").value = "";
    return true;
  }
  // connect: no lock gate — this is registration, there is no session yet
  localStorage.setItem(URL_KEY, link.url);
  await open(link.token ? `${link.url}/register?token=${encodeURIComponent(link.token)}` : link.url);
  return true;
}

async function launch() {
  if (await biometryAvailable()) $("lockRow").classList.remove("hidden");

  if (App) {
    App.addListener("appUrlOpen", ({ url }) => {
      const link = parseDeepLink(url);
      if (link) handleDeepLink(link);
    });
    const launchUrl = await App.getLaunchUrl().catch(() => null);
    const link = launchUrl && parseDeepLink(launchUrl.url);
    if (link && (await handleDeepLink(link))) return;
  }

  const saved = localStorage.getItem(URL_KEY);
  if (!saved) return;
  $("url").value = saved;

  if (localStorage.getItem(LOCK_KEY) === "1") {
    $("form").classList.add("hidden");
    $("unlock").classList.remove("hidden");
    if (await authenticate()) { open(saved); return; }
    fail("Entsperren fehlgeschlagen / unlock failed");
    // retry button stays visible
    return;
  }
  open(saved);
}

if (inWebView) {
$("unlock").addEventListener("click", async () => {
  $("error").textContent = "";
  if (await authenticate()) open(localStorage.getItem(URL_KEY));
  else fail("Entsperren fehlgeschlagen / unlock failed");
});

$("form").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("error").textContent = "";
  $("go").disabled = true;
  const url = normalize($("url").value);
  if (!(await reachable(url))) return fail("Server nicht erreichbar / server unreachable");
  localStorage.setItem(URL_KEY, url);
  localStorage.setItem(LOCK_KEY, $("lock").checked ? "1" : "0");
  location.replace(url);
});

launch();
}

// exported for the node self-check; harmless in the WebView
if (typeof module !== "undefined") module.exports = { normalize, parseDeepLink };
