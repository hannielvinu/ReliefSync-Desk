import { el } from "./ui.js";
let map,
  layer,
  lines,
  markers = new Map(),
  firstFit = false;
export function initMap() {
  if (!window.L) return;
  map = L.map("map", { zoomControl: true }).setView([12.972, 80.227], 12);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution:
      '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 18,
  })
    .on(
      "tileerror",
      () => (document.querySelector("#tile-error").hidden = false),
    )
    .addTo(map);
  layer = L.layerGroup().addTo(map);
  lines = L.layerGroup().addTo(map);
  document.querySelector("#fit-map").onclick = fitMap;
  new ResizeObserver(() => map.invalidateSize()).observe(
    document.querySelector("#map"),
  );
}
export function renderMap(cards, matches, onSelect) {
  if (!map) return;
  layer.clearLayers();
  lines.clearLayers();
  markers.clear();
  for (const card of cards) {
    if (
      card.lat == null ||
      card.status === "duplicate" ||
      card.status === "rejected"
    )
      continue;
    const pin = el(
      "div",
      `pin ${card.intent} u${card.urgency}`,
      `${card.intent === "offer" ? "+" : "!"}${card.urgency}`,
    );
    const marker = L.marker([card.lat, card.lng], {
      icon: L.divIcon({
        className: "map-marker",
        html: pin,
        iconSize: [30, 30],
        iconAnchor: [15, 15],
      }),
      title: `${card.intent}: ${card.item_en} — approximate`,
      alt: `${card.intent}: ${card.item_en}`,
    });
    const popup = el("div");
    popup.append(
      el("strong", "", card.item_en),
      el("p", "", card.location_text),
    );
    marker.bindPopup(popup).on("click", () => onSelect(card.id));
    marker.addTo(layer);
    markers.set(card.id, marker);
  }
  for (const match of matches) {
    if (
      !["suggested", "approved"].includes(match.status) ||
      match.need.lat == null ||
      match.offer.lat == null
    )
      continue;
    L.polyline(
      [
        [match.need.lat, match.need.lng],
        [match.offer.lat, match.offer.lng],
      ],
      {
        color: "#0e7c86",
        weight: 2,
        dashArray: match.status === "suggested" ? "5 7" : null,
        opacity: 0.7,
      },
    ).addTo(lines);
  }
  if (!firstFit && markers.size) {
    fitMap();
    firstFit = true;
  }
}
export function fitMap() {
  if (!map || !markers.size) return;
  const bounds = L.latLngBounds(
    [...markers.values()].map((marker) => marker.getLatLng()),
  );
  map.fitBounds(bounds.pad(0.2), { maxZoom: 14, animate: false });
}
export function highlight(id) {
  for (const [key, marker] of markers) {
    marker
      .getElement()
      ?.querySelector(".pin")
      ?.classList.toggle("highlight", key === id);
  }
  const marker = markers.get(id);
  if (marker)
    map.panTo(marker.getLatLng(), {
      animate: !matchMedia("(prefers-reduced-motion:reduce)").matches,
    });
}
