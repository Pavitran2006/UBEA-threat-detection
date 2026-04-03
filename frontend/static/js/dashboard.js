let activityChart = null;
let anomalyChart = null;
let threatChart = null;

const eventQueue = [];
let flushHandle = null;

const fetchJson = async (url) => {
  if (!window.UEBA_AUTH) throw new Error("Auth helper missing");
  return window.UEBA_AUTH.authFetchJson(url);
};

const simulateSeries = (points, max = 60) =>
  Array.from({ length: points }, () => Math.floor(Math.random() * max) + 10);

const simulateLabels = (points) =>
  Array.from({ length: points }, (_, i) => `T-${points - i}`);

const renderList = (id, items) => {
  const el = document.getElementById(id);
  if (!el) return;
  el.innerHTML = '';
  items.forEach((item) => {
    const row = document.createElement('div');
    row.textContent = item;
    el.appendChild(row);
  });
};

const renderFeedItem = (container, event) => {
  const item = document.createElement("div");
  item.className = "feed-item";
  item.innerHTML = `
    <div class="tag">${event.type}</div>
    <div>${event.message}</div>
    <div class="muted">${event.timestamp}</div>
  `;
  container.prepend(item);
  while (container.children.length > 40) {
    container.removeChild(container.lastChild);
  }
};

const setChart = (chartRef, ctx, config) => {
  if (chartRef) {
    chartRef.data.labels = config.data.labels;
    chartRef.data.datasets[0].data = config.data.datasets[0].data;
    chartRef.update("none");
    return chartRef;
  }
  return new Chart(ctx, config);
};

const initCharts = (activityData, anomalyData) => {
  const activityCtx = document.getElementById('activity-chart');
  const anomalyCtx = document.getElementById('anomaly-chart');
  const threatCtx = document.getElementById('threat-chart');

  if (activityCtx) {
    activityChart = setChart(activityChart, activityCtx, {
      type: 'line',
      data: {
        labels: activityData.labels,
        datasets: [{ label: 'Logins', data: activityData.values, borderColor: '#00f5ff' }],
      },
      options: { responsive: true, plugins: { legend: { display: false } } },
    });
  }

  if (anomalyCtx) {
    anomalyChart = setChart(anomalyChart, anomalyCtx, {
      type: 'bar',
      data: {
        labels: anomalyData.labels,
        datasets: [{ label: 'Anomalies', data: anomalyData.values, backgroundColor: '#ef4444' }],
      },
      options: { responsive: true, plugins: { legend: { display: false } } },
    });
  }

  if (threatCtx && !threatChart) {
    threatChart = new Chart(threatCtx, {
      type: 'bar',
      data: {
        labels: ["Brute Force", "Malware", "Privilege Escalation", "Data Exfiltration"],
        datasets: [{
          label: 'Threats',
          data: [0, 0, 0, 0],
          backgroundColor: ['#00f5ff', '#ef4444', '#ff9f43', '#ff6ee7'],
        }],
      },
      options: { responsive: true, plugins: { legend: { display: false } } },
    });
  }
};

const updateRiskMeter = (score, level) => {
  const meter = document.getElementById("risk-meter");
  const valueEl = document.getElementById("risk-score");
  const levelEl = document.getElementById("risk-level");
  if (!meter || !valueEl || !levelEl) return;
  valueEl.textContent = score;
  levelEl.textContent = level;

  let color = "#22c55e";
  if (score > 70) color = "#ef4444";
  else if (score > 30) color = "#ff9f43";

  meter.style.setProperty("--risk", score);
  meter.style.setProperty("--risk-color", color);
  levelEl.style.color = color;
  valueEl.style.color = color;

  const globalRisk = document.getElementById("global-risk");
  if (globalRisk) globalRisk.textContent = level;
};

const updateThreatChart = (type) => {
  if (!threatChart) return;
  const idx = threatChart.data.labels.indexOf(type);
  if (idx >= 0) {
    threatChart.data.datasets[0].data[idx] += 1;
    threatChart.update("none");
  }
};

const updateActivityChart = (count) => {
  if (!activityChart) return;
  const data = activityChart.data.datasets[0].data;
  data[data.length - 1] += count;
  activityChart.update("none");
};

const updateAnomalyChart = (severity) => {
  if (!anomalyChart) return;
  const severityMap = { Low: 30, Medium: 60, High: 90 };
  const value = severityMap[severity] || 40;
  const data = anomalyChart.data.datasets[0].data;
  data.shift();
  data.push(value);
  anomalyChart.update("none");
};

