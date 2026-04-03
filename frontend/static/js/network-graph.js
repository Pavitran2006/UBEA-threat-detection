const graphContainer = document.getElementById("network-graph");
let graphScene = null;
let graphCamera = null;
let graphRenderer = null;
let graphNodes = [];
let graphLines = null;

const initGraph = () => {
  if (!graphContainer || !window.THREE) return;
  const width = graphContainer.clientWidth;
  const height = graphContainer.clientHeight;

  graphScene = new THREE.Scene();
  graphCamera = new THREE.PerspectiveCamera(60, width / height, 0.1, 1000);
  graphCamera.position.set(0, 0, 60);

  graphRenderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  graphRenderer.setSize(width, height);
  graphRenderer.setPixelRatio(window.devicePixelRatio || 1);
  graphContainer.innerHTML = "";
  graphContainer.appendChild(graphRenderer.domElement);

  const ambient = new THREE.AmbientLight(0x00f5ff, 0.6);
  const point = new THREE.PointLight(0xffffff, 0.8);
  point.position.set(30, 40, 50);
  graphScene.add(ambient, point);

  animateGraph();
};

const buildGraph = (data) => {
  if (!graphScene) return;
  graphNodes.forEach((node) => graphScene.remove(node));
  if (graphLines) graphScene.remove(graphLines);
  graphNodes = [];

  const nodes = data?.nodes || [];
  const links = data?.links || [];

  const sphereGeo = new THREE.SphereGeometry(1.2, 16, 16);

  nodes.forEach((node) => {
    const color = node.suspicious ? 0xef4444 : node.type === "server" ? 0x00f5ff : 0x22c55e;
    const material = new THREE.MeshStandardMaterial({ color });
    const sphere = new THREE.Mesh(sphereGeo, material);
    sphere.position.set(node.x, node.y, node.z);
    graphScene.add(sphere);
    graphNodes.push(sphere);
  });

  const lineMaterial = new THREE.LineBasicMaterial({ color: 0x94a3b8, transparent: true, opacity: 0.6 });
  const points = [];
  links.forEach((link) => {
    const source = nodes.find((n) => n.id === link.source);
    const target = nodes.find((n) => n.id === link.target);
    if (!source || !target) return;
    points.push(new THREE.Vector3(source.x, source.y, source.z));
    points.push(new THREE.Vector3(target.x, target.y, target.z));
  });

  const geometry = new THREE.BufferGeometry().setFromPoints(points);
  graphLines = new THREE.LineSegments(geometry, lineMaterial);
  graphScene.add(graphLines);
};

const animateGraph = () => {
  if (!graphRenderer || !graphScene || !graphCamera) return;
  graphScene.rotation.y += 0.002;
  graphScene.rotation.x += 0.001;
  graphRenderer.render(graphScene, graphCamera);
  requestAnimationFrame(animateGraph);
};

const resizeGraph = () => {
  if (!graphRenderer || !graphCamera || !graphContainer) return;
  const width = graphContainer.clientWidth;
  const height = graphContainer.clientHeight;
  graphRenderer.setSize(width, height);
  graphCamera.aspect = width / height;
  graphCamera.updateProjectionMatrix();
};

window.addEventListener("resize", resizeGraph);

if (graphContainer) initGraph();

window.UEBA_NETWORK_GRAPH = { update: buildGraph };
