class SessionMonitor {
  constructor() {
    this.intervalMs = 10000;
    this.resetBuffer();
    this.initListeners();
    this.start();
  }

  resetBuffer() {
    this.buffer = {
      mouse_movement_frequency: 0,
      click_rate: 0,
      api_request_frequency: 0,
      failed_api_attempts: 0,
      page_navigation_timing_ms: performance.now(),
      page_path: window.location.pathname,
      captured_at: new Date().toISOString()
    };
  }

  initListeners() {
    document.addEventListener("mousemove", () => {
      this.buffer.mouse_movement_frequency += 1;
    });

    document.addEventListener("click", () => {
      this.buffer.click_rate += 1;
    });

    window.addEventListener("popstate", () => {
      this.buffer.page_navigation_timing_ms = performance.now();
      this.buffer.page_path = window.location.pathname;
    });

    const originalFetch = window.fetch.bind(window);
    window.fetch = async (...args) => {
      this.buffer.api_request_frequency += 1;
      try {
        const response = await originalFetch(...args);
        if (!response.ok) {
          this.buffer.failed_api_attempts += 1;
        }
        return response;
      } catch (error) {
        this.buffer.failed_api_attempts += 1;
        throw error;
      }
    };
  }

  async flush() {
    const payload = { ...this.buffer, captured_at: new Date().toISOString() };
    this.resetBuffer();
    try {
      await fetch("/api/session-event", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(payload)
      });
    } catch (error) {
      // Keep silent in production telemetry path.
    }
  }

  start() {
    this.timer = setInterval(() => this.flush(), this.intervalMs);
    window.addEventListener("beforeunload", () => this.flush(), { once: true });
  }
}

window.addEventListener("load", () => {
  if (!window.__SESSION_MONITOR__) {
    window.__SESSION_MONITOR__ = new SessionMonitor();
  }
});

