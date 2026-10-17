"use strict";

const PRODUCT_META = {
  "89": { label: "89#", title: "89# 汽油", color: "#8b5cf6" },
  "92": { label: "92#", title: "92# 汽油", color: "#e11d48" },
  "95": { label: "95#", title: "95# 汽油", color: "#f97316" },
  "98": { label: "98#", title: "98# 汽油", color: "#d946ef" },
  "0": { label: "0#", title: "0# 柴油", color: "#2563eb" },
  "-10": { label: "-10#", title: "-10# 柴油", color: "#0ea5e9" },
  "-20": { label: "-20#", title: "-20# 柴油", color: "#14b8a6" },
  "-35": { label: "-35#", title: "-35# 柴油", color: "#10b981" },
  E92: { label: "E92", title: "E92 乙醇汽油", color: "#a855f7" },
  E95: { label: "E95", title: "E95 乙醇汽油", color: "#ec4899" },
  E98: { label: "E98", title: "E98 乙醇汽油", color: "#f43f5e" },
  aipao95: { label: "爱跑95", title: "爱跑 95", color: "#fb7185" },
  aipao98: { label: "爱跑98", title: "爱跑 98", color: "#be123c" },
  aipao_e92: { label: "爱跑E92", title: "爱跑 E92", color: "#7c3aed" },
  aipao_e95: { label: "爱跑E95", title: "爱跑 E95", color: "#db2777" },
  aipao_e98: { label: "爱跑E98", title: "爱跑 E98", color: "#e11d48" },
};

const PRODUCT_ORDER = Object.keys(PRODUCT_META);
const ZONE_NUMERALS = { 一: 1, 二: 2, 三: 3, 四: 4, 五: 5, 六: 6, 七: 7, 八: 8, 九: 9, 十: 10 };

const state = {
  index: null,
  provinces: [],
  province: null,
  rows: [],
  zones: [],
  zone: "",
  product: "92",
  rangeStart: "",
  rangeEnd: "",
};

const el = {
  meta: document.getElementById("meta-text"),
  footerMeta: document.getElementById("footer-meta"),
  province: document.getElementById("province-select"),
  zoneField: document.getElementById("zone-field"),
  zoneTabs: document.getElementById("zone-tabs"),
  datetimeField: document.getElementById("datetime-field"),
  datetimeTrigger: document.getElementById("datetime-trigger"),
  datetimePopover: document.getElementById("datetime-popover"),
  datetimeLabel: document.getElementById("datetime-label"),
  rangeStartInput: document.getElementById("range-start"),
  rangeEndInput: document.getElementById("range-end"),
  pickerHint: document.getElementById("picker-hint"),
  applyFilter: document.getElementById("apply-filter"),
  latestDate: document.getElementById("latest-date"),
  cards: document.getElementById("cards"),
  chips: document.getElementById("product-chips"),
  chart: document.getElementById("chart"),
  chartWrap: document.getElementById("chart-wrap"),
  tooltip: document.getElementById("chart-tooltip"),
  chartSubtitle: document.getElementById("chart-subtitle"),
  chartEmpty: document.getElementById("chart-empty"),
  table: document.getElementById("history-table"),
  tableSubtitle: document.getElementById("table-subtitle"),
  tableCount: document.getElementById("table-count"),
  tableEmpty: document.getElementById("table-empty"),
};

function metaFor(key) {
  return PRODUCT_META[key] || { label: key, title: key, color: "#94a3b8" };
}

function productRank(key) {
  const index = PRODUCT_ORDER.indexOf(key);
  return index === -1 ? 999 : index;
}

function zoneRank(zone) {
  for (const char of zone) {
    if (ZONE_NUMERALS[char]) return ZONE_NUMERALS[char];
  }
  return 99;
}

function formatDate(value) {
  return String(value || "").replaceAll("-", "/");
}

