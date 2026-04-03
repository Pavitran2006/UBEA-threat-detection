const toggleNav = () => {
  const token = localStorage.getItem("access_token");
  document.querySelectorAll("[data-auth='guest']").forEach((el) => {
    el.style.display = token ? "none" : "";
  });
  document.querySelectorAll("[data-auth='user']").forEach((el) => {
    el.style.display = token ? "" : "none";
  });
};

const initLogout = () => {
  const logoutBtn = document.getElementById("logout-link");
  if (!logoutBtn) return;
  logoutBtn.addEventListener("click", async (event) => {
    event.preventDefault();
    const refreshToken = localStorage.getItem("refresh_token");
    try {
      await fetch("/logout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken || "" }),
      });
    } catch (_) {}
    if (window.UEBA_AUTH) window.UEBA_AUTH.clearTokens();
    window.location.href = "/login";
  });
};

document.addEventListener("DOMContentLoaded", () => {
  toggleNav();
  initLogout();
});