const flushEvents = () => {
  if (!eventQueue.length) return;
  const feed = document.getElementById("live-events");
  const batch = eventQueue.splice(0, eventQueue.length);

  let loginEvents = 0;
  batch.forEach((event) => {
    if (feed) renderFeedItem(feed, event);
    if (["Suspicious Login", "Failed Login"].includes(event.type)) loginEvents += 1;
    updateThreatChart(event.type);
    updateAnomalyChart(event.severity);
    if (event.origin && event.target && window.UEBA_ATTACK_MAP) {
      window.UEBA_ATTACK_MAP.addEvent(event);
    }
  });

  if (loginEvents) updateActivityChart(loginEvents);
};

const connectEventStream = () => {
  const token = window.UEBA_AUTH?.getAccessToken?.();
  if (!token) return;

  let socket;
  const connect = () => {
    socket = new WebSocket(`${window.location.origin.replace("http", "ws")}/ws/events?token=${token}`);
    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      eventQueue.push(data);
    };
    socket.onclose = () => {
      setTimeout(connect, 2000);
    };
  };
  connect();

  if (!flushHandle) {
    flushHandle = setInterval(flushEvents, 1000);
  }
};

const init = async () => {
  let alerts = [];
  let activity = { labels: simulateLabels(10), values: simulateSeries(10) };
  let anomalies = { labels: simulateLabels(8), values: simulateSeries(8, 30) };
  let status = {
    activeUsers: 0,
    detectedThreats: 0,
    normalActivities: 0,
    systemHealth: 'Healthy',
  };

  try {
    const dashboard = await fetchJson('/dashboard-data');
    if (!dashboard) return;
    status = dashboard.status || status;
    activity = dashboard.activity || activity;
    anomalies = dashboard.anomalies || anomalies;
  } catch (err) {
    try {
      const stats = await fetchJson('/api/dashboard/stats');
      if (!stats) return;
      status.activeUsers = stats.total_users || 0;
      status.detectedThreats = stats.security_alerts || 0;
      status.normalActivities = stats.active_sessions || 0;
    } catch (_) {}
  }

  try {
    const alertData = await fetchJson('/alerts');
    if (!alertData) return;
    alerts = alertData.alerts || [];
  } catch (err) {
    alerts = ['No alerts available'];
  }

  const incidentCount = document.getElementById("incident-count");
  if (incidentCount) incidentCount.textContent = status.detectedThreats;

  renderList('threat-alerts', alerts.slice(0, 8));

  const statusEl = document.getElementById('system-status');
  if (statusEl) {
    statusEl.innerHTML = `
      <div>Active Users: ${status.activeUsers}</div>
      <div>Detected Threats: ${status.detectedThreats}</div>
      <div>Normal Activities: ${status.normalActivities}</div>
      <div>System Health: ${status.systemHealth}</div>
    `;
  }

  initCharts(activity, anomalies);

  try {
    const anomalyData = await fetchJson('/api/anomalies');
    if (anomalyData) {
      initCharts(activity, anomalyData);
    }
  } catch (_) {}

  try {
    const riskData = await fetchJson('/api/risk-score');
    if (riskData) updateRiskMeter(riskData.score, riskData.level);
  } catch (_) {}

  try {
    const attackData = await fetchJson('/api/attack-map');
    if (attackData && window.UEBA_ATTACK_MAP) {
      window.UEBA_ATTACK_MAP.update(attackData);
    }
  } catch (_) {}

  try {
    const heatData = await fetchJson('/api/heatmap');
    if (heatData?.grid && window.UEBA_HEATMAP) {
      window.UEBA_HEATMAP.update(heatData.grid);
    }
  } catch (_) {}

  try {
    const graphData = await fetchJson('/api/network-graph');
    if (graphData && window.UEBA_NETWORK_GRAPH) {
      window.UEBA_NETWORK_GRAPH.update(graphData);
    }
  } catch (_) {}

  try {
    const eventsData = await fetchJson('/api/events');
    const feed = document.getElementById("live-events");
    if (feed && eventsData?.events) {
      eventsData.events.forEach((event) => renderFeedItem(feed, event));
      eventsData.events.forEach((event) => updateThreatChart(event.type));
    }
  } catch (_) {}

  connectEventStream();

  document.querySelectorAll('.toggle-btn').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const userId = btn.dataset.userId;
      const action = btn.dataset.action;
      if (!window.UEBA_AUTH) return;
      await window.UEBA_AUTH.authFetch(`/api/admin/users/${userId}/${action}`, {
        method: 'POST',
      });
      window.location.reload();
    });
  });
};

document.addEventListener('DOMContentLoaded', init);