function formatDateTime(value) {
  if (!value) return "未知";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

function priceText(value) {
  return Number.isFinite(value) ? value.toFixed(2) : "—";
}

function deltaText(delta) {
  if (!Number.isFinite(delta) || Math.abs(delta) < 0.005) return "持平";
  return `${delta > 0 ? "+" : ""}${delta.toFixed(2)}`;
}

function deltaClass(delta) {
  if (!Number.isFinite(delta) || Math.abs(delta) < 0.005) return "flat";
  return delta > 0 ? "up" : "down";
}

function zoneRows() {
  return state.rows.filter((row) => !state.zones.length || row.zone === state.zone);
}

function rangeBounds() {
  const dates = zoneRows().map((row) => row.date).filter(Boolean).sort();
  return { min: dates[0] || "", max: dates[dates.length - 1] || "" };
}

function rangeDescription() {
  if (!state.rangeStart || !state.rangeEnd) return "全部时间";
  return `${formatDate(state.rangeStart.slice(0, 10))} – ${formatDate(state.rangeEnd.slice(0, 10))}`;
}

function syncRangeInputs() {
  el.rangeStartInput.value = state.rangeStart;
  el.rangeEndInput.value = state.rangeEnd;
  el.pickerHint.textContent = "选择后点击右侧「应用」";
  el.pickerHint.classList.remove("error");
}

function renderRange() {
  const label =
    state.rangeStart && state.rangeEnd
      ? `${formatDateTime(new Date(state.rangeStart))} → ${formatDateTime(new Date(state.rangeEnd))}`
      : "全部时间";
  el.datetimeLabel.textContent = label;
  el.datetimeLabel.title = label;
  syncRangeInputs();
}

function openPopover() {
  syncRangeInputs();
  el.datetimePopover.hidden = false;
  el.datetimeTrigger.setAttribute("aria-expanded", "true");
}

function closePopover() {
  el.datetimePopover.hidden = true;
  el.datetimeTrigger.setAttribute("aria-expanded", "false");
}

function applyPreset(kind) {
  const { min, max } = rangeBounds();
  if (!min || !max) return;
  let start = min;
  if (kind === "1y" || kind === "3y") {
    const latest = new Date(`${max}T00:00:00Z`);
    latest.setUTCFullYear(latest.getUTCFullYear() - (kind === "1y" ? 1 : 3));
    const candidate = latest.toISOString().slice(0, 10);
    start = candidate < min ? min : candidate;
  }
  el.rangeStartInput.value = `${start}T00:00`;
  el.rangeEndInput.value = `${max}T23:59`;
  el.pickerHint.textContent = "已套用快捷范围，点击「应用」生效";
  el.pickerHint.classList.remove("error");
}

function applyRange() {
  const start = el.rangeStartInput.value;
  const end = el.rangeEndInput.value;
  if (!start || !end) {
    el.pickerHint.textContent = "请选择开始和结束时间";
    el.pickerHint.classList.add("error");
    return;
  }
  if (start.slice(0, 10) > end.slice(0, 10)) {
    el.pickerHint.textContent = "开始时间不能晚于结束时间";
    el.pickerHint.classList.add("error");
    return;
  }
  state.rangeStart = start;
  state.rangeEnd = end;
  closePopover();
  renderAll();
}

function visibleRows() {
  const rows = zoneRows();
  const start = state.rangeStart ? state.rangeStart.slice(0, 10) : "";
  const end = state.rangeEnd ? state.rangeEnd.slice(0, 10) : "";
  return rows.filter((row) => (!start || row.date >= start) && (!end || row.date <= end));
}

function productsIn(rows) {
  const present = new Set();
  for (const row of rows) {
    for (const key of Object.keys(row)) {
      if (key !== "date" && key !== "zone" && Number.isFinite(row[key])) present.add(key);
    }
  }
  return [...present].sort((a, b) => productRank(a) - productRank(b));
}

async function init() {
  el.province.addEventListener("change", () => loadProvince(el.province.value));

  el.datetimeTrigger.addEventListener("click", () => {
    if (el.datetimePopover.hidden) openPopover();
    else closePopover();
  });

  el.datetimePopover.addEventListener("click", (event) => {
    const preset = event.target.closest("button[data-preset]");
    if (preset) applyPreset(preset.dataset.preset);
  });

  el.applyFilter.addEventListener("click", applyRange);

  document.addEventListener("click", (event) => {
    if (el.datetimePopover.hidden || el.datetimeField.contains(event.target)) return;
    closePopover();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !el.datetimePopover.hidden) closePopover();
  });

  try {
    const response = await fetch("data/index.json", { cache: "no-cache" });
    if (!response.ok) throw new Error(`index.json HTTP ${response.status}`);
    state.index = await response.json();
    state.provinces = Array.isArray(state.index.provinces) ? state.index.provinces : [];
    if (!state.provinces.length) {
      showEmpty("还没有采集到数据。请先运行一次采集脚本。");
      return;
    }
    for (const province of state.provinces) {
      const option = document.createElement("option");
      option.value = province.slug;
      option.textContent = `${province.name} · ${province.records} 条`;
      el.province.appendChild(option);
    }
    const requested = new URLSearchParams(location.search).get("p");
    const initial =
      state.provinces.find((item) => item.slug === requested) ||
      state.provinces.find((item) => item.slug === "shanghai") ||
      state.provinces[0];
    await loadProvince(initial.slug);
  } catch (error) {
    console.error(error);
    showEmpty(`数据加载失败：${error.message}`);
  }
}

