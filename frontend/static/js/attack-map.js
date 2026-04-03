const mapContainer = document.getElementById("world-map");
const attackCanvas = document.getElementById("attack-canvas");
const tooltip = document.getElementById("attack-tooltip");
const countryPanel = document.getElementById("country-panel");
const countryNameEl = document.getElementById("country-name");
const countryMetaEl = document.getElementById("country-meta");
const countryEventsEl = document.getElementById("country-events");
const countryCloseBtn = document.getElementById("country-close");

let attackCtx = null;
let attacks = [];
let countryCentroids = new Map();
let attackCounts = new Map();
let projection = null;
let animationId = null;
let attackHover = false;
let currentTransform = null;
let svgGroup = null;

const NATURAL_EARTH_URL = "/static/data/ne_50m_admin_0_countries.geojson";

const resizeCanvas = () => {
  if (!attackCanvas) return;
  const rect = attackCanvas.getBoundingClientRect();
  attackCanvas.width = rect.width;
  attackCanvas.height = rect.height;
  attackCtx = attackCanvas.getContext("2d");
};

const drawAttack = (ctx, attack, t) => {
  if (!projection) return;
  const start = projection([attack.origin.lon, attack.origin.lat]);
  const end = projection([attack.target.lon, attack.target.lat]);
  if (!start || !end) return;

  const progress = (Math.sin(t + attack.phase) + 1) / 2;
  ctx.strokeStyle = attack.color;
  ctx.shadowColor = attack.color;
  ctx.shadowBlur = 8;
  ctx.lineWidth = 1.4;

  ctx.beginPath();
  ctx.moveTo(start[0], start[1]);
  ctx.quadraticCurveTo(
    (start[0] + end[0]) / 2,
    Math.min(start[1], end[1]) - 50,
    end[0],
    end[1]
  );
  ctx.stroke();

  ctx.shadowBlur = 0;
  const pulse = 2.2 + Math.sin(t * 2 + attack.phase) * 1.2;
  ctx.fillStyle = attack.color;
  ctx.beginPath();
  ctx.arc(start[0], start[1], pulse, 0, Math.PI * 2);
  ctx.fill();

  ctx.globalAlpha = 0.4;
  ctx.beginPath();
  ctx.arc(start[0], start[1], pulse + 4, 0, Math.PI * 2);
  ctx.fill();
  ctx.globalAlpha = 1;

  ctx.fillStyle = "rgba(0,245,255,0.85)";
  ctx.beginPath();
  ctx.arc(
    start[0] + (end[0] - start[0]) * progress,
    start[1] + (end[1] - start[1]) * progress,
    2.1,
    0,
    Math.PI * 2
  );
  ctx.fill();
};

const renderAttacks = () => {
  if (!attackCtx) return;
  const { width, height } = attackCanvas;
  attackCtx.setTransform(1, 0, 0, 1, 0, 0);
  attackCtx.clearRect(0, 0, width, height);

  if (currentTransform) {
    attackCtx.setTransform(
      currentTransform.k,
      0,
      0,
      currentTransform.k,
      currentTransform.x,
      currentTransform.y
    );
  }

  const t = Date.now() / 1000;
  attacks.forEach((attack) => drawAttack(attackCtx, attack, t));
  animationId = requestAnimationFrame(renderAttacks);
};

const setAttacks = (data) => {
  attacks = (data || []).map((attack, idx) => ({
    ...attack,
    phase: idx * 0.6,
    color:
      attack.type === "Malware"
        ? "rgba(239,68,68,0.85)"
        : attack.type === "Privilege Escalation"
        ? "rgba(255,159,67,0.85)"
        : attack.type === "Data Exfiltration"
        ? "rgba(255,110,231,0.85)"
        : "rgba(0,245,255,0.85)",
  }));

  attackCounts = new Map();
  attacks.forEach((attack) => {
    const originName = attack.origin.country || attack.origin.name;
    const targetName = attack.target.country || attack.target.name;
    if (originName) attackCounts.set(originName, (attackCounts.get(originName) || 0) + 1);
    if (targetName) attackCounts.set(targetName, (attackCounts.get(targetName) || 0) + 1);
  });

  if (!animationId) renderAttacks();
};

