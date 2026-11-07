import { api } from "./api.js";
import { header, el, button, toast } from "./ui.js";
async function init() {
  let config = {};
  try {
    config = await api("/api/config");
  } catch {}
  header(config);
  if (location.pathname === "/eval")
    try {
      const report = await api("/api/eval");
      const root = document.querySelector("#evaluation-report");
      root.replaceChildren(
        el(
          "p",
          "badge",
          `Extractor used: ${Object.entries(report.extractor_used)
            .map(([key, n]) => `${key} (${n})`)
            .join(", ")}`,
        ),
        el(
          "p",
          "",
          `${report.dataset_size} synthetic samples · ${new Date(report.date).toLocaleString()} · median ${report.median_latency_ms} ms`,
        ),
      );
      const wrap = el("div", "table-wrap");
      const table = el("table");
      const head = el("tr");
      for (const title of [
        "Language",
        "Samples",
        "Intent",
        "Category",
        "Resource",
        "Location",
        "Urgency ±1",
        "Misinformation",
      ])
        head.append(el("th", "", title));
      table.append(head);
      for (const [key, values] of [
        ["Overall", report.overall],
        ...Object.entries(report.per_language),
      ]) {
        const row = el("tr");
        row.append(el("td", "", key), el("td", "", values.count));
        for (const metric of [
          "intent_accuracy",
          "category_accuracy",
          "item_accuracy",
          "location_accuracy",
          "urgency_within_one",
          "misinformation_accuracy",
        ])
          row.append(el("td", "", `${(values[metric] * 100).toFixed(1)}%`));
        table.append(row);
      }
      wrap.append(table);
      root.append(wrap, el("p", "muted", report.dataset_kind));
    } catch (err) {
      document.querySelector("#evaluation-report").textContent = err.message;
    }
  if (location.pathname === "/join") {
    const links = document.querySelector("#join-links");
    links.replaceChildren();
    for (const [url, label, fallback] of [
      [
        config.test_group_url,
        "Open Telegram test group",
        "The test group has not been configured yet. You can still use the dashboard drill.",
      ],
      [
        config.bot_username ? "https://t.me/" + config.bot_username : "",
        "Message the bot",
        "No live Telegram bot connected yet.",
      ],
      [
        config.feedback_url,
        "Share feedback",
        "Feedback form not configured. Use a GitHub issue.",
      ],
    ]) {
      if (url && /^https?:\/\//.test(url)) {
        const a = el("a", "", label);
        a.href = url;
        a.rel = "noopener noreferrer";
        const p = el("p");
        p.append(a);
        links.append(p);
      } else links.append(el("p", "muted", fallback));
    }
    const samples = [
      ["ta", "வேளச்சேரி இன்சுலின் தேவை"],
      ["ta", "Perungudi thanni venum"],
      ["en", "I have insulin available in Velachery"],
      ["es", "Necesito agua en Paiporta"],
      ["de", "Biete eine Pumpe in Alfafar"],
    ];
    for (const [lang, text] of samples) {
      const article = el("article", "sample");
      const content = el("div");
      const p = el("p", "", text);
      p.lang = lang;
      content.append(
        el("small", "", lang.toUpperCase() + " · fictional sample"),
        p,
      );
      article.append(
        content,
        button("Copy", async () => {
          try {
            await navigator.clipboard.writeText(text);
            toast("Copied");
          } catch {
            toast("Select and copy the sample text");
          }
        }),
      );
      document.querySelector("#samples").append(article);
    }
    async function counters() {
      try {
        const stats = await api("/api/stats");
        document.querySelector("#participants").textContent =
          stats.participants;
        document.querySelector("#countries").textContent =
          stats.countries_self_reported;
      } catch {}
    }
    counters();
    setInterval(counters, 10000);
  }
}
init();
