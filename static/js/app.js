/* Vitala front-end app */
"use strict";

/* ---------------- utils ---------------- */
const $ = (s, r) => (r || document).querySelector(s);
const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
function esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}
function num(v, d) { const n = parseFloat(v); return isFinite(n) ? n : d; }
function todayStr() { const d = new Date(); return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0"); }
function deepClone(o) { return JSON.parse(JSON.stringify(o)); }
function toast(msg, ms) {
  const wrap = $("#toast-wrap");
  const el = document.createElement("div");
  el.className = "toast";
  el.textContent = msg;
  wrap.appendChild(el);
  setTimeout(() => { el.style.opacity = "0"; el.style.transition = "opacity .3s"; setTimeout(() => el.remove(), 320); }, ms || 2200);
}
function confirmBox(msg, onOk) {
  const root = $("#modal-root");
  root.innerHTML = "";
  const mask = document.createElement("div");
  mask.className = "modal-mask";
  mask.innerHTML = '<div class="modal"><h3></h3><div class="sub"></div><div class="row" style="justify-content:flex-end;gap:8px;margin-top:8px">'
    + '<button class="btn btn-ghost" data-act="no"></button><button class="btn btn-primary" data-act="yes"></button></div></div>';
  $("h3", mask).textContent = t("common.confirm");
  $(".sub", mask).textContent = msg;
  const [noB, yesB] = $$("button", mask);
  noB.textContent = t("common.cancel"); yesB.textContent = t("common.confirm");
  mask.addEventListener("click", e => { if (e.target === mask) close(); });
  noB.addEventListener("click", close); yesB.addEventListener("click", () => { close(); onOk && onOk(); });
  root.appendChild(mask);
  function close() { mask.remove(); }
}
function showModal(html, { wide } = {}) {
  const root = $("#modal-root");
  const mask = document.createElement("div");
  mask.className = "modal-mask";
  const m = document.createElement("div");
  m.className = "modal" + (wide ? " wide" : "");
  m.innerHTML = html;
  mask.appendChild(m);
  mask.addEventListener("click", e => { if (e.target === mask) mask.remove(); });
  root.appendChild(mask);
  return m;
}
function closeModal() { $("#modal-root").innerHTML = ""; }

/* ---------------- state ---------------- */
const LS = {
  token: "vitala_token", user: "vitala_user", lang: "vitala_lang", theme: "vitala_theme",
};
const S = {
  token: localStorage.getItem(LS.token) || "",
  user: null,
  profile: null,
  targets: null,
  view: "home",
  pendingQuestion: null,
  catalog: null,
  chat: [],
  installEvt: null,
  onboard: { phase: "tour", slide: 0, step: 0, skipped: [] },
};

/* ---------------- api ---------------- */
async function api(path, opts = {}) {
  const init = { method: opts.method || "GET", headers: {} };
  if (opts.body !== undefined) {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(opts.body);
  }
  if (S.token) init.headers["Authorization"] = "Bearer " + S.token;
  let res;
  try {
    res = await fetch(path, init);
  } catch (e) {
    throw { status: 0, detail: t("common.offline") };
  }
  const ct = res.headers.get("content-type") || "";
  const data = ct.includes("application/json") ? await res.json() : await res.text();
  if (res.status === 401 && S.token && !path.includes("/auth/login") && !path.includes("/auth/register")) {
    localStorage.removeItem(LS.token); localStorage.removeItem(LS.user);
    S.token = ""; S.user = null;
    showPage("auth");
    toast(t("common.unauth"));
    throw { status: 401, detail: t("common.unauth") };
  }
  if (!res.ok) throw { status: res.status, detail: data && data.detail ? data.detail : t("err.unknown") };
  return data;
}
function saveSession(token, user) {
  S.token = token; S.user = user;
  localStorage.setItem(LS.token, token);
  localStorage.setItem(LS.user, JSON.stringify(user));
}

/* ---------------- avatar ---------------- */
const AVATARS = ["🥑", "🍎", "🥦", "🍋", "🌱", "🐟", "🍳", "🥗", "🫐", "🏃", "🌻", "💧"];
function avatarStyle(avatar, idx) {
  const palettes = [
    "linear-gradient(135deg,#2f8f62,#4cc083)", "linear-gradient(135deg,#e4573d,#ff9a5c)",
    "linear-gradient(135deg,#6c4cff,#a78bfa)", "linear-gradient(135deg,#0e9f9f,#4cc9c9)",
    "linear-gradient(135deg,#d69a3c,#f2c14e)", "linear-gradient(135deg,#2563eb,#60a5fa)",
  ];
  const i = (idx == null ? 0 : idx) % palettes.length;
  return palettes[i];
}
function avatarHTML(avatar, size, rounded) {
  avatar = avatar || { type: "initials" };
  const cls = "avatar" + (rounded ? " rounded" : "");
  const st = "width:" + size + "px;height:" + size + "px;font-size:" + Math.round(size * 0.42) + "px";
  if (avatar.type === "upload" && avatar.value && avatar.value.indexOf("data:image") === 0) {
    return '<span class="' + cls + '" style="' + st + '"><img src="' + avatar.value + '" alt="avatar"></span>';
  }
  if (avatar.type === "preset" && avatar.value) {
    return '<span class="' + cls + '" style="' + st + ";background:" + avatarStyle(avatar, (AVATARS.indexOf(avatar.value) + 1)) + '">' + esc(avatar.value) + "</span>";
  }
  const name = (S.user && (S.user.display_name || S.user.username)) || "V";
  const ch = (name.trim()[0] || "V").toUpperCase();
  return '<span class="' + cls + '" style="' + st + ";background:" + avatarStyle(avatar, ch.charCodeAt(0)) + '">' + esc(ch) + "</span>";
}

/* ---------------- options / labels ---------------- */
const OPT_KEYS = {
  gender: ["male", "female", "other"],
  goal: ["lose", "gain", "maintain", "healthy"],
  activity: ["sedentary", "light", "moderate", "active", "very_active"],
  exfreq: ["rarely", "1_2", "3_4", "5"],
  extime: ["morning", "afternoon", "evening", "any"],
  diet: ["omnivore", "vegetarian", "vegan"],
  eatout: ["rarely", "sometimes", "often"],
};
const OPT_ICONS = {
  gender: { male: "♂", female: "♀", other: "✨" },
  goal: { lose: "🔥", gain: "💪", maintain: "⚖️", healthy: "🥗" },
  activity: { sedentary: "🪑", light: "🚶", moderate: "🚴", active: "🏃", very_active: "🏋️" },
  exfreq: { rarely: "😴", "1_2": "🌤", "3_4": "🌿", "5": "🔥" },
  extime: { morning: "🌅", afternoon: "☀️", evening: "🌙", any: "⏱" },
  diet: { omnivore: "🍱", vegetarian: "🥬", vegan: "🌱" },
  eatout: { rarely: "🏠", sometimes: "🍜", often: "🍽️" },
};
const ALLERGIES = [
  ["milk", "🥛"], ["egg", "🥚"], ["peanut", "🥜"], ["nut", "🌰"],
  ["seafood", "🦐"], ["gluten", "🌾"], ["soy", "🫘"], ["sesame", "🫓"],
];
const HEALTH_CONDITIONS = [
  ["diabetes", "🩸"], ["hypertension", "❤️"], ["kidney", "🫘"],
  ["gout", "🦶"], ["hyperlipidemia", "🧈"], ["gastric", "🍽️"],
];
const EXERCISE_TYPES = [
  ["running", "🏃"], ["walking", "🚶"], ["swimming", "🏊"], ["cycling", "🚴"],
  ["gym", "🏋️"], ["yoga", "🧘"], ["dance", "💃"], ["ball", "⚽"], ["home", "🏠"],
];
const EX_KEYS = ["running", "walking", "swimming", "cycling", "gym", "yoga", "dance", "ball", "home"];
const ALLERGY_KEYS = ["milk", "egg", "peanut", "nut", "seafood", "gluten", "soy", "sesame"];
const HEALTH_KEYS = ["diabetes", "hypertension", "kidney", "gout", "hyperlipidemia", "gastric"];
function optLabel(cat, key) {
  if (!key) return "";
  const base = t("opt." + cat + "." + key);
  return base === "opt." + cat + "." + key ? key : base;
}
function allergyLabel(key) { const zh = { milk: "牛奶", egg: "鸡蛋", peanut: "花生", nut: "坚果", seafood: "海鲜", gluten: "麸质", soy: "大豆", sesame: "芝麻" }; return getLang() === "zh" ? zh[key] || key : (key === "milk" ? "Milk" : key === "egg" ? "Eggs" : key === "peanut" ? "Peanuts" : key === "nut" ? "Tree nuts" : key === "seafood" ? "Seafood" : key === "gluten" ? "Gluten" : key === "soy" ? "Soy" : key === "sesame" ? "Sesame" : key); }
function healthLabel(key) { const zh = { diabetes: "糖尿病", hypertension: "高血压", kidney: "肾病", gout: "痛风", hyperlipidemia: "高血脂", gastric: "肠胃不适" }; const en = { diabetes: "Diabetes", hypertension: "Hypertension", kidney: "Kidney disease", gout: "Gout", hyperlipidemia: "High lipids", gastric: "Digestive issues" }; return getLang() === "zh" ? zh[key] || key : en[key] || key; }
function exLabel(key) { const zh = { running: "跑步", walking: "快走", swimming: "游泳", cycling: "骑行", gym: "力量训练", yoga: "瑜伽", dance: "舞蹈", ball: "球类", home: "居家锻炼" }; const en = { running: "Running", walking: "Walking", swimming: "Swimming", cycling: "Cycling", gym: "Strength", yoga: "Yoga", dance: "Dance", ball: "Ball sports", home: "Home workout" }; return getLang() === "zh" ? zh[key] || key : en[key] || key; }
function mealTypeLabel(key) { return t("meal." + key); }
const MEAL_KEY = { "早餐": "breakfast", "午餐": "lunch", "晚餐": "dinner", "加餐": "snack", breakfast: "breakfast", lunch: "lunch", dinner: "dinner", snack: "snack" };
function mealKey(v) { return MEAL_KEY[v] || v || "lunch"; }

/* ---------------- markdown ---------------- */
function md2html(src) {
  src = String(src || "");
  let out = "";
  const lines = src.split(/\r?\n/);
  let i = 0;
  let inList = false, listType = null, inTable = false;
  const flushList = () => { if (inList) { out += listType === "ul" ? "</ul>" : "</ol>"; inList = false; listType = null; } };
  function inline(s) {
    s = esc(s);
    s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
    s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/\*([^*]+)\*/g, "<em>$1</em>");
    s = s.replace(/\[([^\]]+)\]\((https?:[^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    return s;
  }
  for (; i < lines.length; i++) {
    const ln = lines[i];
    const tln = ln.trim();
    if (!tln) { flushList(); out += inTable ? "" : ""; continue; }
    if (tln.startsWith("```")) {
      flushList();
      const code = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith("```")) { code.push(lines[i]); i++; }
      out += "<pre>" + esc(code.join("\n")) + "</pre>";
      continue;
    }
    const h = /^(#{1,4})\s+(.*)$/.exec(tln);
    if (h) { flushList(); const lvl = h[1].length; out += "<h" + lvl + ">" + inline(h[2]) + "</h" + lvl + ">"; continue; }
    if (/^\s*[-*]\s+/.test(ln)) {
      if (!inList) { out += "<ul>"; inList = true; listType = "ul"; }
      out += "<li>" + inline(tln.replace(/^\s*[-*]\s+/, "")) + "</li>";
      continue;
    }
    const ol = /^\s*\d+[.)]\s+(.*)$/.exec(ln);
    if (ol) {
      if (!inList) { out += "<ol>"; inList = true; listType = "ol"; }
      out += "<li>" + inline(ol[1]) + "</li>";
      continue;
    }
    flushList();
    if (tln.startsWith(">")) {
      out += "<blockquote>" + inline(tln.replace(/^>\s?/, "")) + "</blockquote>";
      continue;
    }
    if (/^\|.*\|$/.test(tln) && /^\|[\s:|-]+\|$/.test(lines[i + 1] || "")) {
      // table header
      const cells = tln.split("|").slice(1, -1).map(c => inline(c.trim()));
      out += "<table><thead><tr>" + cells.map(c => "<th>" + c + "</th>").join("") + "</tr></thead><tbody>";
      i++;
      while (i + 1 < lines.length && /^\|.*\|$/.test(lines[i + 1].trim())) {
        i++;
        const row = lines[i].split("|").slice(1, -1).map(c => "<td>" + inline(c.trim()) + "</td>");
        out += "<tr>" + row.join("") + "</tr>";
      }
      out += "</tbody></table>";
      continue;
    }
    out += "<p>" + inline(tln) + "</p>";
  }
  flushList();
  return out;
}

/* ---------------- theme & language ---------------- */
function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme || "light");
  localStorage.setItem(LS.theme, theme || "light");
  const colors = { light: "#f5f7f4", fresh: "#fff8f3", dark: "#0e1116" };
  const mt = $("#meta-theme"); if (mt) mt.setAttribute("content", colors[theme] || colors.light);
  if (S.token && S.user && S.user.theme !== theme) {
    S.user.theme = theme;
    api("/api/me", { method: "PUT", body: { theme } }).catch(() => {});
  }
}
function applyLanguage(lang) {
  const l = lang === "en" ? "en" : "zh";
  setLang(l);
  localStorage.setItem(LS.lang, l);
  document.title = "Vitala" + (l === "zh" ? " — 你的 AI 营养管家" : " — Your nutrition companion");
  if (S.token && S.user && S.user.language !== l) {
    S.user.language = l;
    api("/api/me", { method: "PUT", body: { language: l } }).catch(() => {});
  }
  refreshUI();
}
/* ---------------- router ---------------- */
function showPage(name) {
  ["auth", "onboard", "app"].forEach(p => {
    $("#page-" + p).classList.toggle("hidden", p !== name);
  });
  if (name === "auth") renderAuth();
  else if (name === "onboard") renderOnboarding();
  else if (name === "app") renderShell();
  translateStatic();
}
function refreshUI() {
  if (!$("#page-app").classList.contains("hidden")) {
    if ($("#page-auth").classList.contains("hidden") && $("#page-onboard").classList.contains("hidden")) {
      renderShell();
    }
  } else if (!$("#page-auth").classList.contains("hidden")) {
    renderAuth();
  } else if (!$("#page-onboard").classList.contains("hidden")) {
    renderOnboarding();
  }
}
function switchView(view) {
  S.view = view;
  renderShell();
}
function goChat(text) {
  S.pendingQuestion = text || null;
  S.view = "chat";
  renderShell();
}
function logout() {
  api("/api/auth/logout", { method: "POST" }).catch(() => {});
  localStorage.removeItem(LS.token);
  localStorage.removeItem(LS.user);
  S.token = ""; S.user = null; S.profile = null; S.targets = null; S.chat = [];
  showPage("auth");
}

