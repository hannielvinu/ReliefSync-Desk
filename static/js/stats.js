import { t } from "./i18n.js";
import { el } from "./ui.js";
export function renderStats(data) {
  const items = [
    ["processed", data.messages_processed, "all intake languages"],
    ["openNeeds", data.needs, "awaiting coordination"],
    ["openOffers", data.offers, "resources available"],
    ["duplicates", data.duplicates_merged, "repeat reports grouped"],
    [
      "connections",
      data.matches_approved,
      `${data.matches_suggested} suggested · ${data.matches_completed} completed`,
    ],
    [
      "latency",
      `${data.median_seconds_message_to_card}s`,
      "median processing time",
    ],
    [
      "reach",
      data.participants,
      `${data.countries_self_reported} ${t("selfReported")}${data.simulated_participants ? " · " + data.simulated_participants + " simulated" : ""}`,
    ],
  ];
  document.querySelector("#stats").replaceChildren(
    ...items.map(([label, value, note]) => {
      const node = el("div", "stat");
      node.append(
        el("span", "stat-label", t(label)),
        el("span", "stat-value", value ?? 0),
        el("small", "", note),
      );
      return node;
    }),
  );
}
