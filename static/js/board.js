import { t } from "./i18n.js";
import { el, empty, age } from "./ui.js";
export function renderBoard(cards, onSelect) {
  const target = document.querySelector("#card-list");
  const nodes = [];
  for (const card of cards) {
    const node = el("button", "request-card");
    node.type = "button";
    node.dataset.id = card.id;
    node.setAttribute(
      "aria-label",
      `${card.intent}: ${card.item_en}, urgency ${card.urgency}, ${card.location_text}`,
    );
    node.onclick = () => onSelect(card.id);
    const top = el("div", "card-top");
    top.append(
      el(
        "span",
        `intent-icon ${card.intent}`,
        card.intent === "offer" ? "+" : "!",
      ),
      el("span", "", t(card.intent)),
      el("span", "card-id mono", `RS-${String(card.id).padStart(4, "0")}`),
    );
    const title = el("h3", "", card.item_en);
    const original = el(
      "div",
      "card-line",
      card.item === card.item_en ? "" : card.item,
    );
    original.lang = card.language;
    const line = el("div", "card-line", `⌖ ${card.location_text}`);
    const tags = el("div", "card-tags");
    tags.append(
      el(
        "span",
        `urgency u${card.urgency}`,
        `U${card.urgency} ${t(["", "low", "supplies", "priority", "high", "critical"][card.urgency])}`,
      ),
      el("span", "chip", card.category),
      el("span", "chip", card.language.toUpperCase()),
    );
    if (card.repeat_count > 1)
      tags.append(el("span", "chip", `${card.repeat_count} ${t("reports")}`));
    if (card.simulated)
      tags.append(el("span", "chip simulation", t("simulated")));
    if (card.possible_misinformation)
      tags.append(el("span", "chip", t("flagged")));
    if (card.cluster_id)
      tags.append(el("span", "chip", "Possible same incident"));
    for (const flag of JSON.parse(card.vulnerable_flags || "[]"))
      tags.append(el("span", "chip", flag));
    const conf = el("div", "confidence");
    const progress = el("progress");
    progress.max = 1;
    progress.value = card.confidence;
    progress.setAttribute("aria-label", t("confidence"));
    conf.append(
      el(
        "span",
        "",
        `${Math.round(card.confidence * 100)}% ${t("confidence")} · ${card.extractor}`,
      ),
      progress,
      el("span", "", age(card.created_at)),
    );
    node.append(
      top,
      title,
      original,
      line,
      tags,
      el("span", "chip", t(card.status)),
      conf,
    );
    nodes.push(node);
  }
  target.replaceChildren(
    ...(nodes.length ? nodes : [empty(t("emptyBoard"), t("emptyHelp"))]),
  );
  document.querySelector("#board-count").textContent = `${cards.length} cards`;
}