/* ---------------- auth view ---------------- */
function renderAuth() {
  const host = $("#page-auth");
  host.innerHTML = '<div class="auth-shell">'
    + '<div class="auth-brand"><div class="inner">'
    + '<div class="ab-logo"><span class="mark">' + sproutSVG(22) + '</span><b style="font-size:22px">Vitala</b></div>'
    + '<h1 data-i18n="slogan1">' + t("slogan1") + "</h1>"
    + '<p class="lead" data-i18n="slogan2">' + t("slogan2") + "</p>"
    + '<div class="auth-features">'
    + feat("💬", "auth.feature1t", "auth.feature1d")
    + feat("📊", "auth.feature2t", "auth.feature2d")
    + feat("🎨", "auth.feature3t", "auth.feature3d")
    + feat("🔒", "auth.feature4t", "auth.feature4d")
    + "</div></div></div>"
    + '<div class="auth-form-side"><div class="auth-card">'
    + '<div class="auth-mobile-logo"><div style="display:flex;align-items:center;justify-content:center;gap:8px">'
    + '<span class="brand-mark" style="width:40px;height:40px;font-size:0;border-radius:13px">' + sproutSVG(22) + '</span>'
    + '<b style="font-size:20px">Vitala</b></div></div>'
    + '<div class="auth-tabs"><button data-mode="login" class="' + (S.authMode !== "register" ? "active" : "") + '">' + t("auth.tabLogin") + "</button>"
    + '<button data-mode="register" class="' + (S.authMode === "register" ? "active" : "") + '">' + t("auth.tabRegister") + "</button></div>"
    + '<div id="auth-body"></div></div></div></div>';
  $$(".auth-tabs button", host).forEach(b => b.addEventListener("click", () => { S.authMode = b.getAttribute("data-mode"); renderAuth(); }));
  renderAuthForm();
  function feat(ico, kt, kd) {
    return '<div class="auth-feature"><div class="f-ico">' + ico + '</div><div><b>' + t(kt) + "</b><span>" + t(kd) + "</span></div></div>";
  }
}
function renderAuthForm() {
  const body = $("#auth-body");
  if (S.authMode === "register") {
    body.innerHTML = '<h2>' + t("auth.create") + "</h2>"
      + '<p class="auth-sub">' + t("auth.createSub") + "</p>"
      + '<div class="field"><label>' + t("auth.username") + "</label><input class='input' id='reg-user' maxlength='24' placeholder='" + t("auth.usernamePh") + "'></div>"
      + '<div class="field"><label>' + t("me.avatar") + '</label><div class="chip-row" id="reg-avatars"></div></div>'
      + '<div class="grid grid-2" style="gap:10px">'
      + '<div class="field"><label>' + t("auth.email") + "</label><input class='input' id='reg-email' inputmode='email' placeholder='" + t("auth.emailPh") + "'></div>"
      + '<div class="field"><label>' + t("auth.phone") + "</label><input class='input' id='reg-phone' inputmode='tel' placeholder='" + t("auth.phonePh") + "'></div></div>"
      + '<p class="hint muted small" style="margin:-6px 0 10px">' + t("auth.contactHint") + "</p>"
      + '<div class="field"><label>' + t("auth.password") + "</label><input class='input' id='reg-pw' type='password' placeholder='" + t("auth.passwordPh") + "'></div>"
      + '<div class="field"><label>' + t("auth.confirm") + "</label><input class='input' id='reg-pw2' type='password' placeholder='" + t("auth.confirmPh") + "'></div>"
      + '<button class="btn btn-primary btn-block btn-lg" id="reg-submit">' + t("auth.submitRegister") + "</button>"
      + '<div class="auth-switch">' + t("auth.hasAccount") + ' <a id="to-login">' + t("auth.backLogin") + "</a></div>"
      + '<div class="auth-agree">' + t("auth.agree") + "</div>";
    let avatarPick = "";
    const box = $("#reg-avatars");
    AVATARS.forEach((a, idx) => {
      const b = document.createElement("div");
      b.className = "avatar-preset" + (idx === 0 ? " active" : "");
      b.textContent = a;
      b.dataset.val = a;
      b.style.background = avatarStyle(null, idx + 1);
      b.addEventListener("click", () => { $$(".avatar-preset", box).forEach(x => x.classList.remove("active")); b.classList.add("active"); });
      box.appendChild(b);
    });
    $("#reg-submit").addEventListener("click", doRegister);
    $$("input", body).forEach(i => i.addEventListener("keydown", e => { if (e.key === "Enter") doRegister(); }));
    $("#to-login").addEventListener("click", () => { S.authMode = "login"; renderAuth(); });
  } else {
    body.innerHTML = '<h2>' + t("auth.welcome") + "</h2>"
      + '<p class="auth-sub">' + t("auth.welcomeSub") + "</p>"
      + '<div class="field"><label>' + t("auth.identifier") + '</label><input class="input" id="lg-id" autocomplete="username" placeholder="' + t("auth.identifierPh") + '"></div>'
      + '<div class="field"><label>' + t("auth.password") + '</label><input class="input" id="lg-pw" type="password" placeholder="' + t("auth.passwordPh") + '"></div>'
      + '<button class="btn btn-primary btn-block btn-lg" id="lg-submit">' + t("auth.submitLogin") + "</button>"
      + '<div class="auth-switch">' + t("auth.noAccount") + ' <a id="to-reg">' + t("auth.joinNow") + "</a></div>";
    $("#lg-submit").addEventListener("click", doLogin);
    $$("input", body).forEach(i => i.addEventListener("keydown", e => { if (e.key === "Enter") doLogin(); }));
    $("#to-reg").addEventListener("click", () => { S.authMode = "register"; renderAuth(); });
  }
}
async function doLogin() {
  const identifier = $("#lg-id").value.trim();
  const password = $("#lg-pw").value;
  if (!identifier || !password) { toast(t("err.unknown")); return; }
  const btn = $("#lg-submit"); btn.disabled = true; btn.textContent = t("common.loading");
  try {
    const d = await api("/api/auth/login", { method: "POST", body: { identifier, password } });
    saveSession(d.token, d.user);
    toast(t("auth.loggedIn"));
    bootMain(d.user);
  } catch (e) { toast(e.detail || t("err.unknown")); btn.disabled = false; btn.textContent = t("auth.submitLogin"); }
}
async function doRegister() {
  const username = $("#reg-user").value.trim();
  const email = $("#reg-email").value.trim();
  const phone = $("#reg-phone").value.trim();
  const pw = $("#reg-pw").value;
  const pw2 = $("#reg-pw2").value;
  if (username.length < 2) { toast(t("auth.userLen")); return; }
  if (pw.length < 6) { toast(t("auth.pwdShort")); return; }
  if (pw !== pw2) { toast(t("auth.mismatch")); return; }
  if (!email && !phone) { toast(t("auth.needContact")); return; }
  const picked = $(".avatar-preset.active");
  const avatar = { type: "preset", value: picked ? picked.dataset.val : AVATARS[0] };
  const btn = $("#reg-submit"); btn.disabled = true; btn.textContent = t("common.loading");
  try {
    const d = await api("/api/auth/register", { method: "POST", body: { username, password: pw, email: email || null, phone: phone || null, avatar } });
    saveSession(d.token, d.user);
    toast(t("auth.registered"));
    bootMain(d.user);
  } catch (e) { toast(e.detail || t("err.unknown")); btn.disabled = false; btn.textContent = t("auth.submitRegister"); }
}

