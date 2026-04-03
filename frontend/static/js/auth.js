const setAccessToken = (token) => localStorage.setItem("access_token", token);
const setRefreshToken = (token) => localStorage.setItem("refresh_token", token);
const getAccessToken = () => localStorage.getItem("access_token");
const getRefreshToken = () => localStorage.getItem("refresh_token");
const clearTokens = () => {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
};

const refreshAccessToken = async () => {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;
  const response = await fetch("/refresh", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!response.ok) return false;
  const data = await response.json();
  if (!data.access_token) return false;
  setAccessToken(data.access_token);
  return true;
};

const requireAuth = async () => {
  const accessToken = getAccessToken();
  if (accessToken) return true;
  const refreshed = await refreshAccessToken();
  if (refreshed) return true;
  clearTokens();
  window.location.href = "/login";
  return false;
};

const authFetch = async (path, options = {}) => {
  if (!(await requireAuth())) return null;
  let accessToken = getAccessToken();

  const buildHeaders = (token) => ({
    ...(options.headers || {}),
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  });

  let response = await fetch(path, { ...options, headers: buildHeaders(accessToken) });
  if (response.status === 401) {
    const refreshed = await refreshAccessToken();
    if (!refreshed) {
      clearTokens();
      window.location.href = "/login";
      return null;
    }
    accessToken = getAccessToken();
    response = await fetch(path, { ...options, headers: buildHeaders(accessToken) });
  }
  return response;
};

const authFetchJson = async (path, options = {}) => {
  const response = await authFetch(path, options);
  if (!response) return null;
  if (!response.ok) throw new Error(`Failed ${path}`);
  return response.json();
};

window.UEBA_AUTH = {
  setAccessToken,
  setRefreshToken,
  getAccessToken,
  getRefreshToken,
  clearTokens,
  requireAuth,
  authFetch,
  authFetchJson,
};

const path = (window.location.pathname || "").toLowerCase();
if (path.endsWith("/dashboard") || path.endsWith("/dashboard/")) {
  requireAuth();
}