function showEmpty(message) {
  el.meta.textContent = message;
  el.cards.innerHTML = "";
  el.chartEmpty.hidden = false;
  el.chartEmpty.textContent = message;
  el.tableEmpty.hidden = false;
  el.tableEmpty.textContent = message;
}

async function loadProvince(slug) {
  const entry = state.provinces.find((item) => item.slug === slug);
  if (!entry) return;
  state.province = entry;
  el.province.value = slug;
  el.meta.textContent = "正在加载…";

  try {
    const version = encodeURIComponent(state.index.generated_at || "");
    const response = await fetch(`data/${entry.file}?v=${version}`, { cache: "no-cache" });
    if (!response.ok) throw new Error(`${entry.file} HTTP ${response.status}`);
    const rows = await response.json();
    state.rows = Array.isArray(rows) ? rows.filter((row) => row && row.date) : [];
    state.zones = [...new Set(state.rows.map((row) => row.zone).filter(Boolean))].sort(
      (a, b) => zoneRank(a) - zoneRank(b) || a.localeCompare(b, "zh-CN"),
    );
    state.zone = state.zones[0] || "";
    const products = productsIn(zoneRows());
    state.product = products.includes(state.product) ? state.product : products[0] || "92";
    const { min, max } = rangeBounds();
    state.rangeStart = min ? `${min}T00:00` : "";
    state.rangeEnd = max ? `${max}T23:59` : "";
    closePopover();
    history.replaceState(null, "", `?p=${encodeURIComponent(slug)}`);
    renderAll();
  } catch (error) {
    console.error(error);
    showEmpty(`加载 ${entry.name} 失败：${error.message}`);
  }
}

function renderAll() {
  renderMeta();
  renderZones();
  renderRange();
  renderCards();
  renderChips();
  renderChart();
  renderTable();
}

function renderMeta() {
  const index = state.index;
  el.meta.textContent = `更新于 ${formatDateTime(index.generated_at)} · ${index.provinces.length} 个省份`;
  el.footerMeta.textContent = `共 ${index.total_records || 0} 条调价记录 · 页面生成于 ${formatDateTime(index.generated_at)}`;
}

function renderZones() {
  el.zoneTabs.innerHTML = "";
  el.zoneField.hidden = state.zones.length <= 1;
  if (state.zones.length <= 1) return;
  for (const zone of state.zones) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = zone;
    button.classList.toggle("active", zone === state.zone);
    button.addEventListener("click", () => {
      state.zone = zone;
      const products = productsIn(zoneRows());
      if (!products.includes(state.product)) state.product = products[0] || "92";
      renderAll();
    });
    el.zoneTabs.appendChild(button);
  }
}

function latestRows(rows) {
  const byDate = new Map();
  for (const row of rows) {
    const current = byDate.get(row.date);
    if (!current || row.date >= current.date) byDate.set(row.date, row);
  }
  return [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date));
}

function renderCards() {
  const rows = zoneRows();
  const products = productsIn(rows);
  el.cards.innerHTML = "";
  if (!rows.length || !products.length) {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "暂无价格数据";
    el.cards.appendChild(empty);
    return;
  }

  const ordered = latestRows(rows);
  const latest = ordered[ordered.length - 1];
  const previous = ordered.length > 1 ? ordered[ordered.length - 2] : null;
  el.latestDate.textContent = `${state.province.name}${state.zone ? ` · ${state.zone}` : ""} · ${formatDate(latest.date)} 调价`;

  for (const key of products) {
    const meta = metaFor(key);
    const value = latest[key];
    if (!Number.isFinite(value)) continue;
    const previousValue = previous && Number.isFinite(previous[key]) ? previous[key] : null;
    const deltaValue = previousValue === null ? null : Math.round((value - previousValue) * 100) / 100;

    const card = document.createElement("button");
    card.type = "button";
    card.className = "price-card";
    card.style.setProperty("--accent", meta.color);
    card.classList.toggle("active", key === state.product);
    card.addEventListener("click", () => {
      state.product = key;
      renderCards();
      renderChips();
      renderChart();
      document.querySelector(".chart-panel").scrollIntoView({ behavior: "smooth", block: "start" });
    });

    const label = document.createElement("span");
    label.className = "label";
    label.textContent = meta.title;

    const valueLine = document.createElement("span");
    valueLine.className = "value";
    valueLine.textContent = priceText(value);
    const unit = document.createElement("span");
    unit.className = "unit";
    unit.textContent = "元/升";
    valueLine.appendChild(unit);

    const delta = document.createElement("span");
    delta.className = `delta ${deltaClass(deltaValue === null ? 0 : deltaValue)}`;
    delta.textContent = deltaValue === null ? "首期" : deltaText(deltaValue);

    card.append(label, valueLine, delta);
    el.cards.appendChild(card);
  }
}