/* ---------------- onboarding ---------------- */
const TOUR = [
  { ico: "💬", kt: "tour.1t", kd: "tour.1d" },
  { ico: "📊", kt: "tour.2t", kd: "tour.2d" },
  { ico: "🍳", kt: "tour.3t", kd: "tour.3d" },
  { ico: "🧑", kt: "tour.4t", kd: "tour.4d" },
];
function renderOnboarding() {
  const host = $("#page-onboard");
  host.innerHTML = '<div class="onb-shell"><div class="onb-box">'
    + '<div class="onb-brand"><span class="mark">' + sproutSVG(24) + '</span><b>Vitala</b></div>'
    + '<div id="onb-body"></div></div></div>';
  const b = $("#onb-body");
  if (S.onboard.phase === "tour") {
    const s = TOUR[S.onboard.slide];
    b.innerHTML = '<div class="onb-card tour-stage" style="padding:34px 26px 26px">'
      + '<div class="tour-art">' + s.ico + "</div>"
      + "<h2>" + t(s.kt) + "</h2><p>" + t(s.kd) + "</p>"
      + '<div class="tour-dots">' + TOUR.map((x, i) => '<span class="tdot' + (i === S.onboard.slide ? " on" : "") + '"></span>').join("") + "</div>"
      + '<div class="row" style="justify-content:center;margin-top:20px">'
      + '<button class="btn btn-ghost" id="tour-skip">' + t("onb.skipAll") + "</button>"
      + '<button class="btn btn-primary btn-lg" id="tour-next">' + (S.onboard.slide === TOUR.length - 1 ? t("tour.done") : t("tour.next")) + "</button>"
      + "</div></div>";
    $("#tour-skip").addEventListener("click", () => { S.onboard.phase = "wizard"; S.onboard.step = 0; renderOnboarding(); });
    $("#tour-next").addEventListener("click", () => {
      if (S.onboard.slide < TOUR.length - 1) { S.onboard.slide++; renderOnboarding(); }
      else { S.onboard.phase = "wizard"; S.onboard.step = 0; renderOnboarding(); }
    });
  } else if (S.onboard.phase === "wizard") {
    renderWizard();
  }
}
function wizardSteps() {
  return [
    { kt: "onb.aboutYou", kd: "onb.aboutYouD", render: stepAbout },
    { kt: "onb.goal", kd: "onb.goalD", render: stepGoal },
    { kt: "onb.diet", kd: "onb.dietD", render: stepDiet },
    { kt: "onb.habits", kd: "onb.habitsD", render: stepHabits },
  ];
}
function renderWizard() {
  const b = $("#onb-body");
  const steps = wizardSteps();
  const step = S.onboard.step;
  const total = steps.length;
  b.innerHTML = '<div class="onb-progress">' + Array.from({ length: total }, (x, i) => '<span class="dot' + (i < step ? " done" : "") + (i === step ? " done" : "") + '"></span>').join("") + "</div>"
    + '<div class="onb-card onb-step" id="wiz-card">'
    + '<h2>' + t(steps[step].kt) + "</h2><p class='desc'>" + t(steps[step].kd) + "</p>"
    + '<div id="wiz-fields"></div></div>'
    + '<div class="onb-nav"><button class="onb-skip" id="wiz-skip">' + t("onb.skipStep") + "</button>"
    + '<div class="spacer"></div>'
    + (step > 0 ? '<button class="btn btn-ghost" id="wiz-back">' + t("onb.back") + "</button>" : "")
    + '<button class="btn btn-primary" id="wiz-next">' + (step === total - 1 ? t("onb.finish") : t("onb.next")) + "</button></div>";
  steps[step].render($("#wiz-fields"));
  $("#wiz-skip").addEventListener("click", () => { S.onboard.skipped.push("step" + (step + 1)); advanceWizard(step, true); });
  $("#wiz-next").addEventListener("click", () => advanceWizard(step, false));
  const bk = $("#wiz-back"); if (bk) bk.addEventListener("click", () => { S.onboard.step--; renderOnboarding(); });
}
function advanceWizard(step, skipped) {
  if (!skipped) collectWizard(step);
  const steps = wizardSteps().length;
  if (step < steps - 1) { S.onboard.step++; renderWizard(); }
  else submitOnboarding();
}
function segHTML(group, name, keys, current, big) {
  return '<div class="seg" data-group="' + group + '" data-name="' + name + '">'
    + keys.map(k => {
      const icon = OPT_ICONS[group] && OPT_ICONS[group][k];
      return '<button type="button" value="' + k + '" class="' + (current === k ? "active" : "") + '">'
        + (big && icon ? '<span class="big">' + icon + "</span>" : "") + optLabel(group, k) + "</button>";
    }).join("") + "</div>";
}
function chipHTML(keys, current, labelFn) {
  return '<div class="chip-row" data-multi="1">'
    + keys.map(k => '<span class="chip' + (current.includes(k) ? " active" : "") + '" data-val="' + k + '">' + labelFn(k) + "</span>").join("")
    + "</div>";
}
function stepAbout(root) {
  const p = S.profile.basic_info;
  root.innerHTML =
    '<div class="field"><label>' + t("f.gender") + "</label>" + segHTML("gender", "gender", OPT_KEYS.gender, p.gender || "", true) + "</div>"
    + '<div class="grid grid-3" style="gap:10px">'
    + numField("age", t("f.age"), p.age, t("f.placeholder.age"), 10, 100) + "岁"
    + numField("height_cm", t("f.height"), p.height_cm, t("f.placeholder.height"), 100, 250, "cm")
    + numField("weight_kg", t("f.weight"), p.weight_kg, t("f.placeholder.weight"), 30, 250, "kg")
    + "</div>"
    + '<div class="grid grid-2" style="gap:10px">'
    + '<div class="field"><label>' + t("f.bodyFat") + ' <span class="hint">(' + t("onb.optional") + ")</span></label><div class='input-wrap'><input class='input' id='f-body_fat_pct' type='number' min='3' max='60' value='" + (p.body_fat_pct || "") + "' placeholder='" + t("f.placeholder.bf") + "'><span class='suffix'>%</span></div></div>"
    + '<div class="field"><label>' + t("f.activity") + "</label><div id='act-wrap'></div></div>"
    + "</div>";
  $("#act-wrap").innerHTML = segHTML("activity", "activity_level", OPT_KEYS.activity, p.activity_level || "", true);
  bindSeg(root);
  function numField(key, label, val, ph, min, max, suffix) {
    return '<div class="field"><label>' + label + "</label><div class='input-wrap'><input class='input' id='f-" + key + "' type='number' min='" + min + "' max='" + max + "' value='" + (val == null ? "" : val) + "' placeholder='" + ph + "'" + (suffix ? " style='padding-right:44px'" : "") + "><span class='suffix'>" + (suffix || "") + "</span></div></div>";
  }
}
function stepGoal(root) {
  const dp = S.profile.dietary_preferences;
  const lf = S.profile.lifestyle;
  root.innerHTML =
    '<div class="field"><label>' + t("f.goal") + "</label></div>"
    + segHTML("goal", "goal", OPT_KEYS.goal, dp.goal || "", true) + '<div style="height:8px"></div>'
    + '<div class="field"><label>' + t("f.exFreq") + "</label></div>"
    + segHTML("exfreq", "exercise_frequency", OPT_KEYS.exfreq, lf.exercise_frequency || "", true) + '<div style="height:8px"></div>'
    + '<div class="field"><label>' + t("f.exTypes") + "</label></div>"
    + chipHTML(EX_KEYS, lf.exercise_types || [], exLabel) + '<div style="height:8px"></div>'
    + '<div class="field"><label>' + t("f.exTime") + "</label></div>"
    + segHTML("extime", "exercise_time", OPT_KEYS.extime, lf.exercise_time || "", true);
  bindSeg(root);
  bindChips(root, arr => { lf.exercise_types = arr; });
}
function stepDiet(root) {
  const dp = S.profile.dietary_preferences;
  root.innerHTML =
    '<div class="field"><label>' + t("f.dietType") + "</label></div>"
    + segHTML("diet", "dietary_type", OPT_KEYS.diet, dp.dietary_type || "", true) + '<div style="height:10px"></div>'
    + '<div class="field"><label>' + t("f.allergies") + "</label>" + chipHTML(ALLERGY_KEYS, S.profile.allergies || [], allergyLabel) + "</div>"
    + '<div class="field"><label>' + t("f.dislikes") + "</label><div class='tagbox' id='dislike-box'><input id='dislike-input' placeholder='" + t("f.placeholder.dislike") + "'></div></div>"
    + '<div class="grid grid-3" style="gap:10px">'
    + '<div class="field"><label>' + t("f.breakfast") + '</label><input class="input" type="time" id="mt-breakfast" value="' + (dp.meal_times && dp.meal_times.breakfast || "07:30") + '"></div>'
    + '<div class="field"><label>' + t("f.lunch") + '</label><input class="input" type="time" id="mt-lunch" value="' + (dp.meal_times && dp.meal_times.lunch || "12:00") + '"></div>'
    + '<div class="field"><label>' + t("f.dinner") + '</label><input class="input" type="time" id="mt-dinner" value="' + (dp.meal_times && dp.meal_times.dinner || "18:30") + '"></div>'
    + "</div>"
    + '<div class="field"><label>' + t("f.waterGoal") + ' · <b id="water-val">' + ((S.profile.lifestyle && S.profile.lifestyle.water_goal_ml) || 2000) + " ml</b></label>"
    + '<input class="input" type="range" id="f-water" min="1000" max="4000" step="250" value="' + ((S.profile.lifestyle && S.profile.lifestyle.water_goal_ml) || 2000) + '"></div>';
  bindChips(root, arr => { S.profile.allergies = arr; });
  renderDislikeBox(root);
  $("#f-water").addEventListener("input", () => { $("#water-val").textContent = $("#f-water").value + " ml"; });
  function renderDislikeBox(r) {
    const box = $("#dislike-box");
    const input = $("#dislike-input");
    const list = dp.disliked_foods || (dp.disliked_foods = []);
    box.innerHTML = "";
    list.forEach((food, i) => {
      const tag = document.createElement("span");
      tag.className = "tag";
      tag.innerHTML = esc(food) + '<span class="x">✕</span>';
      tag.querySelector(".x").addEventListener("click", () => { list.splice(i, 1); renderDislikeBox(r); });
      box.appendChild(tag);
    });
    const ni = document.createElement("input");
    ni.placeholder = t("f.placeholder.dislike");
    box.appendChild(ni);
    ni.addEventListener("keydown", e => {
      if (e.key === "Enter" && ni.value.trim()) {
        e.preventDefault();
        list.push(ni.value.trim());
        renderDislikeBox(r);
      }
    });
  }
}
function stepHabits(root) {
  const lf = S.profile.lifestyle;
  root.innerHTML =
    '<div class="grid grid-2" style="gap:10px">'
    + '<div class="field"><label>' + t("f.sleep") + '</label><div class="input-wrap"><input class="input" id="f-sleep" type="number" min="3" max="14" step="0.5" value="' + (lf.sleep_hours == null ? "" : lf.sleep_hours) + '" placeholder="' + t("f.placeholder.sleep") + '"><span class="suffix">h</span></div></div>'
    + '<div class="field"><label>' + t("f.eatOut") + "</label><div id='eat-wrap'></div></div>"
    + "</div>"
    + '<div class="field" style="margin-top:4px"><label>' + t("f.health") + "</label>" + chipHTML(HEALTH_KEYS, S.profile.health_conditions || [], healthLabel) + "</div>"
    + '<div class="row-between card" style="margin-top:8px;box-shadow:none;padding:12px 14px"><div><b style="font-size:14px">' + t("f.smokingY") + "</b></div><button class='toggle" + (lf.smoking ? " on" : "") + "' id='tg-smoke' type='button'></button></div>"
    + '<div class="row-between card" style="margin-top:8px;box-shadow:none;padding:12px 14px"><div><b style="font-size:14px">' + t("f.alcoholY") + "</b></div><button class='toggle" + (lf.alcohol ? " on" : "") + "' id='tg-drink' type='button'></button></div>";
  $("#eat-wrap").innerHTML = segHTML("eatout", "eat_out_freq", OPT_KEYS.eatout, lf.eat_out_freq || "", true);
  bindSeg(root);
  bindChips(root, arr => { S.profile.health_conditions = arr; });
  const tg = (id, key) => { const el = $(id); el.addEventListener("click", () => { el.classList.toggle("on"); lf[key] = el.classList.contains("on"); }); };
  tg("#tg-smoke", "smoking"); tg("#tg-drink", "alcohol");
}
function bindSeg(root) {
  $$(".seg", root).forEach(seg => {
    seg.addEventListener("click", e => {
      const btn = e.target.closest("button");
      if (!btn) return;
      $$("button", seg).forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
    });
  });
}
function bindChips(root, onUpdate) {
  $$(".chip-row[data-multi='1']", root).forEach(row => {
    row.addEventListener("click", e => {
      const chip = e.target.closest(".chip");
      if (!chip) return;
      chip.classList.toggle("active");
      const vals = $$(".chip.active", row).map(c => c.dataset.val);
      onUpdate(vals);
    });
  });
}
function collectWizard(step) {
  const p = S.profile;
  if (step === 0) {
    const act = $(".seg[data-name='activity_level'] button.active");
    const gen = $(".seg[data-name='gender'] button.active");
    p.basic_info.gender = gen ? gen.value : "";
    p.basic_info.age = num($("#f-age").value, null);
    p.basic_info.height_cm = num($("#f-height_cm").value, null);
    p.basic_info.weight_kg = num($("#f-weight_kg").value, null);
    p.basic_info.body_fat_pct = $("#f-body_fat_pct").value ? num($("#f-body_fat_pct").value, null) : null;
    p.basic_info.activity_level = act ? act.value : "";
  } else if (step === 1) {
    const goal = $(".seg[data-name='goal'] button.active");
    const fr = $(".seg[data-name='exercise_frequency'] button.active");
    const tm = $(".seg[data-name='exercise_time'] button.active");
    p.dietary_preferences.goal = goal ? goal.value : "";
    p.lifestyle.exercise_frequency = fr ? fr.value : "";
    p.lifestyle.exercise_time = tm ? tm.value : "";
  } else if (step === 2) {
    const dt = $(".seg[data-name='dietary_type'] button.active");
    p.dietary_preferences.dietary_type = dt ? dt.value : "";
    p.dietary_preferences.meal_times = {
      breakfast: numVal("#mt-breakfast", "07:30"),
      lunch: numVal("#mt-lunch", "12:00"),
      dinner: numVal("#mt-dinner", "18:30"),
    };
    p.lifestyle.water_goal_ml = num($("#f-water").value, 2000);
  } else if (step === 3) {
    const eo = $(".seg[data-name='eat_out_freq'] button.active");
    p.lifestyle.eat_out_freq = eo ? eo.value : "";
    p.lifestyle.sleep_hours = $("#f-sleep").value ? num($("#f-sleep").value, null) : null;
  }
  function numVal(sel, dflt) { const el = $(sel); return el ? el.value || dflt : dflt; }
}
async function submitOnboarding() {
  const btn = $("#wiz-next");
  if (btn) { btn.disabled = true; btn.textContent = t("common.loading"); }
  try {
    const d = await api("/api/me/onboarding", { method: "POST", body: { profile: S.profile, skipped: S.onboard.skipped } });
    S.user = d.user; S.profile = d.profile; S.targets = d.targets;
    S.user.onboarding_done = true;
    S.onboard = { phase: "tour", slide: 0, step: 0, skipped: [] };
    showPage("app");
  } catch (e) {
    toast(e.detail || t("err.unknown"));
    if (btn) { btn.disabled = false; btn.textContent = t("onb.finish"); }
  }
}
/* ---------------- shell ---------------- */
const VIEW_META = [
  { id: "home", icon: "🏠", key: "nav.home" },
  { id: "chat", icon: "💬", key: "nav.chat" },
  { id: "discover", icon: "🧭", key: "nav.discover" },
  { id: "me", icon: "👤", key: "nav.me" },
];
function renderShell() {
  const appEl = $("#page-app");
  const top = $("#topbar");
  top.innerHTML = '<div class="brand" data-go="home">' + logoMark(34) + '<span class="brand-name">Vitala</span></div>'
    + '<nav class="topnav">' + VIEW_META.map(v =>
      '<button data-view="' + v.id + '" class="' + (S.view === v.id ? "active" : "") + '">' + t(v.key) + "</button>").join("") + "</nav>"
    + '<div class="top-actions">'
    + '<button class="icon-btn" id="t-lang" title="Language">' + (getLang() === "zh" ? "EN" : "中文") + "</button>"
    + '<button class="icon-btn" id="t-theme" title="Theme">' + svgIcon('palette', 18) + '</button>'
    + '<button class="icon-btn" id="t-user" data-go="me">' + avatarHTML((S.user && S.user.avatar) || { type: "initials" }, 34, false) + "</button>"
    + "</div>";
  const nav = $("#bottomnav");
  nav.innerHTML = VIEW_META.map(v =>
    '<button data-view="' + v.id + '" class="' + (S.view === v.id ? "active" : "") + '"><span class="ico">' + svgIcon(v.id) + "</span>" + t(v.key) + "</button>").join("");
  $$("[data-view]", appEl).forEach(b => b.addEventListener("click", () => switchView(b.getAttribute("data-view"))));
  $$("[data-go]", appEl).forEach(b => b.addEventListener("click", () => {
    const g = b.getAttribute("data-go");
    if (g === "home") switchView("home");
    if (g === "me") switchView("me");
  }));
  $("#t-lang").addEventListener("click", () => applyLanguage(getLang() === "zh" ? "en" : "zh"));
  const order = ["light", "fresh", "dark"];
  $("#t-theme").addEventListener("click", () => {
    const cur = document.documentElement.getAttribute("data-theme") || "light";
    applyTheme(order[(order.indexOf(cur) + 1) % order.length]);
  });
  $("#t-user").addEventListener("click", () => switchView("me"));
  const main = $("#main");
  main.classList.toggle("chat-mode", S.view === "chat");
  if (S.view === "home") renderHome();
  else if (S.view === "chat") renderChat();
  else if (S.view === "discover") renderDiscover();
  else if (S.view === "me") renderMe();
  else if (S.view === "settings") renderSettings();
  translateStatic();
}

