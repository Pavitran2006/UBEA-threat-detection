const showMessage = (type, text) => {
  const el = document.getElementById("auth-message");
  if (!el) return;
  el.className = `alert ${type}`;
  el.textContent = text;
  el.style.display = "block";
};

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("reset-form");
  if (!form) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const password = document.getElementById("reset-password").value;
    const confirmPassword = document.getElementById("reset-confirm").value;
    const resetToken = localStorage.getItem("resetToken");

    if (!resetToken) {
      showMessage("error", "Reset token missing. Please request a new OTP.");
      return;
    }
    if (password !== confirmPassword) {
      showMessage("error", "Passwords do not match.");
      return;
    }

    try {
      const response = await fetch("/reset-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reset_token: resetToken, password, confirm_password: confirmPassword }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        showMessage("error", data.detail || "Password reset failed.");
        return;
      }

      localStorage.removeItem("resetToken");
      localStorage.removeItem("otpIdentifier");
      localStorage.removeItem("otpPurpose");
      showMessage("success", "Password updated. Please login.");
      setTimeout(() => {
        window.location.href = "/login";
      }, 800);
    } catch (err) {
      showMessage("error", "Network error. Please try again.");
    }
  });
});
