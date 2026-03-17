/* global Office */

(function () {
  "use strict";

  const statusEl = document.getElementById("status");
  const apiUrlEl = document.getElementById("apiUrl");
  const tenantIdEl = document.getElementById("tenantId");
  const tokenEl = document.getElementById("accessToken");
  const connectionSelectEl = document.getElementById("connectionSelect");
  const btnPull = document.getElementById("btnPull");
  const btnPush = document.getElementById("btnPush");
  const btnRefreshConnections = document.getElementById("btnRefreshConnections");

  // Cache of the last fetched bindings (populated by pull)
  let lastBindings = [];

  function setStatus(msg) {
    statusEl.textContent = msg;
  }

  function getActiveConnectionId() {
    return (connectionSelectEl && connectionSelectEl.value) || "";
  }

  function getHeaders() {
    const tenantId = (tenantIdEl && tenantIdEl.value) || "";
    const headers = { "X-Tenant-ID": tenantId, "Content-Type": "application/json" };
    const token = (tokenEl && tokenEl.value) || "";
    if (token) headers["Authorization"] = "Bearer " + token.trim();
    return headers;
  }

  async function onRefreshConnections() {
    const base = (apiUrlEl && apiUrlEl.value) || "";
    const tenantId = (tenantIdEl && tenantIdEl.value) || "";
    if (!base || !tenantId) {
      console.warn("onRefreshConnections: apiUrl and tenantId are required");
      return;
    }
    try {
      const token = (tokenEl && tokenEl.value) || "";
      const headers = { "X-Tenant-ID": tenantId };
      if (token) headers["Authorization"] = "Bearer " + token.trim();
      const response = await fetch(`${base}/excel/connections`, { headers });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        console.error("Failed to load connections:", data.detail || response.status);
        return;
      }
      const select = connectionSelectEl;
      if (!select) return;
      // Clear existing options except the placeholder
      while (select.options.length > 1) select.remove(1);
      for (const item of data.items || []) {
        const option = document.createElement("option");
        option.value = item.id;
        option.textContent = item.label || item.id;
        select.appendChild(option);
      }
    } catch (err) {
      console.error("Failed to load connections:", err);
    }
  }

  Office.onReady(function (info) {
    if (info.host === Office.HostType.Excel) {
      btnPull.addEventListener("click", onPull);
      btnPush.addEventListener("click", onPush);
      if (btnRefreshConnections) {
        btnRefreshConnections.addEventListener("click", onRefreshConnections);
      }
      if (connectionSelectEl) {
        connectionSelectEl.addEventListener("change", function () {
          // Selection is read dynamically by getActiveConnectionId() — no additional state needed
        });
      }
      setStatus("Ready. Enter API URL, Tenant ID, and Connection ID, then Pull or Push.");
      // Auto-load connections if API URL and Tenant ID are already populated (e.g. persisted values)
      const base = (apiUrlEl && apiUrlEl.value) || "";
      const tenantId = (tenantIdEl && tenantIdEl.value) || "";
      if (base && tenantId) {
        onRefreshConnections();
      }
    } else {
      setStatus("This add-in runs in Excel only.");
    }
  });

  async function onPull() {
    const base = (apiUrlEl && apiUrlEl.value) || "";
    const connId = getActiveConnectionId();
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

      // Cache bindings for use by push
      lastBindings = data.values || [];

      // Write values into Excel cells
      try {
        await Excel.run(async (context) => {
          for (const binding of lastBindings) {
            if (binding.cell_ref && binding.current_value !== undefined) {
              const range = context.workbook.worksheets
                .getActiveWorksheet()
                .getRange(binding.cell_ref);
              range.values = [[binding.current_value]];
            }
          }
          await context.sync();
        });
      } catch (excelErr) {
        console.warn("Excel.run unavailable or failed — cell values not written:", excelErr);
      }

      setStatus("Pull OK. Values: " + JSON.stringify(lastBindings.slice(0, 5)) + (lastBindings.length > 5 ? "..." : ""));
    } catch (err) {
      setStatus("Pull error: " + err.message);
    }
  }

  async function onPush() {
    const base = (apiUrlEl && apiUrlEl.value) || "";
    const connId = getActiveConnectionId();
    if (!base || !connId) {
      setStatus("Please set API base URL and Connection ID.");
      return;
    }
    setStatus("Pushing...");

    // Ensure we have a binding list — fetch from pull endpoint if cache is empty
    let bindings = lastBindings;
    if (!bindings || bindings.length === 0) {
      try {
        const pullRes = await fetch(`${base}/excel/connections/${connId}/pull`, {
          method: "POST",
          headers: getHeaders(),
        });
        const pullData = await pullRes.json().catch(() => ({}));
        if (pullRes.ok) {
          bindings = pullData.values || [];
          lastBindings = bindings;
        }
      } catch (fetchErr) {
        console.warn("Could not fetch bindings before push:", fetchErr);
      }
    }

    // Read current cell values from the workbook
    const changes = [];
    try {
      await Excel.run(async (context) => {
        for (const binding of bindings) {
          if (binding.cell_ref) {
            const range = context.workbook.worksheets
              .getActiveWorksheet()
              .getRange(binding.cell_ref);
            range.load("values");
            await context.sync();
            changes.push({
              binding_id: binding.binding_id,
              new_value: range.values[0][0],
            });
          }
        }
      });
    } catch (excelErr) {
      console.warn("Excel.run unavailable or failed — sending empty changes:", excelErr);
    }

    try {
      const res = await fetch(`${base}/excel/connections/${connId}/push`, {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({ changes }),
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