async function refreshMe() {
  try {
    const d = await api("/api/me");
    S.user = d.user; S.profile = d.profile; S.targets = d.targets;
  } catch (e) { /* ignore */ }
}

/* ---------------- home ---------------- */
function greeting() {
  const h = new Date().getHours();
  const name = (S.user && (S.user.display_name || S.user.username)) || "";
  if (h < 5) return t("home.hello", { name });
  if (h < 11) return t("home.morning", { name });
  if (h < 18) return t("home.afternoon", { name });
  return t("home.evening", { name });
}
function tracking() {
  const tr = (S.profile && S.profile.tracking) || {};
  const today = tr.date === todayStr();
  const meals = today ? tr.meals || [] : [];
  const waters = today ? tr.water_logs || [] : [];
  const workouts = today ? tr.workouts || [] : [];
  const sum = (arr, k) => arr.reduce((a, x) => a + (num(x[k], 0)), 0);
  const totals = { cal: sum(meals, "calories"), pro: sum(meals, "protein_g"), fat: sum(meals, "fat_g"), carb: sum(meals, "carbs_g"), water: sum(waters, "ml") };
  return { meals, waters, workouts, totals };
}
function profileCompleteness() {
  const p = (S.profile || {});
  const checks = [
    p.basic_info && p.basic_info.gender, p.basic_info && p.basic_info.age,
    p.basic_info && p.basic_info.height_cm, p.basic_info && p.basic_info.weight_kg,
    p.dietary_preferences && p.dietary_preferences.goal,
    p.basic_info && p.basic_info.activity_level,
    p.dietary_preferences && p.dietary_preferences.dietary_type,
    p.lifestyle && p.lifestyle.sleep_hours,
    p.lifestyle && p.lifestyle.water_goal_ml,
  ];
  const filled = checks.filter(Boolean).length;
  return Math.round(filled / checks.length * 100);
}
function renderHome() {
  const main = $("#main");
  const tgt = S.targets || {};
  const tr = tracking();
  const cal = tgt.calories || 2000;
  const pct = Math.min(100, Math.round(tr.totals.cal / cal * 100));
  const remain = Math.max(0, cal - tr.totals.cal);
  const waterGoal = (S.profile && S.profile.lifestyle && S.profile.lifestyle.water_goal_ml) || 2000;
  const waterPct = Math.min(100, Math.round(tr.totals.water / waterGoal * 100));
  const comp = profileCompleteness();
  const macro = (name, cls, now, tgtv, unit) => {
    const tp = Math.min(100, Math.round((now / (tgtv || 1)) * 100));
    return '<div class="macro-item"><div class="macro-row"><span>' + name + '</span><b>' + Math.round(now) + " / " + (tgtv || 0) + " " + unit + "</b></div>"
      + '<div class="macro-bar"><i class="' + cls + '" style="width:' + tp + '%"></i></div></div>';
  };
  const tip = comp < 80 ? '<div class="tip-card section-gap">💡<div><b>' + t("home.incomplete") + '</b><div class="mt-1"><button class="btn btn-sm btn-soft" data-act="goprofile">' + t("home.goEdit") + "</button></div></div></div>" : "";
  const mealsHtml = tr.meals.length ? tr.meals.slice(-5).reverse().map(m =>
    '<div class="tl-item"><div class="ico">🍽️</div><div class="info"><div class="name">' + esc(m.name || m.meal_type || "") + '</div><div class="meta">' + esc(m.meal_type ? mealTypeLabel(m.meal_type) : "") + (m.t ? " · " + m.t : "") + "</div></div><div class='cal'>" + (num(m.calories, 0) ? num(m.calories, 0) + " kcal" : "") + "</div></div>").join("")
    : '<div class="empty-note">' + t("home.noMeal") + "</div>";
  const wkHtml = tr.workouts.length ? tr.workouts.slice(-4).reverse().map(w =>
    '<div class="tl-item"><div class="ico">💪</div><div class="info"><div class="name">' + esc(w.name || t("track.workout")) + '</div><div class="meta">' + (w.minutes ? w.minutes + " " + t("unit.min") : "") + (w.t ? " · " + w.t : "") + "</div></div></div>").join("")
    : '<div class="empty-note">' + t("home.noWorkout") + "</div>";
  main.innerHTML = '<div class="page-in">'
    + '<div class="hero-strip"><div><h1 class="hero-title">' + greeting() + "</h1><p class='hero-sub'>" + t("home.subReady") + "</p></div>"
    + '<span data-act="goprofile" style="cursor:pointer">' + avatarHTML((S.user && S.user.avatar) || { type: "initials" }, 48, true) + "</span></div>"
    + tip
    + '<div class="cal-hero mt-2">'
    + '<div class="cal-card"><div class="cal-top"><span class="cal-label">' + t("home.calTarget") + "</span><span style='opacity:.9;font-size:12px'>" + (S.profile && S.profile.dietary_preferences && S.profile.dietary_preferences.goal ? optLabel("goal", S.profile.dietary_preferences.goal) : "") + "</span></div>"
    + '<div class="cal-main"><span class="cal-num">' + remain + '</span><span class="cal-unit">kcal</span></div>'
    + '<div class="cal-foot">' + t("home.remain") + " · " + t("home.consumed") + " " + Math.round(tr.totals.cal) + " / " + cal + " kcal</div>"
    + "</div>"
    + '<div class="macro-card"><div class="card-title">' + t("home.todayLog") + "</div>"
    + macro(t("home.protein"), "mb-p", tr.totals.pro, tgt.protein_g, "g")
    + macro(t("home.fat"), "mb-f", tr.totals.fat, tgt.fat_g, "g")
    + macro(t("home.carbs"), "mb-c", tr.totals.carb, tgt.carbs_g, "g")
    + '<div class="macro-legend"><span><i style="background:var(--brand)"></i>' + t("home.protein") + "</span><span><i style='background:var(--accent)'></i>" + t("home.fat") + "</span><span><i style='background:#d69a3c'></i>" + t("home.carbs") + "</span></div>"
    + "</div></div>"
    + '<div class="stat-grid section-gap">'
    + mini("🔥", tgt.bmr || "—", t("home.bmr")) + mini("⚡", tgt.tdee || "—", t("home.tdee")) + mini("📐", tgt.bmi || "—", t("home.bmi"))
    + "</div>"
    + '<div class="grid section-gap" style="grid-template-columns:1fr 1fr">'
    + '<div class="card water-card"><div class="water-ring" style="--p:' + waterPct + '"><div>💧</div></div><div class="water-info"><div class="t">' + tr.totals.water + " / " + waterGoal + ' ml</div><div class="s">' + t("home.waterTarget", { n: waterGoal }) + "</div>"
    + '<div class="row mt-1"><button class="btn btn-sm btn-soft" data-act="water">' + t("home.addWater") + "</button><button class='btn btn-sm btn-ghost' data-act='customwater'>" + t("common.optional") + "</button></div></div></div>"
    + '<div class="card"><div class="card-title">' + t("home.tipTitle") + '<span style="text-transform:none;letter-spacing:0">✨</span></div>'
    + '<p style="margin:0;font-size:13.5px;color:var(--text-2)">' + dailyTip() + "</p></div>"
    + "</div>"
    + '<div class="grid section-gap" style="grid-template-columns:1.15fr .85fr">'
    + '<div class="card"><div class="card-title">' + t("home.meals") + '<span class="more" data-act="addmeal">+ ' + t("home.addMeal") + "</span></div>" + mealsHtml + "</div>"
    + '<div class="card"><div class="card-title">' + t("home.workouts") + '<span class="more" data-act="addworkout">+ ' + t("home.addWorkout") + "</span></div>" + wkHtml + "</div>"
    + "</div>"
    + '<div class="section-gap"><div class="card-title" style="text-transform:none;font-size:14px;color:var(--text);letter-spacing:0">' + t("home.quickAsk") + "</div>"
    + '<div class="quickask-grid">'
    + ["chat.suggest1", "chat.suggest2", "chat.suggest3", "chat.suggest4"].map(k => '<button class="qa-btn" data-q="' + esc(t(k)) + '">' + t(k) + "</button>").join("")
    + "</div></div>"
    + "</div>";
  main.querySelectorAll("[data-act]").forEach(b => {
    b.addEventListener("click", async () => {
      const act = b.getAttribute("data-act");
      if (act === "goprofile") switchView("me");
      if (act === "water") { await logEntry({ type: "water", ml: 250 }); toast(t("home.added")); renderHome(); }
      if (act === "customwater") openWaterModal();
      if (act === "addmeal") openMealModal();
      if (act === "addworkout") openWorkoutModal();
    });
  });
  main.querySelectorAll("[data-q]").forEach(b => b.addEventListener("click", () => goChat(b.getAttribute("data-q"))));
  function mini(ico, v, l) { return '<div class="stat-mini"><div class="v">' + v + "</div><div class='l'>" + l + "</div></div>"; }
}
function dailyTip() {
  const tips = [
    "先吃蔬菜和蛋白质，再吃主食，血糖更平稳",
    "每天 2000 ml 水分成 6-8 次喝完，别等渴了再喝",
    "蛋白质均匀分配到三餐，比一顿吃光更利于增肌",
    "晚餐别太晚，睡前 3 小时吃完更利于睡眠",
    "记录每一餐，比任何节食方法都更有效",
    "吃饭慢一点，大脑需要约 20 分钟感受饱腹",
  ];
  if (getLang() === "en") {
    return "Eat vegetables & protein first, then carbs — steadier blood sugar. Drink water steadily through the day, not all at once.";
  }
  return tips[new Date().getDate() % tips.length];
}
async function logEntry(body) {
  const d = await api("/api/me/tracking", { method: "POST", body });
  S.profile = d.profile; S.targets = d.targets;
}
async function undoLog(type) {
  const d = await api("/api/me/tracking?type=" + type, { method: "DELETE" });
  S.profile = d.profile; S.targets = d.targets;
  renderHome();
}
function openWaterModal() {
  const m = showModal('<h3>💧 ' + t("track.water") + '</h3><p class="sub">' + t("home.waterTarget", { n: (S.profile.lifestyle && S.profile.lifestyle.water_goal_ml) || 2000 }) + "</p>"
    + '<div class="grid" style="grid-template-columns:repeat(3,1fr)">' + [150, 250, 350, 500, 750, 1000].map(v => '<button class="btn btn-ghost" data-ml="' + v + '">' + v + ' ml</button>').join("") + "</div>"
    + '<div class="row mt-2"><button class="btn btn-ghost grow" data-close>取消</button></div>');
  m.querySelectorAll("[data-ml]").forEach(b => b.addEventListener("click", async () => {
    closeModal(); await logEntry({ type: "water", ml: num(b.getAttribute("data-ml"), 250) }); toast(t("home.added")); renderHome();
  }));
  m.querySelectorAll("[data-close]").forEach(b => b.addEventListener("click", closeModal));
}
function openMealModal() {
  const m = showModal('<h3>🍽️ ' + t("home.addMeal") + '</h3><p class="sub">' + t("home.todayLog") + "</p>"
    + '<div class="field"><label>' + t("f.mealFreq") + '</label><div class="seg" data-mealtype>' + ["breakfast", "lunch", "dinner", "snack"].map((k, i) => '<button type="button" value="' + k + '" class="' + (i === 0 ? "active" : "") + '">' + (i === 0 ? "🌅" : i === 1 ? "☀️" : i === 2 ? "🌙" : "🍪") + " " + mealTypeLabel(k) + "</button>").join("") + "</div></div>"
    + '<div class="field"><label>' + t("home.addMeal") + " - " + t("common.optional") + '</label><input class="input" id="m-name" placeholder="' + (getLang() === "zh" ? "例如：鸡胸肉沙拉" : "e.g. Grilled chicken salad") + '"></div>'
    + '<div class="grid grid-2" style="gap:10px">'
    + '<div class="field"><label>kcal</label><input class="input" id="m-cal" type="number" placeholder="300"></div>'
    + '<div class="field"><label>' + t("dis.protein") + ' (g)</label><input class="input" id="m-pro" type="number" placeholder="25"></div>'
    + '<div class="field"><label>' + t("dis.fat") + ' (g)</label><input class="input" id="m-fat" type="number" placeholder="10"></div>'
    + '<div class="field"><label>' + t("dis.carbs") + ' (g)</label><input class="input" id="m-carb" type="number" placeholder="30"></div>'
    + "</div>"
    + '<div class="row"><button class="btn btn-ghost grow" data-close>' + t("common.cancel") + '</button><button class="btn btn-primary grow" id="m-save">' + t("common.save") + "</button></div>");
  m.querySelectorAll("[data-mealtype] button").forEach(b => b.addEventListener("click", () => { m.querySelectorAll("[data-mealtype] button").forEach(x => x.classList.remove("active")); b.classList.add("active"); }));
  m.querySelectorAll("[data-close]").forEach(b => b.addEventListener("click", closeModal));
  $("#m-save").addEventListener("click", async () => {
    const type = $("[data-mealtype] button.active", m).value;
    const name = $("#m-name", m).value.trim() || mealTypeLabel(type);
    await logEntry({ type: "meal", meal_type: type, name, calories: num($("#m-cal", m).value, 0), protein_g: num($("#m-pro", m).value, 0), fat_g: num($("#m-fat", m).value, 0), carbs_g: num($("#m-carb", m).value, 0) });
    closeModal(); toast(t("home.added")); renderHome();
  });
}
function openWorkoutModal() {
  const m = showModal('<h3>💪 ' + t("home.addWorkout") + '</h3><p class="sub">' + t("home.todayLog") + "</p>"
    + '<div class="field"><label>' + (getLang() === "zh" ? "运动名称" : "Workout name") + '</label><div class="chip-row" id="wk-chips"></div></div>'
    + '<div class="field"><label>' + t("unit.min") + '</label><div class="seg" data-wkmin>' + [15, 30, 45, 60, 90].map((v, i) => '<button type="button" value="' + v + '" class="' + (i === 2 ? "active" : "") + '">' + v + "</button>").join("") + "</div></div>"
    + '<div class="row"><button class="btn btn-ghost grow" data-close>' + t("common.cancel") + '</button><button class="btn btn-primary grow" id="wk-save">' + t("common.save") + "</button></div>");
  const box = $("#wk-chips", m);
  EX_KEYS.forEach((k, i) => {
    const c = document.createElement("span");
    c.className = "chip" + (i === 3 ? " active" : "");
    c.textContent = exLabel(k);
    c.dataset.val = k;
    c.addEventListener("click", () => { box.querySelectorAll(".chip").forEach(x => x.classList.remove("active")); c.classList.add("active"); });
    box.appendChild(c);
  });
  m.querySelectorAll("[data-close]").forEach(b => b.addEventListener("click", closeModal));
  $("#wk-save", m).addEventListener("click", async () => {
    const act = box.querySelector(".chip.active");
    const minutes = num($("[data-wkmin] button.active", m).value, 30);
    await logEntry({ type: "workout", name: act ? exLabel(act.dataset.val) : t("track.workout"), minutes });
    closeModal(); toast(t("home.added")); renderHome();
  });
}

