const heatmapCanvas = document.getElementById("threat-heatmap");
let heatmapCtx = null;
let heatmapGrid = [];

const resizeHeatmap = () => {
  if (!heatmapCanvas) return;
  const rect = heatmapCanvas.getBoundingClientRect();
  heatmapCanvas.width = rect.width;
  heatmapCanvas.height = rect.height;
  heatmapCtx = heatmapCanvas.getContext("2d");
  renderHeatmap();
};

const colorForValue = (value) => {
  if (value > 0.7) return "rgba(239,68,68,0.85)";
  if (value > 0.4) return "rgba(255,159,67,0.85)";
  return "rgba(34,197,94,0.75)";
};

const renderHeatmap = () => {
  if (!heatmapCtx || !heatmapCanvas) return;
  heatmapCtx.clearRect(0, 0, heatmapCanvas.width, heatmapCanvas.height);
  const rows = heatmapGrid.length || 6;
  const cols = heatmapGrid[0]?.length || 10;
  const cellWidth = heatmapCanvas.width / cols;
  const cellHeight = heatmapCanvas.height / rows;

  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const value = heatmapGrid[r]?.[c] ?? Math.random();
      heatmapCtx.fillStyle = colorForValue(value);
      heatmapCtx.fillRect(c * cellWidth, r * cellHeight, cellWidth - 2, cellHeight - 2);
    }
  }
};

const setHeatmap = (grid) => {
  heatmapGrid = grid || [];
  renderHeatmap();
};

window.addEventListener("resize", resizeHeatmap);

if (heatmapCanvas) {
  resizeHeatmap();
}

window.UEBA_HEATMAP = { update: setHeatmap };