const addAttack = (attack) => {
  const formatted = formatAttack(attack);
  attacks.unshift({
    ...formatted,
    phase: Math.random() * 2,
    color:
      formatted.type === "Malware"
        ? "rgba(239,68,68,0.85)"
        : formatted.type === "Privilege Escalation"
        ? "rgba(255,159,67,0.85)"
        : formatted.type === "Data Exfiltration"
        ? "rgba(255,110,231,0.85)"
        : "rgba(0,245,255,0.85)",
  });
  attacks = attacks.slice(0, 60);
  const originName = formatted.origin.country || formatted.origin.name;
  const targetName = formatted.target.country || formatted.target.name;
  if (originName) attackCounts.set(originName, (attackCounts.get(originName) || 0) + 1);
  if (targetName) attackCounts.set(targetName, (attackCounts.get(targetName) || 0) + 1);
};

const formatAttack = (entry) => {
  if (entry.origin && entry.target && entry.origin.lat) return entry;

  const origin = countryCentroids.get(entry.origin) || {};
  const target = countryCentroids.get(entry.target) || {};
  return {
    origin: {
      lat: origin.lat || 0,
      lon: origin.lon || 0,
      country: entry.origin,
    },
    target: {
      lat: target.lat || 0,
      lon: target.lon || 0,
      country: entry.target,
    },
    type: entry.type,
    timestamp: entry.timestamp || "",
  };
};

const threatLevel = (count) => {
  if (count > 6) return "High";
  if (count > 2) return "Medium";
  return "Low";
};

const updateTooltip = (countryName, x, y) => {
  if (!tooltip) return;
  if (attackHover) return;
  if (!countryName) {
    tooltip.classList.remove("visible");
    return;
  }
  const count = attackCounts.get(countryName) || 0;
  const level = threatLevel(count);
  tooltip.innerHTML = `
    <div><strong>${countryName}</strong></div>
    <div>Attacks: ${count}</div>
    <div class="muted">Threat Level: ${level}</div>
  `;
  tooltip.style.left = `${x}px`;
  tooltip.style.top = `${y}px`;
  tooltip.classList.add("visible");
};

const showAttackTooltip = (attack, x, y) => {
  if (!tooltip) return;
  if (!attack) {
    attackHover = false;
    return;
  }
  attackHover = true;
  tooltip.innerHTML = `
    <div><strong>${attack.type}</strong></div>
    <div>${attack.origin.country} → ${attack.target.country}</div>
    <div class="muted">${attack.timestamp}</div>
  `;
  tooltip.style.left = `${x}px`;
  tooltip.style.top = `${y}px`;
  tooltip.classList.add("visible");
};

const findNearestAttack = (x, y) => {
  if (!projection || !attacks.length) return null;
  let closest = null;
  let minDist = 14;
  attacks.forEach((attack) => {
    const start = projection([attack.origin.lon, attack.origin.lat]);
    const end = projection([attack.target.lon, attack.target.lat]);
    if (!start || !end) return;
    const distStart = Math.hypot(start[0] - x, start[1] - y);
    const distEnd = Math.hypot(end[0] - x, end[1] - y);
    const dist = Math.min(distStart, distEnd);
    if (dist < minDist) {
      minDist = dist;
      closest = attack;
    }
  });
  return closest;
};