/* ---------------- chat ---------------- */
function chatKey() { return "vitala_chat_" + (S.user ? S.user.id : "guest"); }
function renderChat() {
  const main = $("#main");
  const msgs = S.chat;
  main.innerHTML = '<div class="chat-layout">'
    + '<aside class="chat-side"><div class="cs-title">' + t("home.quickAsk") + "</div>"
    + ["chat.suggest1", "chat.suggest2", "chat.suggest3", "chat.suggest4"].map(k => '<button class="cs-item" data-q="' + esc(t(k)) + '">' + t(k) + "</button>").join("")
    + '<div class="cs-title">' + t("chat.title") + "</div>"
    + '<div class="cs-item muted" style="font-size:11.5px;line-height:1.6;color:var(--muted)">' + t("chat.disclaimer") + "</div>"
    + "</aside>"
    + '<div class="chat-main"><div class="chat-head"><div><div class="ttl">💬 ' + t("chat.title") + '</div><div class="sub">' + t("chat.sub") + "</div></div>"
    + '<button class="btn btn-sm btn-ghost" id="chat-clear">' + t("chat.clear") + "</button></div>"
    + '<div class="chat-scroll" id="chat-scroll"></div>'
    + '<div class="chat-inputbar"><textarea id="chat-input" rows="1" placeholder="' + t("chat.placeholder") + '"></textarea>'
    + '<button class="btn btn-primary" id="chat-send" style="border-radius:14px;padding:0 18px">' + t("chat.send") + "</button></div>"
    + '<div class="chat-disclaimer">' + t("chat.disclaimer") + "</div>"
    + "</div></div>";
  const scroll = $("#chat-scroll");
  if (!msgs.length) {
    scroll.innerHTML = '<div class="chat-empty"><div class="big">🥗</div><h2>' + t("chat.title") + "</h2>"
      + '<p style="max-width:360px;margin:0 0 14px">' + t("chat.sub") + "</p>"
      + '<div class="quickask-grid" style="max-width:420px;width:100%">'
      + ["chat.suggest1", "chat.suggest2", "chat.suggest3", "chat.suggest4"].map(k => '<button class="qa-btn" data-q="' + esc(t(k)) + '">' + t(k) + "</button>").join("")
      + "</div></div>";
  } else {
    msgs.forEach(msg => appendBubble(msg, false));
  }
  scroll.scrollTop = scroll.scrollHeight;
  bindChatEvents();
  if (S.pendingQuestion) {
    const q = S.pendingQuestion; S.pendingQuestion = null;
    setTimeout(() => sendChat(q), 120);
  }
}
function bindChatEvents() {
  const input = $("#chat-input");
  const send = $("#chat-send");
  const sendNow = () => { const q = input.value.trim(); if (q) { input.value = ""; autoGrow(); sendChat(q); } };
  send.addEventListener("click", sendNow);
  input.addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendNow(); } });
  input.addEventListener("input", autoGrow);
  const cc = $("#chat-clear");
  if (cc) cc.addEventListener("click", () => confirmBox(t("chat.clearConfirm"), () => { S.chat = []; saveChat(); renderChat(); }));
  $("#main").querySelectorAll("[data-q]").forEach(b => b.addEventListener("click", () => {
    const q = b.getAttribute("data-q");
    if (q.startsWith(t("chat.suggest1")) || q.startsWith(t("chat.suggest2")) || q.startsWith(t("chat.suggest3")) || q.startsWith(t("chat.suggest4"))) {
      input.value = q; sendNow();
    } else sendChat(q);
  }));
  function autoGrow() { input.style.height = "auto"; input.style.height = Math.min(input.scrollHeight, 120) + "px"; }
}
function appendBubble(msg, animate) {
  const scroll = $("#chat-scroll");
  const div = document.createElement("div");
  div.className = "bubble " + msg.role;
  const av = msg.role === "bot" ? "V" : ((S.user && (S.user.display_name || S.user.username)[0]) || "U");
  let html = "";
  if (msg.role === "bot") {
    html = '<div class="av">V</div><div><div class="bbl markdown">' + md2html(msg.content) + "</div>";
    if (msg.sources && msg.sources.length) {
      html += '<div class="src-row">' + msg.sources.slice(0, 4).map(s => '<span class="src-chip">📄 ' + esc(s.title) + "</span>").join("") + "</div>";
    }
    html += "</div>";
  } else {
    html = '<div class="av">' + esc(av) + "</div><div><div class='bbl'>" + esc(msg.content) + "</div></div>";
  }
  div.innerHTML = html;
  scroll.appendChild(div);
  scroll.scrollTop = scroll.scrollHeight;
  return div;
}
function showTyping() {
  const scroll = $("#chat-scroll");
  const div = document.createElement("div");
  div.className = "bubble bot";
  div.id = "typing";
  div.innerHTML = '<div class="av">V</div><div class="bbl"><div class="typing"><span></span><span></span><span></span></div></div>';
  scroll.appendChild(div);
  scroll.scrollTop = scroll.scrollHeight;
}
function removeTyping() { const el = $("#typing"); if (el) el.remove(); }
function saveChat() { try { localStorage.setItem(chatKey(), JSON.stringify(S.chat.slice(-60))); } catch (e) {} }
const GREET_RE = /^(你好|您好|嗨|哈喽|hello|hi|hey|hiya|在吗|早上好|中午好|下午好|晚上好|good\s?(morning|afternoon|evening))/i;
const SRC_MARK = "\n[[SRC]]";

function chatHistory() { return S.chat.slice(-10).map(m => ({ role: m.role, content: m.content })); }

async function sendChat(text) {
  S.chat.push({ role: "user", content: text });
  appendBubble({ role: "user", content: text }, true);
  const clean = text.trim().replace(/[!！?？。.,，~～\s]+$/, "");
  // 问候语：不调大模型、不联网检索，直接本地秒回
  if (clean.length <= 14 && GREET_RE.test(clean)) {
    const bot = { role: "bot", content: t("chat.greet"), sources: [] };
    await new Promise(r => setTimeout(r, 220));
    S.chat.push(bot);
    appendBubble(bot, true);
    saveChat();
    return;
  }
  showTyping();
  try {
    await streamChat(text);
  } catch (e) {
    removeTyping();
    try {
      const d = await api("/api/chat", { method: "POST", body: { query: text, chat_history: chatHistory(), use_rewrite: true } });
      const bot = { role: "bot", content: d.answer || "", sources: d.sources || [] };
      S.chat.push(bot);
      appendBubble(bot, true);
      saveChat();
    } catch (e2) {
      appendBubble({ role: "bot", content: t("chat.error") + "：" + (e2.detail || "") }, true);
    }
  }
}