function renderChips() {
  const products = productsIn(zoneRows());
  el.chips.innerHTML = "";
  for (const key of products) {
    const meta = metaFor(key);
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = meta.label;
    button.style.setProperty("--accent", meta.color);
    button.classList.toggle("active", key === state.product);
    button.addEventListener("click", () => {
      state.product = key;
      renderCards();
      renderChips();
      renderChart();
    });
    el.chips.appendChild(button);
  }
}

function svgElement(name, attrs = {}) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", name);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value));
  return node;
}

function renderChart() {
  const svg = el.chart;
  svg.innerHTML = "";
  el.tooltip.hidden = true;

  const rows = visibleRows();
  const points = rows
    .filter((row) => Number.isFinite(row[state.product]))
    .map((row) => ({ date: row.date, value: row[state.product] }))
    .sort((a, b) => a.date.localeCompare(b.date));

  const meta = metaFor(state.product);
  el.chartSubtitle.textContent = `${state.province.name}${state.zone ? ` · ${state.zone}` : ""} · ${meta.title} · ${points.length} 个调价周期`;
  if (points.length < 2) {
    el.chartEmpty.hidden = false;
    el.chartEmpty.textContent = "当前范围内没有足够的记录。";
    return;
  }
  el.chartEmpty.hidden = true;

  const W = 920;
  const H = 340;
  const margin = { left: 56, right: 18, top: 18, bottom: 38 };
  const innerW = W - margin.left - margin.right;
  const innerH = H - margin.top - margin.bottom;
  const minValue = Math.min(...points.map((point) => point.value));
  const maxValue = Math.max(...points.map((point) => point.value));
  const pad = Math.max(0.05, (maxValue - minValue) * 0.18);
  const yMin = minValue - pad;
  const yMax = maxValue + pad;
  const xMin = new Date(`${points[0].date}T00:00:00Z`).getTime();
  const xMax = new Date(`${points[points.length - 1].date}T00:00:00Z`).getTime();
  const span = Math.max(1, xMax - xMin);

  const x = (date) => margin.left + ((new Date(`${date}T00:00:00Z`).getTime() - xMin) / span) * innerW;
  const y = (value) => margin.top + innerH - ((value - yMin) / (yMax - yMin)) * innerH;

  const defs = svgElement("defs");
  const gradient = svgElement("linearGradient", { id: "area-gradient", x1: "0", y1: "0", x2: "0", y2: "1" });
  const stop1 = svgElement("stop", { offset: "0%", "stop-color": meta.color, "stop-opacity": "0.22" });
  const stop2 = svgElement("stop", { offset: "100%", "stop-color": meta.color, "stop-opacity": "0.01" });
  gradient.append(stop1, stop2);
  defs.appendChild(gradient);
  svg.appendChild(defs);

  for (let i = 0; i <= 4; i += 1) {
    const value = yMin + ((yMax - yMin) * i) / 4;
    const lineY = y(value);
    svg.appendChild(
      svgElement("line", {
        x1: margin.left,
        y1: lineY,
        x2: W - margin.right,
        y2: lineY,
        stroke: "currentColor",
        "stroke-opacity": "0.1",
        "stroke-dasharray": i === 0 ? "0" : "3 4",
      }),
    );
    const label = svgElement("text", {
      x: margin.left - 10,
      y: lineY + 4,
      "text-anchor": "end",
      "font-size": "11",
      fill: "currentColor",
      "fill-opacity": "0.55",
    });
    label.textContent = value.toFixed(2);
    svg.appendChild(label);
  }

  const tickCount = Math.min(6, points.length);
  const tickIndexes = new Set();
  for (let i = 0; i < tickCount; i += 1) {
    tickIndexes.add(Math.round((i * (points.length - 1)) / Math.max(1, tickCount - 1)));
  }
  for (const index of tickIndexes) {
    const point = points[index];
    const tx = x(point.date);
    const label = svgElement("text", {
      x: tx,
      y: H - 12,
      "text-anchor": "middle",
      "font-size": "11",
      fill: "currentColor",
      "fill-opacity": "0.55",
    });
    label.textContent = point.date.slice(2, 7);
    svg.appendChild(label);
  }

  const linePath = points.map((point, index) => `${index === 0 ? "M" : "L"}${x(point.date).toFixed(2)},${y(point.value).toFixed(2)}`).join(" ");
  const areaPath = `${linePath} L${x(points[points.length - 1].date).toFixed(2)},${H - margin.bottom} L${x(points[0].date).toFixed(2)},${H - margin.bottom} Z`;
  svg.appendChild(svgElement("path", { d: areaPath, fill: "url(#area-gradient)" }));
  svg.appendChild(
    svgElement("path", {
      d: linePath,
      fill: "none",
      stroke: meta.color,
      "stroke-width": "2.4",
      "stroke-linecap": "round",
      "stroke-linejoin": "round",
    }),
  );

  const hover = svgElement("circle", {
    r: "4.5",
    fill: meta.color,
    stroke: "var(--card)",
    "stroke-width": "2",
    opacity: "0",
  });
  svg.appendChild(hover);

  const overlay = svgElement("rect", {
    x: margin.left,
    y: margin.top,
    width: innerW,
    height: innerH,
    fill: "transparent",
    style: "cursor: crosshair",
  });
  svg.appendChild(overlay);

  overlay.addEventListener("mousemove", (event) => {
    const rect = svg.getBoundingClientRect();
    const localX = ((event.clientX - rect.left) / rect.width) * W;
    let nearest = points[0];
    let distance = Infinity;
    for (const point of points) {
      const current = Math.abs(x(point.date) - localX);
      if (current < distance) {
        distance = current;
        nearest = point;
      }
    }
    const px = x(nearest.date);
    const py = y(nearest.value);
    hover.setAttribute("cx", px);
    hover.setAttribute("cy", py);
    hover.setAttribute("opacity", "1");
    el.tooltip.hidden = false;
    el.tooltip.innerHTML = "";
    const dateLine = document.createElement("div");
    dateLine.className = "tip-date";
    dateLine.textContent = formatDate(nearest.date);
    const priceLine = document.createElement("div");
    priceLine.className = "tip-price";
    priceLine.textContent = `${priceText(nearest.value)} 元/升`;
    el.tooltip.append(dateLine, priceLine);
    const left = (px / W) * rect.width;
    const top = (py / H) * rect.height;
    el.tooltip.style.left = `${Math.min(rect.width - 130, Math.max(8, left + 12))}px`;
    el.tooltip.style.top = `${Math.max(8, top - 58)}px`;
  });

  overlay.addEventListener("mouseleave", () => {
    hover.setAttribute("opacity", "0");
    el.tooltip.hidden = true;
  });
}