const renderMap = (geojson) => {
  if (!mapContainer || !window.d3) return;
  mapContainer.innerHTML = "";

  const width = mapContainer.clientWidth;
  const height = mapContainer.clientHeight;
  const svg = d3
    .select(mapContainer)
    .append("svg")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("preserveAspectRatio", "xMidYMid meet");

  svgGroup = svg.append("g");

  projection = d3.geoNaturalEarth1().fitSize([width, height], geojson);
  const path = d3.geoPath(projection);

  countryCentroids = new Map();
  geojson.features.forEach((feature) => {
    const name = feature.properties?.name || feature.properties?.NAME || feature.properties?.admin;
    if (!name) return;
    const centroid = path.centroid(feature);
    const coords = projection.invert(centroid);
    if (coords) {
      countryCentroids.set(name, { lon: coords[0], lat: coords[1] });
    }
  });

  svgGroup
    .selectAll("path")
    .data(geojson.features)
    .enter()
    .append("path")
    .attr("d", path)
    .on("mousemove", function (event, d) {
      const name = d.properties?.name || d.properties?.NAME || d.properties?.admin || "Unknown";
      d3.select(this).classed("hovered", true);
      const rect = mapContainer.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      updateTooltip(name, x, y);
    })
    .on("mouseleave", function () {
      d3.select(this).classed("hovered", false);
      updateTooltip(null);
    })
    .on("click", function (event, d) {
      const name = d.properties?.name || d.properties?.NAME || d.properties?.admin || "Unknown";
      showCountryPanel(name);
    });

  const zoom = d3
    .zoom()
    .scaleExtent([1, 6])
    .on("zoom", (event) => {
      currentTransform = event.transform;
      svgGroup.attr("transform", currentTransform);
    });

  svg.call(zoom);
  currentTransform = d3.zoomIdentity;
};

const showCountryPanel = (countryName) => {
  if (!countryPanel || !countryEventsEl || !countryNameEl || !countryMetaEl) return;
  const relevant = attacks.filter(
    (attack) => attack.origin.country === countryName || attack.target.country === countryName
  );
  const count = relevant.length;
  const level = threatLevel(count);

  countryNameEl.textContent = countryName;
  countryMetaEl.textContent = `Threat Level: ${level} • Attacks: ${count}`;
  countryEventsEl.innerHTML = "";

  relevant.slice(0, 8).forEach((attack) => {
    const item = document.createElement("div");
    item.className = "panel-item";
    item.innerHTML = `
      <div><strong>${attack.type}</strong></div>
      <div>${attack.origin.country} → ${attack.target.country}</div>
      <div class="muted">${attack.timestamp}</div>
    `;
    countryEventsEl.appendChild(item);
  });

  countryPanel.classList.add("open");
  countryPanel.setAttribute("aria-hidden", "false");
};

const loadGeoJSON = async () => {
  if (!mapContainer) return;
  const response = await fetch(NATURAL_EARTH_URL);
  const data = await response.json();
  renderMap(data);
};

window.addEventListener("resize", () => {
  resizeCanvas();
  if (mapContainer && projection) {
    loadGeoJSON();
  }
});

if (mapContainer && attackCanvas) {
  resizeCanvas();
  loadGeoJSON();
  renderAttacks();
}

if (mapContainer) {
  mapContainer.addEventListener("mousemove", (event) => {
    const rect = mapContainer.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    const attack = findNearestAttack(x, y);
    if (attack) {
      showAttackTooltip(attack, x, y);
    } else if (attackHover) {
      tooltip.classList.remove("visible");
      attackHover = false;
    }
  });
  mapContainer.addEventListener("mouseleave", () => {
    if (tooltip) tooltip.classList.remove("visible");
    attackHover = false;
  });
}

if (countryCloseBtn) {
  countryCloseBtn.addEventListener("click", () => {
    countryPanel?.classList.remove("open");
    countryPanel?.setAttribute("aria-hidden", "true");
  });
}

window.UEBA_ATTACK_MAP = {
  update: (data) => {
    const formatted = (Array.isArray(data) ? data : data?.attacks || []).map(formatAttack);
    setAttacks(formatted);
  },
  addEvent: (event) => addAttack(event),
};