async function streamChat(text) {
  const headers = { "Content-Type": "application/json" };
  if (S.token) headers["Authorization"] = "Bearer " + S.token;
  const res = await fetch("/api/chat/stream", { method: "POST", headers, body: JSON.stringify({ query: text, chat_history: chatHistory(), use_rewrite: true }) });
  if (!res.ok) {
    const err = {};
    try { const j = await res.json(); err.detail = j.detail; } catch (x) { err.detail = res.statusText; }
    throw err;
  }
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  removeTyping();
  const wrap = document.createElement("div");
  wrap.className = "bubble bot";
  wrap.innerHTML = '<div class="av">V</div><div><div class="bbl md-live"></div></div>';
  const scroll = $("#chat-scroll");
  scroll.appendChild(wrap);
  const bbl = wrap.querySelector(".md-live");
  let buf = "";
  let plain = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const idx = buf.indexOf(SRC_MARK);
    plain = idx >= 0 ? buf.slice(0, idx) : buf;
    bbl.textContent = plain;
    scroll.scrollTop = scroll.scrollHeight;
  }
  let answer = buf;
  let sources = [];
  const idx = buf.indexOf(SRC_MARK);
  if (idx >= 0) {
    answer = buf.slice(0, idx);
    try { sources = JSON.parse(buf.slice(idx + SRC_MARK.length)); } catch (x) { sources = []; }
  }
  let srcHtml = "";
  if (sources && sources.length) {
    srcHtml = '<div class="src-row">' + sources.slice(0, 4).map(s => '<span class="src-chip">📄 ' + esc(s.title) + "</span>").join("") + "</div>";
  }
  bbl.innerHTML = md2html(answer) + srcHtml;
  const bot = { role: "bot", content: answer, sources: sources || [] };
  S.chat.push(bot);
  saveChat();
  scroll.scrollTop = scroll.scrollHeight;
}

/* ---------------- discover ---------------- */
const S_DIS = { tab: "recipes", cat: "all", q: "" };
async function renderDiscover() {
  const main = $("#main");
  main.innerHTML = '<div class="page-in">'
    + '<div class="page-head"><div><h1>' + t("dis.title") + "</h1><p>" + t("dis.sub") + "</p></div>"
    + '<div class="searchbar"><span class="s-ico">🔍</span><input class="input" id="dis-q" placeholder="' + t("dis.search") + '"></div></div>'
    + '<div class="dis-tabs">'
    + '<button class="dis-tab' + (S_DIS.tab === "recipes" ? " active" : "") + '" data-tab="recipes">🍳 ' + t("dis.tabRecipes") + "</button>"
    + '<button class="dis-tab' + (S_DIS.tab === "knowledge" ? " active" : "") + '" data-tab="knowledge">📚 ' + t("dis.tabKnowledge") + "</button>"
    + "</div>"
    + '<div id="dis-filter"></div>'
    + '<div id="dis-list" class="mt-1"><div class="empty-note">' + t("common.loading") + "</div></div>"
    + "</div>";
  $("#dis-q").addEventListener("input", () => { S_DIS.q = $("#dis-q").value.trim().toLowerCase(); renderDisList(); });
  $$(".dis-tab", main).forEach(b => b.addEventListener("click", () => { S_DIS.tab = b.getAttribute("data-tab"); S_DIS.cat = "all"; renderDiscover(); }));
  if (!S.catalog) {
    try { S.catalog = await api("/api/catalog"); } catch (e) { toast(e.detail || t("err.unknown")); S.catalog = { recipes: [], knowledge: [] }; }
  }
  renderDisFilter();
  renderDisList();
}
function renderDisFilter() {
  const host = $("#dis-filter");
  if (S_DIS.tab === "recipes") {
    host.innerHTML = '<div class="chip-row">' + ["all", "减脂餐", "增肌餐", "维持餐"].map(c =>
      '<span class="chip' + (S_DIS.cat === c ? " active" : "") + '" data-cat="' + c + '">' + (c === "all" ? t("dis.all") : c) + "</span>").join("") + "</div>";
    $$("#dis-filter .chip").forEach(ch => ch.addEventListener("click", () => { S_DIS.cat = ch.getAttribute("data-cat"); renderDisFilter(); renderDisList(); }));
  } else host.innerHTML = "";
}
function renderDisList() {
  const list = $("#dis-list");
  if (!list) return;
  const data = S.catalog || { recipes: [], knowledge: [] };
  if (S_DIS.tab === "recipes") {
    let items = data.recipes || [];
    if (S_DIS.cat !== "all") items = items.filter(r => r.category === S_DIS.cat);
    if (S_DIS.q) items = items.filter(r => (r.name + " " + (r.tags || []).join(" ")).toLowerCase().includes(S_DIS.q));
    if (!items.length) { list.innerHTML = '<div class="empty-note">' + t("dis.empty") + "</div>"; return; }
    list.innerHTML = '<div class="recipe-grid">' + items.map(r => {
      const ico = r.category === "减脂餐" ? "🥗" : r.category === "增肌餐" ? "🍗" : "🥘";
      const tags = (r.tags || []).slice(0, 2).map(tg => '<span class="pill">' + esc(tg) + "</span>").join("");
      return '<div class="recipe-card" data-id="' + esc(r.id) + '">'
        + '<div class="recipe-thumb">' + ico + "</div>"
        + '<div class="recipe-body"><h4>' + esc(r.name) + "</h4>"
        + '<div class="recipe-meta"><span class="pill cat">' + esc(r.category) + "</span>" + (r.meal_type ? '<span class="pill">' + mealTypeLabel(mealKey(r.meal_type)) + "</span>" : "") + tags + "</div>"
        + '<div class="recipe-nums"><span><b>' + (r.calories || 0) + "</b> kcal</span>" + (r.cook_time ? '<span>⏱ ' + r.cook_time + ' ' + t("unit.min") + "</span>" : "") + "</div>"
        + "</div></div>";
    }).join("") + "</div>";
    $$(".recipe-card", list).forEach(card => card.addEventListener("click", () => openRecipe(card.getAttribute("data-id"))));
  } else {
    let items = data.knowledge || [];
    if (S_DIS.q) items = items.filter(k => (k.title + " " + (k.summary || "")).toLowerCase().includes(S_DIS.q));
    if (!items.length) { list.innerHTML = '<div class="empty-note">' + t("dis.empty") + "</div>"; return; }
    list.innerHTML = '<div class="know-list">' + items.map(k =>
      '<div class="know-card" data-id="' + esc(k.id) + '"><h4>📄 ' + esc(k.title) + '</h4><p>' + esc(k.summary) + "…</p></div>").join("") + "</div>";
    $$(".know-card", list).forEach(card => card.addEventListener("click", () => openKnowledge(card.getAttribute("data-id"))));
  }
}
async function openRecipe(id) {
  try {
    const r = await api("/api/catalog/recipe/" + id);
    const m = showModal('<h3>' + esc(r.name) + '</h3>' + (r.description ? '<p class="sub">' + esc(r.description) + "</p>" : "") + '<div class="row" style="gap:6px;flex-wrap:wrap">'
      + '<span class="pill cat">' + esc(r.category) + "</span>" + (r.meal_type ? '<span class="pill">' + mealTypeLabel(mealKey(r.meal_type)) + "</span>" : "") + (r.cook_time ? '<span class="pill">⏱ ' + r.cook_time + ' ' + t("unit.min") + "</span>" : "") + "</div>"
      + '<div class="stat-grid mt-1" style="grid-template-columns:repeat(4,1fr)">'
      + '<div class="stat-mini" style="padding:9px"><div class="v">' + (r.calories || 0) + '</div><div class="l">kcal</div></div>'
      + '<div class="stat-mini" style="padding:9px"><div class="v">' + (r.protein || 0) + '</div><div class="l">' + t("dis.protein") + "</div></div>"
      + '<div class="stat-mini" style="padding:9px"><div class="v">' + (r.fat || 0) + '</div><div class="l">' + t("dis.fat") + "</div></div>"
      + '<div class="stat-mini" style="padding:9px"><div class="v">' + (r.carbs || 0) + '</div><div class="l">' + t("dis.carbs") + "</div></div>"
      + "</div>"
      + '<h4 class="mt-2">🧺 ' + t("dis.ingredients") + '</h4><ul class="small" style="margin:6px 0;padding-left:18px;color:var(--text-2)">'
      + (r.ingredients || []).map(i => "<li>" + esc(i.name) + " · " + i.amount + (i.unit || "") + "</li>").join("") + "</ul>"
      + '<h4>👩‍🍳 ' + t("dis.steps") + '</h4><ol class="small" style="margin:6px 0;padding-left:18px;color:var(--text-2)">'
      + (r.steps || []).map(s => "<li>" + esc(s) + "</li>").join("") + "</ol>"
      + '<div class="row mt-2"><button class="btn btn-soft grow" id="r-ask">💬 ' + t("dis.askAi") + '</button><button class="btn btn-ghost" data-close>' + t("common.close") + "</button></div>", { wide: true });
    $("#r-ask", m).addEventListener("click", () => { closeModal(); goChat(getLang() === "zh" ? "这道菜「" + r.name + "」怎么做？适合我的目标吗？" : "How do I cook " + r.name + "? Is it good for my goal?"); });
    m.querySelectorAll("[data-close]").forEach(b => b.addEventListener("click", closeModal));
  } catch (e) { toast(e.detail || t("err.unknown")); }
}
async function openKnowledge(id) {
  try {
    const k = await api("/api/catalog/knowledge/" + id);
    const m = showModal('<h3>📄 ' + esc(k.title) + '</h3><div class="sub">' + t("dis.tabKnowledge") + "</div>"
      + '<div class="markdown small" style="max-height:52vh;overflow:auto;padding-right:6px">' + md2html(k.content) + "</div>"
      + '<div class="row mt-2"><button class="btn btn-soft grow" id="k-ask">💬 ' + t("dis.askAi") + '</button><button class="btn btn-ghost" data-close>' + t("common.close") + "</button></div>", { wide: true });
    $("#k-ask", m).addEventListener("click", () => { closeModal(); goChat(getLang() === "zh" ? "请给我讲讲「" + k.title + "」的重点" : "Summarize the key points of " + k.title); });
    m.querySelectorAll("[data-close]").forEach(b => b.addEventListener("click", closeModal));
  } catch (e) { toast(e.detail || t("err.unknown")); }
}

