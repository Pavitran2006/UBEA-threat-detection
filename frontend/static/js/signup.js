const showMessage = (type, text) => {
  const el = document.getElementById("auth-message");
  if (!el) return;
  el.className = `alert ${type}`;
  el.textContent = text;
  el.style.display = "block";
};

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("signup-form");
  if (!form) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const fullName = document.getElementById("signup-name").value.trim();
    const email = document.getElementById("signup-email").value.trim();
    const phone = document.getElementById("signup-phone").value.trim();
    const password = document.getElementById("signup-password").value;
    const confirmPassword = document.getElementById("signup-confirm").value;

    if (password !== confirmPassword) {
      showMessage("error", "Passwords do not match.");
      return;
    }

    try {
      const response = await fetch("/signup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          full_name: fullName,
          email,
          phone,
          password,
          confirm_password: confirmPassword,
        }),
      });

      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        showMessage("error", data.detail || "Signup failed.");
        return;
      }

      localStorage.setItem("otpIdentifier", email || phone);
      localStorage.setItem("otpPurpose", "signup");
      window.location.href = "/verify-otp";
    } catch (err) {
      showMessage("error", "Network error. Please try again.");
    }
  });
});
