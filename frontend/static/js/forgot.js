const showMessage = (type, text) => {
  const el = document.getElementById("auth-message");
  if (!el) return;
  el.className = `alert ${type}`;
  el.textContent = text;
  el.style.display = "block";
};

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("forgot-form");
  if (!form) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const identifier = document.getElementById("forgot-identifier").value.trim();

    try {
      const response = await fetch("/forgot-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: identifier }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        showMessage("error", data.detail || "Failed to send OTP.");
        return;
      }
      localStorage.setItem("otpIdentifier", identifier);
      localStorage.setItem("otpPurpose", "reset");
      window.location.href = "/verify-otp";
    } catch (err) {
      showMessage("error", "Network error. Please try again.");
    }
  });
});