/* ---------------- me / profile ---------------- */
function renderMe() {
  const main = $("#main");
  const p = S.profile || {};
  const bi = p.basic_info || {};
  const dp = p.dietary_preferences || {};
  const lf = p.lifestyle || {};
  const comp = profileCompleteness();
  main.innerHTML = '<div class="page-in">'
    + '<div class="me-top">' + avatarHTML(S.user.avatar, 76, true)
    + '<div class="grow"><h2>' + esc(S.user.display_name || S.user.username) + '</h2><div class="sub">@' + esc(S.user.username) + " · " + (S.user.email || S.user.phone || "") + "</div></div>"
    + '<button class="btn btn-sm btn-ghost" data-act="avatar">' + t("me.avatar") + "</button></div>"
    + '<div class="me-grid">'
    + '<div>'
    + section("basic", t("me.section.basic"), t("me.displayName") + " / " + t("f.gender"),
      '<div class="grid grid-2" style="gap:10px">'
      + '<div class="field"><label>' + t("me.displayName") + '</label><input class="input" id="v-display" value="' + esc(S.user.display_name || "") + '"></div>'
      + '<div class="field"><label>' + t("f.gender") + "</label><div id='v-gender'></div></div></div>"
      + '<div class="actions"><button class="btn btn-primary btn-sm" data-save="basic">' + t("f.save") + "</button></div>")
    + section("body", t("me.section.body"), t("me.sub"),
      '<div class="grid grid-3" style="gap:10px">'
      + nf("age", t("f.age"), bi.age, 10, 100) + nf("height_cm", t("f.height"), bi.height_cm, 100, 250) + nf("weight_kg", t("f.weight"), bi.weight_kg, 30, 250)
      + "</div>"
      + '<div class="grid grid-2" style="gap:10px">'
      + '<div class="field"><label>' + t("f.bodyFat") + '</label><input class="input" type="number" id="v-body_fat_pct" value="' + (bi.body_fat_pct || "") + '" placeholder="' + t("f.placeholder.bf") + '"></div>'
      + '<div class="field"><label>' + t("f.activity") + "</label><div id='v-activity'></div></div></div>"
      + '<div class="actions"><button class="btn btn-primary btn-sm" data-save="body">' + t("f.save") + "</button></div>")
    + section("diet", t("me.section.diet"), t("me.sub"),
      '<div class="grid grid-2" style="gap:10px">'
      + '<div class="field"><label>' + t("f.goal") + "</label><div id='v-goal'></div></div>"
      + '<div class="field"><label>' + t("f.dietType") + "</label><div id='v-diet'></div></div>"
      + "</div>"
      + '<div class="field"><label>' + t("f.allergies") + "</label>" + chipHTML(ALLERGY_KEYS, p.allergies || [], allergyLabel) + "</div>"
      + '<div class="field"><label>' + t("f.dislikes") + "</label><div class='tagbox' id='v-dislike'></div></div>"
      + '<div class="grid grid-3" style="gap:10px">'
      + timeField("breakfast", dp.meal_times && dp.meal_times.breakfast)
      + timeField("lunch", dp.meal_times && dp.meal_times.lunch)
      + timeField("dinner", dp.meal_times && dp.meal_times.dinner)
      + "</div>"
      + '<div class="actions"><button class="btn btn-primary btn-sm" data-save="diet">' + t("f.save") + "</button></div>")
    + section("lifestyle", t("me.section.lifestyle"), t("me.sub"),
      '<div class="grid grid-2" style="gap:10px">'
      + '<div class="field"><label>' + t("f.exFreq") + "</label><div id='v-exfreq'></div></div>"
      + '<div class="field"><label>' + t("f.exTime") + "</label><div id='v-extime'></div></div>"
      + "</div>"
      + '<div class="field"><label>' + t("f.exTypes") + "</label>" + chipHTML(EX_KEYS, lf.exercise_types || [], exLabel) + "</div>"
      + '<div class="grid grid-2" style="gap:10px">'
      + '<div class="field"><label>' + t("f.sleep") + '</label><input class="input" type="number" id="v-sleep" step="0.5" min="3" max="14" value="' + (lf.sleep_hours || "") + '"></div>'
      + '<div class="field"><label>' + t("f.eatOut") + "</label><div id='v-eatout'></div></div>"
      + "</div>"
      + '<div class="field"><label>' + t("f.waterGoal") + ' · <b id="v-water-val">' + (lf.water_goal_ml || 2000) + ' ml</b></label>'
      + '<input class="input" type="range" id="v-water" min="1000" max="4000" step="250" value="' + (lf.water_goal_ml || 2000) + '"></div>'
      + '<div class="row-between" style="padding:6px 0"><b style="font-size:14px">' + t("f.smokingY") + '</b><button class="toggle' + (lf.smoking ? " on" : "") + '" id="v-smoke"></button></div>'
      + '<div class="row-between" style="padding:6px 0"><b style="font-size:14px">' + t("f.alcoholY") + '</b><button class="toggle' + (lf.alcohol ? " on" : "") + '" id="v-drink"></button></div>'
      + '<div class="actions"><button class="btn btn-primary btn-sm" data-save="lifestyle">' + t("f.save") + "</button></div>")
    + section("health", t("me.section.health"), t("me.sub"),
      chipHTML(HEALTH_KEYS, p.health_conditions || [], healthLabel)
      + '<div class="actions"><button class="btn btn-primary btn-sm" data-save="health">' + t("f.save") + "</button></div>")
    + "</div>"
    + '<aside style="position:sticky;top:80px">'
    + '<div class="card"><div class="card-title">' + t("me.complete") + "</div>"
    + '<div class="row"><div class="ring" style="--p:' + comp + '"><div><b>' + comp + '%</b></div></div>'
    + '<div class="small muted" style="line-height:1.6">' + t("me.completeHint") + "</div></div></div>"
    + '<div class="card mt-1"><div class="card-title">' + t("set.account") + "</div>"
    + '<div class="view-field"><span class="lbl">' + t("me.username") + '</span><span class="val">@' + esc(S.user.username) + "</span></div>"
    + '<div class="view-field"><span class="lbl">' + t("auth.email") + '</span><span class="val">' + esc(S.user.email || "—") + "</span></div>"
    + '<div class="view-field"><span class="lbl">' + t("auth.phone") + '</span><span class="val">' + esc(S.user.phone || "—") + "</span></div>"
    + '<div class="mt-1"><button class="btn btn-block btn-ghost" data-act="settings">⚙️ ' + t("nav.settings") + "</button></div>"
    + '<div class="mt-1"><button class="btn btn-block btn-danger-soft" data-act="logout">' + t("auth.logout") + "</button></div>"
    + "</div></aside>"
    + "</div></div>";
  function section(id, title, sub, inner) {
    return '<div class="form-section" data-sec="' + id + '"><h3>' + title + '</h3><p class="sec-sub">' + sub + "</p>" + inner + "</div>";
  }
  function nf(id, label, val, min, max) {
    return '<div class="field"><label>' + label + '</label><input class="input" type="number" id="v-' + id + '" min="' + min + '" max="' + max + '" value="' + (val == null ? "" : val) + '"></div>';
  }
  function timeField(key, val) {
    return '<div class="field"><label>' + t("f." + key) + '</label><input class="input" type="time" id="v-mt-' + key + '" value="' + (val || "") + '"></div>';
  }
  // fill segment wrappers
  const putSeg = (sel, group, keys, cur) => { const el = $(sel); if (el) el.innerHTML = segHTML(group, group, keys, cur || "", true); };
  putSeg("#v-gender", "gender", OPT_KEYS.gender, bi.gender);
  putSeg("#v-activity", "activity", OPT_KEYS.activity, bi.activity_level);
  putSeg("#v-goal", "goal", OPT_KEYS.goal, dp.goal);
  putSeg("#v-diet", "diet", OPT_KEYS.diet, dp.dietary_type);
  putSeg("#v-exfreq", "exfreq", OPT_KEYS.exfreq, lf.exercise_frequency);
  putSeg("#v-extime", "extime", OPT_KEYS.extime, lf.exercise_time);
  putSeg("#v-eatout", "eatout", OPT_KEYS.eatout, lf.eat_out_freq);
  bindSeg(main);
  bindChips(main, () => {});
  const dislike = $("#v-dislike");
  if (dislike) renderTagBox(dislike, dp.disliked_foods || (dp.disliked_foods = []));
  const w = $("#v-water");
  if (w) w.addEventListener("input", () => { $("#v-water-val").textContent = w.value + " ml"; });
  const smoke = $("#v-smoke"); if (smoke) smoke.addEventListener("click", () => smoke.classList.toggle("on"));
  const drink = $("#v-drink"); if (drink) drink.addEventListener("click", () => drink.classList.toggle("on"));
  // actions
  main.querySelectorAll("[data-save]").forEach(b => b.addEventListener("click", () => saveSection(b.getAttribute("data-save"))));
  main.querySelectorAll("[data-act]").forEach(b => b.addEventListener("click", () => {
    const act = b.getAttribute("data-act");
    if (act === "avatar") openAvatarPicker();
    if (act === "settings") switchView("settings");
    if (act === "logout") confirmBox(t("auth.logoutConfirm"), logout);
  }));
  function renderTagBox(box, list) {
    box.innerHTML = "";
    list.forEach((food, i) => {
      const tag = document.createElement("span");
      tag.className = "tag";
      tag.innerHTML = esc(food) + '<span class="x">✕</span>';
      tag.querySelector(".x").addEventListener("click", () => { list.splice(i, 1); renderTagBox(box, list); });
      box.appendChild(tag);
    });
    const inp = document.createElement("input");
    inp.placeholder = t("f.placeholder.dislike");
    box.appendChild(inp);
    inp.addEventListener("keydown", e => { if (e.key === "Enter" && inp.value.trim()) { e.preventDefault(); list.push(inp.value.trim()); renderTagBox(box, list); } });
  }
}
function collectProfileSection(sec) {
  const p = S.profile;
  const val = (sel) => { const el = $(sel); return el ? el.value : ""; };
  const segVal = (name) => { const el = $('.seg[data-name="' + name + '"] button.active'); return el ? el.value : ""; };
  const upd = {};
  if (sec === "basic") {
    upd.basic_info = { gender: segVal("gender") };
    upd.display = val("#v-display");
  } else if (sec === "body") {
    upd.basic_info = {
      age: $("#v-age").value ? num($("#v-age").value, null) : null,
      height_cm: $("#v-height_cm").value ? num($("#v-height_cm").value, null) : null,
      weight_kg: $("#v-weight_kg").value ? num($("#v-weight_kg").value, null) : null,
      body_fat_pct: $("#v-body_fat_pct").value ? num($("#v-body_fat_pct").value, null) : null,
      activity_level: segVal("activity"),
    };
  } else if (sec === "diet") {
    upd.dietary_preferences = {
      goal: segVal("goal"),
      dietary_type: segVal("diet"),
      meal_times: {
        breakfast: val("#v-mt-breakfast"), lunch: val("#v-mt-lunch"), dinner: val("#v-mt-dinner"),
      },
    };
    upd.allergies = $$("#main .form-section[data-sec='diet'] .chip.active").map(c => c.dataset.val);
  } else if (sec === "lifestyle") {
    upd.lifestyle = {
      exercise_frequency: segVal("exfreq"),
      exercise_time: segVal("extime"),
      exercise_types: $$("#main .form-section[data-sec='lifestyle'] .chip.active").map(c => c.dataset.val),
      sleep_hours: $("#v-sleep").value ? num($("#v-sleep").value, null) : null,
      eat_out_freq: segVal("eatout"),
      water_goal_ml: num($("#v-water").value, 2000),
      smoking: $("#v-smoke") ? $("#v-smoke").classList.contains("on") : false,
      alcohol: $("#v-drink") ? $("#v-drink").classList.contains("on") : false,
    };
  } else if (sec === "health") {
    upd.health_conditions = $$("#main .form-section[data-sec='health'] .chip.active").map(c => c.dataset.val);
  }
  return upd;
}
async function saveSection(sec) {
  const body = { profile: collectProfileSection(sec) };
  const dn = body.profile.display;
  delete body.profile.display;
  if (dn !== undefined) body.display_name = dn || null;
  try {
    const d = await api("/api/me", { method: "PUT", body });
    S.user = d.user; S.profile = d.profile; S.targets = d.targets;
    toast(t("set.profileUpdated"));
    renderMe();
  } catch (e) { toast(e.detail || t("err.unknown")); }
}
function openAvatarPicker() {
  const m = showModal('<h3>🎨 ' + t("me.avatar") + '</h3><p class="sub">' + t("me.sub") + "</p>"
    + '<div class="chip-row" id="ap-row"></div>'
    + '<div class="row mt-2"><label class="btn btn-ghost grow" style="cursor:pointer">📁 上传<input type="file" id="ap-file" accept="image/*" style="display:none"></label>'
    + '<button class="btn btn-soft" id="ap-initials">ABC</button></div>'
    + '<div class="row mt-2"><button class="btn btn-ghost grow" data-close>' + t("common.cancel") + '</button><button class="btn btn-primary grow" id="ap-save">' + t("common.save") + "</button></div>");
  const row = $("#ap-row", m);
  let picked = (S.user.avatar && S.user.avatar.type === "preset") ? S.user.avatar.value : AVATARS[0];
  let fileData = null;
  AVATARS.forEach((a, i) => {
    const b = document.createElement("div");
    b.className = "avatar-preset" + (picked === a ? " active" : "");
    b.textContent = a;
    b.style.background = avatarStyle(null, i + 1);
    b.addEventListener("click", () => { $$(".avatar-preset", row).forEach(x => x.classList.remove("active")); b.classList.add("active"); picked = a; fileData = null; });
    row.appendChild(b);
  });
  const f = $("#ap-file", m);
  f.addEventListener("change", () => {
    const file = f.files[0];
    if (!file) return;
    const rd = new FileReader();
    rd.onload = () => {
      fileData = rd.result;
      toast(getLang() === "zh" ? "已选择图片，点保存" : "Image selected, tap Save");
    };
    rd.readAsDataURL(file);
  });
  $("#ap-initials", m).addEventListener("click", () => { fileData = null; picked = null; toast(getLang() === "zh" ? "将使用昵称首字母" : "Will use your initial"); });
  $("#ap-save", m).addEventListener("click", async () => {
    let avatar;
    if (fileData) avatar = { type: "upload", value: fileData };
    else if (picked) avatar = { type: "preset", value: picked };
    else avatar = { type: "initials" };
    closeModal();
    try {
      const d = await api("/api/me", { method: "PUT", body: { avatar } });
      S.user = d.user; toast(t("set.saved")); refreshUI();
    } catch (e) { toast(e.detail || t("err.unknown")); }
  });
  m.querySelectorAll("[data-close]").forEach(b => b.addEventListener("click", closeModal));
}

