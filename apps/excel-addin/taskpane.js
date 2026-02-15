/* global Office */

(function () {
  "use strict";

  const statusEl = document.getElementById("status");
  const apiUrlEl = document.getElementById("apiUrl");
  const tenantIdEl = document.getElementById("tenantId");
  const tokenEl = document.getElementById("accessToken");
  const connectionIdEl = document.getElementById("connectionId");
  const btnPull = document.getElementById("btnPull");
  const btnPush = document.getElementById("btnPush");

  function setStatus(msg) {
    statusEl.textContent = msg;
  }

  function getHeaders() {
    const tenantId = (tenantIdEl && tenantIdEl.value) || "";
    const headers = { "X-Tenant-ID": tenantId, "Content-Type": "application/json" };
    const token = (tokenEl && tokenEl.value) || "";
    if (token) headers["Authorization"] = "Bearer " + token.trim();
    return headers;
  }

  Office.onReady(function (info) {
    if (info.host === Office.HostType.Excel) {
      btnPull.addEventListener("click", onPull);
      btnPush.addEventListener("click", onPush);
      setStatus("Ready. Enter API URL, Tenant ID, and Connection ID, then Pull or Push.");
    } else {
      setStatus("This add-in runs in Excel only.");
    }
  });

  async function onPull() {
    const base = (apiUrlEl && apiUrlEl.value) || "";
    const connId = (connectionIdEl && connectionIdEl.value) || "";
    if (!base || !connId) {
      setStatus("Please set API base URL and Connection ID.");
      return;
    }
    setStatus("Pulling...");
    try {
      const res = await fetch(`${base}/excel/connections/${connId}/pull`, {
        method: "POST",
        headers: getHeaders(),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setStatus("Pull failed: " + (data.detail || res.status));
        return;
      }
      setStatus("Pull OK. Values: " + JSON.stringify((data.values || []).slice(0, 5)) + (data.values && data.values.length > 5 ? "..." : ""));
    } catch (err) {
      setStatus("Pull error: " + err.message);
    }
  }

  async function onPush() {
    const base = (apiUrlEl && apiUrlEl.value) || "";
    const connId = (connectionIdEl && connectionIdEl.value) || "";
    if (!base || !connId) {
      setStatus("Please set API base URL and Connection ID.");
      return;
    }
    setStatus("Push: send empty changes (log only). Add binding changes in a future build.");
    try {
      const res = await fetch(`${base}/excel/connections/${connId}/push`, {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({ changes: [] }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setStatus("Push failed: " + (data.detail || res.status));
        return;
      }
      setStatus("Push OK: " + JSON.stringify(data));
    } catch (err) {
      setStatus("Push error: " + err.message);
    }
  }
})();
