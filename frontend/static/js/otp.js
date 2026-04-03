const showMessage = (type, text) => {
  const el = document.getElementById("auth-message");
  if (!el) return;
  el.className = `alert ${type}`;
  el.textContent = text;
  el.style.display = "block";
};

const resendBtn = () => document.getElementById("resend-otp");
const countdownEl = () => document.getElementById("otp-countdown");

const startCountdown = (seconds) => {
  const btn = resendBtn();
  const counter = countdownEl();
  if (!btn || !counter) return;
  btn.disabled = true;
  let remaining = seconds;
  counter.textContent = `Resend in ${remaining}s`;
  const timer = setInterval(() => {
    remaining -= 1;
    counter.textContent = remaining > 0 ? `Resend in ${remaining}s` : "You can resend OTP now";
    if (remaining <= 0) {
      clearInterval(timer);
      btn.disabled = false;
    }
  }, 1000);
};

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("otp-form");
  const btn = resendBtn();
  const identifier = localStorage.getItem("otpIdentifier");
  const purpose = localStorage.getItem("otpPurpose") || "reset";

  if (btn) {
    btn.addEventListener("click", async () => {
      try {
        const response = await fetch("/send-otp", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ identifier, purpose }),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          showMessage("error", data.detail || "Failed to resend OTP.");
          return;
        }
        showMessage("success", "OTP sent successfully.");
        startCountdown(30);
      } catch (err) {
        showMessage("error", "Network error. Please try again.");
      }
    });
  }

  startCountdown(30);

  if (!form) return;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const otp = document.getElementById("otp-code").value.trim();

    try {
      const response = await fetch("/verify-otp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identifier, otp, purpose }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        showMessage("error", data.detail || "OTP verification failed.");
        return;
      }

      if (purpose === "signup") {
        showMessage("success", "Account verified. You can now login.");
        setTimeout(() => {
          window.location.href = "/login";
        }, 800);
        return;
      }

      if (purpose === "login") {
        if (window.UEBA_AUTH) {
          window.UEBA_AUTH.setAccessToken(data.access_token);
          window.UEBA_AUTH.setRefreshToken(data.refresh_token);
        } else {
          localStorage.setItem("access_token", data.access_token);
          localStorage.setItem("refresh_token", data.refresh_token);
        }
        showMessage("success", "Login verified. Redirecting...");
        setTimeout(() => {
          window.location.href = "/dashboard";
        }, 700);
        return;
      }

      if (data.reset_token) {
        localStorage.setItem("resetToken", data.reset_token);
        window.location.href = "/reset-password";
      } else {
        showMessage("error", "Reset token missing.");
      }
    } catch (err) {
      showMessage("error", "Network error. Please try again.");
    }
  });
});
