import { api, post } from "./api.js";
import { t, applyLanguage, language } from "./i18n.js";
export function el(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== null && text !== undefined) node.textContent = String(text);
  return node;
}
export function button(text, action, className = "") {
  const node = el("button", className, text);
  node.type = "button";
  node.addEventListener("click", action);
  return node;
}
export function translated(tag, key, className = "") {
  const node = el(tag, className, t(key));
  node.dataset.i18n = key;
  return node;
}
let toastTimer;
export function toast(message) {
  const node = document.querySelector("#toast");
  if (!node) return;
  node.textContent = message;
  node.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (node.hidden = true), 5000);
}
export function empty(title, help, symbol = "◎") {
  const node = el("div", "empty");
  node.append(
    el("div", "empty-symbol", symbol),
    el("strong", "", title),
    el("span", "", help),
  );
  return node;
}
export function age(date) {
  const minutes = Math.max(
    0,
    Math.floor((Date.now() - Date.parse(date)) / 60000),
  );
  return minutes < 1
    ? "just now"
    : minutes < 60
      ? `${minutes} min ago`
      : `${Math.floor(minutes / 60)} h ago`;
}
export function header(config = {}) {
  const target = document.querySelector("#shared-header");
  const head = el("header", "topbar");
  const brand = el("a", "brand");
  brand.href = "/";
  const logo = el("img");
  logo.src = "/static/img/logo.svg";
  logo.alt = "";
  brand.append(logo, el("span", "", "ReliefSync Desk"));
  head.append(brand);
  const nav = el("nav");
  nav.setAttribute("aria-label", "Main navigation");
  for (const [url, key] of [
    ["/", "dashboard"],
    ["/about", "about"],
    ["/architecture", "architecture"],
    ["/eval", "evaluation"],
    ["/join", "join"],
  ]) {
    const a = translated("a", key);
    a.href = url;
    if (location.pathname === url) a.setAttribute("aria-current", "page");
    nav.append(a);
  }
  head.append(nav);
  const actions = el("div", "header-actions");
  const select = el("select");
  select.setAttribute("aria-label", "Interface language");
  for (const [value, label] of [
    ["en", "EN"],
    ["ta", "தமிழ்"],
    ["es", "ES"],
    ["de", "DE"],
  ]) {
    const option = el("option", "", label);
    option.value = value;
    select.append(option);
  }
  select.value = language;
  select.addEventListener("change", () => applyLanguage(select.value));
  const theme = button(
    "◐",
    () => {
      const current =
        document.documentElement.dataset.theme ||
        (matchMedia("(prefers-color-scheme:dark)").matches ? "dark" : "light");
      const next = current === "dark" ? "light" : "dark";
      document.documentElement.dataset.theme = next;
      try {
        localStorage.setItem("reliefsync-theme", next);
      } catch {}
    },
    "theme",
  );
  theme.setAttribute("aria-label", "Toggle light and dark theme");
  const login = button(
    t(config.authenticated ? "logout" : "login"),
    async () => {
      if (config.authenticated) {
        await post("/api/logout");
        location.reload();
      } else {
        const dialog = document.querySelector("#login-dialog");
        if (dialog) dialog.showModal();
        else location.href = "/";
      }
    },
  );
  login.id = "login-btn";
  actions.append(select, theme, login);
  head.append(actions);
  target.replaceChildren(head);
  const foot = el("footer", "footer");
  foot.append(translated("span", "footer"));
  const links = el("span");
  for (const [url, label] of [
    ["/safety", t("safety")],
    ["https://github.com/hannielvinu/ReliefSync-Desk", "GitHub"],
    [
      "https://github.com/hannielvinu/ReliefSync-Desk/blob/main/LICENSE",
      "MIT · Hanniel Vinu",
    ],
  ]) {
    const a = el("a", "", label);
    a.href = url;
    links.append(a, document.createTextNode(" · "));
  }
  foot.append(links);
  document.querySelector("#shared-footer").replaceChildren(foot);
  try {
    const theme = localStorage.getItem("reliefsync-theme");
    if (["light", "dark"].includes(theme))
      document.documentElement.dataset.theme = theme;
  } catch {}
  applyLanguage();
  const form = document.querySelector("#login-form");
  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        await post("/api/login", {
          token: document.querySelector("#login-token").value,
        });
        document.querySelector("#login-token").value = "";
        location.reload();
      } catch (err) {
        toast(err.message);
      }
    });
    document.querySelector("#cancel-login").onclick = () =>
      document.querySelector("#login-dialog").close();
  }
}
let closeDrawerAction, lastFocused;
export function closeDrawer() {
  document.querySelector("#drawer").hidden = true;
  document.querySelector("#drawer-backdrop").hidden = true;
  document.querySelector("#main").inert = false;
  document.querySelector("#shared-header").inert = false;
  lastFocused?.focus();
}
export async function openDrawer(id, config, onRefresh) {
  try {
    const card = await api(`/api/cards/${id}`);
    lastFocused = document.activeElement;
    const drawer = document.querySelector("#drawer");
    drawer.replaceChildren();
    const close = button("×", closeDrawer, "drawer-close");
    close.setAttribute("aria-label", t("close"));
    drawer.append(
      close,
      el("p", "eyebrow", `REQUEST / RS-${String(card.id).padStart(4, "0")}`),
      el("h2", "", card.item_en),
      el(
        "p",
        "muted",
        `${t(card.intent)} · ${t(card.status)}${card.simulated ? " · " + t("simulated") : ""}`,
      ),
      el("h3", "", t("original")),
    );
    const quote = el("blockquote", "", card.text);
    quote.lang = card.language;
    drawer.append(
      quote,
      el("h3", "", t("translation")),
      el("p", "", card.message_en),
    );
    const dl = el("dl");
    for (const [key, value] of [
      ["location", card.location_text],
      [
        "source",
        `${card.loc_source} · ${Math.round(card.loc_confidence * 100)}%`,
      ],
      ["urgency", `U${card.urgency} · ${card.urgency_reason}`],
      [
        "confidence",
        `${Math.round(card.confidence * 100)}% · ${card.extractor}`,
      ],
      ["language", card.language],
      ["status", card.status],
    ])
      dl.append(el("dt", "", t(key)), el("dd", "", value));
    if (card.exact_location)
      dl.append(
        el("dt", "", "Coordinator coordinates"),
        el("dd", "mono", `${card.lat}, ${card.lng}`),
      );
    if (card.cluster_id)
      dl.append(
        el("dt", "", "Incident cluster"),
        el("dd", "", `${card.cluster_id} · possible same incident, not merged`),
      );
    drawer.append(dl);
    if (config.authenticated) {
      const form = el("form");
      const item = el("input");
      item.value = card.item;
      item.maxLength = 60;
      const canonical = el("input");
      canonical.value = card.item_en;
      canonical.maxLength = 100;
      const area = el("input");
      area.value = card.location_text;
      const urgency = el("input");
      urgency.type = "number";
      urgency.min = 1;
      urgency.max = 5;
      urgency.value = card.urgency;
      for (const [text, input] of [
        [t("item"), item],
        ["English resource", canonical],
        [t("location"), area],
        [t("urgency"), urgency],
      ]) {
        const label = el("label", "", text);
        label.append(input);
        form.append(label);
      }
      const save = el("button", "primary", t("save"));
      save.type = "submit";
      form.append(save);
      form.onsubmit = async (e) => {
        e.preventDefault();
        try {
          await api(`/api/cards/${id}`, {
            method: "PATCH",
            body: JSON.stringify({
              item: item.value,
              item_en: canonical.value,
              location_text: area.value,
              urgency: Number(urgency.value),
            }),
          });
          closeDrawer();
          onRefresh();
        } catch (err) {
          toast(err.message);
        }
      };
      form.append(
        button(t("fulfilled"), () => updateStatus("fulfilled")),
        button(t("reject"), () => updateStatus("rejected")),
        button("Reopen", () => updateStatus("open")),
      );
      async function updateStatus(status) {
        try {
          await api(`/api/cards/${id}`, {
            method: "PATCH",
            body: JSON.stringify({ status }),
          });
          closeDrawer();
          onRefresh();
        } catch (err) {
          toast(err.message);
        }
      }
      drawer.append(form);
    }
    drawer.append(el("h3", "", t("audit")));
    const audit = el("ul", "audit");
    for (const row of card.audit)
      audit.append(
        el("li", "", `${new Date(row.ts).toLocaleString()} · ${row.action}`),
      );
    for (const row of card.duplicates)
      audit.append(el("li", "", `Duplicate report RS-${row.id}`));
    drawer.append(audit);
    drawer.hidden = false;
    document.querySelector("#drawer-backdrop").hidden = false;
    document.querySelector("#main").inert = true;
    document.querySelector("#shared-header").inert = true;
    drawer.focus();
    closeDrawerAction = closeDrawer;
  } catch (err) {
    toast(err.message);
  }
}
document.addEventListener("keydown", (event) => {
  const drawer = document.querySelector("#drawer");
  if (!drawer || drawer.hidden) return;
  if (event.key === "Escape") closeDrawerAction?.();
  if (event.key === "Tab") {
    const items = [
      ...drawer.querySelectorAll("button,input,select,textarea,a"),
    ].filter((n) => !n.disabled);
    if (!items.length) {
      event.preventDefault();
      return;
    }
    const first = items[0],
      last = items.at(-1);
    if (
      event.shiftKey &&
      (document.activeElement === first || document.activeElement === drawer)
    ) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }
});
document
  .querySelector("#drawer-backdrop")
  ?.addEventListener("click", closeDrawer);
