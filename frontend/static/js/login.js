const showMessage = (type, text) => {
  const el = document.getElementById("auth-message");
  if (!el) return;
  el.className = `alert ${type}`;
  el.textContent = text;
  el.style.display = "block";
};

const setLoading = (isLoading) => {
  const button = document.getElementById("login-btn");
  const spinner = document.getElementById("login-spinner");
  if (!button || !spinner) return;
  button.disabled = isLoading;
  spinner.style.display = isLoading ? "inline-block" : "none";
};

document.addEventListener("DOMContentLoaded", () => {
  if (localStorage.getItem("signupSuccess")) {
    localStorage.removeItem("signupSuccess");
    showMessage("success", "Signup successful. Please login.");
  }

  const form = document.getElementById("login-form");
  if (!form) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    setLoading(true);

    const identifier = document.getElementById("login-email").value.trim();
    const password = document.getElementById("login-password").value;

    try {
      const response = await fetch("/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: identifier, password }),
      });

      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        showMessage("error", data.detail || "Login failed.");
        setLoading(false);
        return;
      }

      if (data.mfa_required) {
        localStorage.setItem("otpIdentifier", identifier);
        localStorage.setItem("otpPurpose", "login");
        showMessage("success", "OTP sent. Verify to continue.");
        setTimeout(() => {
          window.location.href = "/verify-otp";
        }, 600);
        return;
      }

      if (window.UEBA_AUTH) {
        window.UEBA_AUTH.setAccessToken(data.access_token);
        window.UEBA_AUTH.setRefreshToken(data.refresh_token);
      } else {
        localStorage.setItem("access_token", data.access_token);
        localStorage.setItem("refresh_token", data.refresh_token);
      }
      showMessage("success", "Login successful. Redirecting to dashboard...");
      setTimeout(() => {
        window.location.href = "/dashboard";
      }, 800);
    } catch (err) {
      showMessage("error", "Network error. Please try again.");
      setLoading(false);
    }
  });
});