/* ---------------- settings ---------------- */
function renderSettings() {
  const main = $("#main");
  const themes = [
    { id: "light", cls: "sw-light", ico: "🌿", key: "theme.light" },
    { id: "fresh", cls: "sw-fresh", ico: "🍑", key: "theme.fresh" },
    { id: "dark", cls: "sw-dark", ico: "🌙", key: "theme.dark" },
  ];
  const curTheme = document.documentElement.getAttribute("data-theme") || "light";
  const curLang = getLang();
  main.innerHTML = '<div class="page-in" style="max-width:760px;margin:0 auto">'
    + '<div class="page-head"><div><h1>⚙️ ' + t("nav.settings") + "</h1><p>" + t("set.title") + "</p></div></div>"
    + '<div class="settings-group"><h3>' + t("set.appearance") + "</h3><div class='settings-card'>"
    + '<div class="set-row" style="cursor:default"><div class="s-ico">🎨</div><div class="s-body"><b>' + t("app.theme") + "</b><span>" + t("set.langNote") + "</span></div>"
    + '<div class="theme-row" style="width:60%">' + themes.map(th =>
      '<div class="theme-card' + (curTheme === th.id ? " active" : "") + '" data-theme="' + th.id + '"><div class="theme-swatch ' + th.cls + '">' + th.ico + "</div><div class='tt'>" + t(th.key) + "</div></div>").join("") + "</div></div>"
    + '<div class="set-row" style="cursor:default"><div class="s-ico">🌐</div><div class="s-body"><b>' + t("app.language") + "</b><span>" + t("set.langNote") + "</span></div>"
    + '<div class="lang-row" style="width:46%">'
    + '<div class="lang-card' + (curLang === "zh" ? " active" : "") + '" data-lang="zh"><span class="big">中</span>简体中文</div>'
    + '<div class="lang-card' + (curLang === "en" ? " active" : "") + '" data-lang="en"><span class="big">A</span>English</div>'
    + "</div></div></div></div>"
    + '<div class="settings-group"><h3>' + t("auth.security") + "</h3><div class='settings-card'>"
    + setRow("👤", t("me.displayName"), esc(S.user.display_name || ""), "nick")
    + setRow("📧", t("auth.email"), esc(S.user.email || "—"), "email")
    + setRow("📱", t("auth.phone"), esc(S.user.phone || "—"), "phone")
    + setRow("🔑", t("auth.changePwd"), "", "pwd")
    + "</div></div>"
    + '<div class="settings-group"><h3>' + t("set.about") + "</h3><div class='settings-card'>"
    + setRow("📲", t("set.install"), t("set.installHint"), "install")
    + setRow("💚", "Vitala", t("set.version"), null, false)
    + "</div><p class='small muted mt-1' style='padding:0 6px;line-height:1.7'>" + t("set.aboutText") + "</p></div>"
    + '<button class="btn btn-block btn-danger-soft mt-2" id="s-logout">' + t("auth.logout") + "</button>"
    + "</div>";
  $$(".theme-card", main).forEach(c => c.addEventListener("click", () => applyTheme(c.getAttribute("data-theme"))));
  $$(".lang-card", main).forEach(c => c.addEventListener("click", () => applyLanguage(c.getAttribute("data-lang"))));
  main.querySelectorAll("[data-row]").forEach(r => r.addEventListener("click", () => handleSetRow(r.getAttribute("data-row"))));
  $("#s-logout").addEventListener("click", () => confirmBox(t("auth.logoutConfirm"), logout));
  function setRow(ico, title, sub, row, clickable) {
    const disabled = clickable === false ? " style='opacity:.75'" : "";
    return '<div class="set-row" data-row="' + row + '"' + (clickable === false ? " style='cursor:default'" : "") + '><div class="s-ico">' + ico + '</div><div class="s-body"><b>' + title + "</b><span>" + sub + "</span></div>"
      + (clickable === false ? "" : '<span class="chev">›</span>') + "</div>";
  }
}
function handleSetRow(row) {
  if (row === "nick") {
    const m = showModal('<h3>👤 ' + t("me.displayName") + '</h3><div class="field mt-1"><input class="input" id="n-value" value="' + esc(S.user.display_name || "") + '"></div>'
      + '<div class="row"><button class="btn btn-ghost grow" data-close>' + t("common.cancel") + '</button><button class="btn btn-primary grow" id="n-save">' + t("common.save") + "</button></div>");
    $("#n-save", m).addEventListener("click", async () => { const v = $("#n-value", m).value.trim(); closeModal(); if (!v) return; await putAcct({ display_name: v }); });
    m.querySelectorAll("[data-close]").forEach(b => b.addEventListener("click", closeModal));
  } else if (row === "email" || row === "phone") {
    const isEmail = row === "email";
    const label = isEmail ? t("auth.email") : t("auth.phone");
    const m = showModal('<h3>' + (isEmail ? "📧 " : "📱 ") + label + '</h3><div class="field mt-1"><input class="input" id="c-value" type="' + (isEmail ? "email" : "tel") + '" value="' + esc(isEmail ? S.user.email || "" : S.user.phone || "") + '"></div>'
      + '<div class="row"><button class="btn btn-ghost grow" data-close>' + t("common.cancel") + '</button><button class="btn btn-primary grow" id="c-save">' + t("common.save") + "</button></div>");
    $("#c-save", m).addEventListener("click", async () => {
      const v = $("#c-value", m).value.trim() || null; closeModal();
      try {
        const d = await api("/api/auth/contact", { method: "PUT", body: { field: row, value: v } });
        S.user = d.user; S.profile = d.profile; S.targets = d.targets; toast(t("auth.contactChanged")); renderSettings();
      } catch (e) { toast(e.detail || t("err.unknown")); }
    });
    m.querySelectorAll("[data-close]").forEach(b => b.addEventListener("click", closeModal));
  } else if (row === "pwd") {
    const m = showModal('<h3>🔑 ' + t("auth.changePwd") + '</h3><div class="field"><label>' + t("auth.oldPwd") + '</label><input class="input" type="password" id="p-old"></div>'
      + '<div class="field"><label>' + t("auth.newPwd") + '</label><input class="input" type="password" id="p-new" placeholder="' + t("auth.passwordPh") + '"></div>'
      + '<div class="field"><label>' + t("auth.confirmPwd") + '</label><input class="input" type="password" id="p-new2"></div>'
      + '<div class="row"><button class="btn btn-ghost grow" data-close>' + t("common.cancel") + '</button><button class="btn btn-primary grow" id="p-save">' + t("common.save") + "</button></div>");
    $("#p-save", m).addEventListener("click", async () => {
      const o = $("#p-old", m).value, n = $("#p-new", m).value, n2 = $("#p-new2", m).value;
      if (n.length < 6) { toast(t("auth.pwdShort")); return; }
      if (n !== n2) { toast(t("auth.mismatch")); return; }
      try { await api("/api/auth/password", { method: "PUT", body: { old_password: o, new_password: n } }); closeModal(); toast(t("auth.pwdChanged")); }
      catch (e) { toast(e.detail || t("err.unknown")); }
    });
    m.querySelectorAll("[data-close]").forEach(b => b.addEventListener("click", closeModal));
  } else if (row === "install") {
    if (S.installEvt) { S.installEvt.prompt(); } else { toast(t("pwa.installed")); }
  }
}
async function putAcct(body) {
  try { const d = await api("/api/me", { method: "PUT", body }); S.user = d.user; S.profile = d.profile; toast(t("set.saved")); renderSettings(); }
  catch (e) { toast(e.detail || t("err.unknown")); }
}

/* ---------------- boot ---------------- */
async function bootMain(user) {
  S.user = user;
  S.profile = user.profile;
  try {
    const full = await api("/api/me");
    S.user = full.user; S.profile = full.profile; S.targets = full.targets;
  } catch (e) { /* offline-ish: still proceed with cached data */ }
  if (S.user && S.user.theme) { const cur = document.documentElement.getAttribute("data-theme"); if (cur !== S.user.theme) applyTheme(S.user.theme); }
  if (S.user && (S.user.language === "zh" || S.user.language === "en")) {
    if (getLang() !== S.user.language) { setLang(S.user.language); localStorage.setItem(LS.lang, S.user.language); }
  }
  S.chat = [];
  try { S.chat = JSON.parse(localStorage.getItem(chatKey()) || "[]"); } catch (e) { S.chat = []; }
  if (!S.user.onboarding_done) {
    showPage("onboard");
  } else {
    showPage("app");
  }
}

/* ---------------- brand & svg icons (v2.1) ---------------- */
const V_ICON_PATHS = {
  home: '<path d="M3.5 10.6 12 3.8l8.5 6.8"/><path d="M5.6 9.4V20h4.4v-5h4v5h4.4V9.4"/>',
  chat: '<path d="M4 6.2h16v9.6H9.6L4 19.6V6.2Z"/><path d="M8 9.6h8M8 12.6h5"/>',
  discover: '<circle cx="12" cy="12" r="8.6"/><path d="m15.2 8.8-1.7 4.7-4.7 1.7 1.7-4.7 4.7-1.7Z"/>',
  me: '<circle cx="12" cy="8.2" r="3.7"/><path d="M5.2 19.4c.7-3.3 3.5-4.9 6.8-4.9s6.1 1.6 6.8 4.9"/>',
  palette: '<path d="M12 3.6a8.4 8.4 0 1 0 0 16.8c1.1 0 1.8-.6 1.8-1.4 0-1.7 1.4-2.8 3-2.8h1.1a2.4 2.4 0 0 0 2.4-2.4c0-5.7-4-10.2-8.3-10.2Z"/><path d="M9.4 9.6h.01M14.6 8.6h.01M8.2 13.4h.01M12.6 15.2h.01"/>',
};
function svgIcon(name, size) {
  const s = size || 22;
  return '<svg class="ico-svg" viewBox="0 0 24 24" width="' + s + '" height="' + s + '" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + (V_ICON_PATHS[name] || "") + "</svg>";
}
function sproutSVG(px, color) {
  const col = color || "currentColor";
  return '<svg viewBox="0 0 24 24" width="' + px + '" height="' + px + '" fill="none" stroke="' + col + '" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    + '<path d="M12 21.2V9.6"/><path d="M12 13.4c0-3.4-1.9-5.7-5.5-6.4.4 3.9 2.5 6.4 5.5 6.4Z"/><path d="M12 13.4c0-3.4 1.9-5.7 5.5-6.4-.4 3.9-2.5 6.4-5.5 6.4Z"/></svg>';
}
function logoMark(px) {
  const dark = (document.documentElement.getAttribute("data-theme") === "dark");
  const ink = dark ? "#15231B" : "#FFFFFF";
  const br = Math.max(9, Math.round(px * 0.3));
  return '<span class="brand-mark" style="width:' + px + "px;height:" + px + "px;border-radius:" + br + 'px">' + sproutSVG(Math.round(px * 0.58), ink) + "</span>";
}


(function init() {
  // splash min time
  const t0 = Date.now();
  // theme/lang from cache to avoid flash
  const cached = (() => { try { return JSON.parse(localStorage.getItem(LS.user) || "null"); } catch (e) { return null; } })();
  const theme = localStorage.getItem(LS.theme) || (cached && cached.theme) || "light";
  applyTheme(theme);
  let lang = localStorage.getItem(LS.lang);
  if (!lang) {
    if (cached && (cached.language === "zh" || cached.language === "en")) lang = cached.language;
    else lang = (navigator.language || "zh").toLowerCase().startsWith("zh") ? "zh" : "en";
  }
  setLang(lang);
  document.title = lang === "zh" ? "Vitala — 你的 AI 营养管家" : "Vitala — Your nutrition companion";
  const splash = $("#splash");
  setTimeout(() => { splash.classList.add("fade"); setTimeout(() => splash.remove(), 400); }, 420);
  if (navigator.serviceWorker) {
    window.addEventListener("load", () => { navigator.serviceWorker.register("/static/sw.js").catch(() => {}); });
  }
  window.addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); S.installEvt = e; });
  async function start() {
    if (S.token) {
      try {
        const d = await api("/api/auth/me");
        await bootMain(d.user);
        return;
      } catch (e) { /* invalid token, fall through to auth */ }
    }
    showPage("auth");
  }
  start();
})();