function renderTable() {
  const rows = visibleRows().slice().sort((a, b) => b.date.localeCompare(a.date));
  const products = productsIn(zoneRows());
  const thead = el.table.querySelector("thead");
  const tbody = el.table.querySelector("tbody");
  thead.innerHTML = "";
  tbody.innerHTML = "";
  el.tableSubtitle.textContent = `${state.province.name}${state.zone ? ` · ${state.zone}` : ""} · ${rangeDescription()}`;
  el.tableCount.textContent = `${rows.length} 条记录`;
  el.tableEmpty.hidden = rows.length > 0;

  const headerRow = document.createElement("tr");
  const dateHeader = document.createElement("th");
  dateHeader.textContent = "调价日期";
  headerRow.appendChild(dateHeader);
  for (const key of products) {
    const th = document.createElement("th");
    th.textContent = metaFor(key).title;
    headerRow.appendChild(th);
  }
  thead.appendChild(headerRow);

  const ascending = rows.slice().sort((a, b) => a.date.localeCompare(b.date));
  const indexByDate = new Map(ascending.map((row, index) => [row.date, index]));

  for (const row of rows) {
    const tr = document.createElement("tr");
    const dateCell = document.createElement("td");
    dateCell.className = "date";
    dateCell.textContent = formatDate(row.date);
    tr.appendChild(dateCell);
    for (const key of products) {
      const cell = document.createElement("td");
      const value = row[key];
      if (Number.isFinite(value)) {
        cell.textContent = priceText(value);
        cell.className = "price";
        const index = indexByDate.get(row.date) ?? -1;
        const before = index > 0 ? ascending[index - 1][key] : null;
        if (Number.isFinite(before)) {
          const delta = Math.round((value - before) * 100) / 100;
          if (Math.abs(delta) >= 0.005) cell.classList.add(delta > 0 ? "up" : "down");
        }
      } else {
        cell.textContent = "—";
      }
      tr.appendChild(cell);
    }
    tbody.appendChild(tr);
  }
}

document.addEventListener("DOMContentLoaded", init);
