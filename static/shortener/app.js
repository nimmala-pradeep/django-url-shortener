(() => {
  "use strict";

  const STORE_KEY = "snip.links";
  const $ = (sel) => document.querySelector(sel);

  const form = $("#shorten-form");
  const urlInput = $("#url");
  const aliasInput = $("#alias");
  const expiresInput = $("#expires");
  const submitBtn = $("#submit");
  const errorBox = $("#form-error");
  const resultBox = $("#result");
  const resultLink = $("#result-link");
  const copyBtn = $("#copy");
  const list = $("#history-list");
  const emptyMsg = $("#empty");
  const clearBtn = $("#clear");
  const csrfToken = document.querySelector('meta[name="csrf-token"]').content;

  $("#host-prefix").textContent = `${location.host}/`;

  // ---- storage (guarded: storage can be unavailable) ----
  function loadSaved() {
    try {
      const parsed = JSON.parse(localStorage.getItem(STORE_KEY) || "[]");
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }

  function saveList(items) {
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify(items.slice(0, 25)));
    } catch {
      /* ignore quota / privacy-mode errors */
    }
  }

  // ---- form ----
  function showError(message) {
    errorBox.textContent = message;
    errorBox.hidden = !message;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    showError("");

    const payload = {
      url: urlInput.value.trim(),
      alias: aliasInput.value.trim(),
      expires_in_days: expiresInput.value || null,
    };

    if (!payload.url) {
      showError("Enter a URL to shorten.");
      urlInput.focus();
      return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = "Shortening…";

    try {
      const res = await fetch("/api/shorten", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        showError(data.error || "Something went wrong. Try again.");
        return;
      }

      showResult(data);
      const items = loadSaved().filter((l) => l.code !== data.code);
      items.unshift({ code: data.code });
      saveList(items);
      renderHistory();
      form.reset();
    } catch {
      showError("Could not reach the server. Check your connection.");
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "Shorten link";
    }
  });

  function showResult(data) {
    resultLink.textContent = data.short_url.replace(/^https?:\/\//, "");
    resultLink.href = data.short_url;
    resultLink.dataset.full = data.short_url;
    copyBtn.textContent = "Copy";
    resultBox.hidden = false;
  }

  copyBtn.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(resultLink.dataset.full);
      copyBtn.textContent = "Copied";
    } catch {
      copyBtn.textContent = "Press Ctrl+C";
      const range = document.createRange();
      range.selectNodeContents(resultLink);
      const sel = getSelection();
      sel.removeAllRanges();
      sel.addRange(range);
    }
    setTimeout(() => (copyBtn.textContent = "Copy"), 1800);
  });

  // ---- history with live stats ----
  function fmtDate(iso) {
    return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
  }

  function buildSparkline(days) {
    const max = Math.max(1, ...days.map((d) => d.clicks));
    const wrap = document.createElement("div");
    wrap.className = "spark";
    wrap.setAttribute("role", "img");
    wrap.setAttribute("aria-label", `Clicks over the last 7 days: ${days.map((d) => d.clicks).join(", ")}`);
    days.forEach((d) => {
      const bar = document.createElement("span");
      bar.style.height = `${Math.max(8, (d.clicks / max) * 100)}%`;
      if (d.clicks === 0) bar.className = "zero";
      bar.title = `${fmtDate(d.date)}: ${d.clicks} click${d.clicks === 1 ? "" : "s"}`;
      wrap.appendChild(bar);
    });
    return wrap;
  }

  function buildItem(stats) {
    const li = document.createElement("li");
    li.className = "item";

    const top = document.createElement("div");
    top.className = "item-top";
    const a = document.createElement("a");
    a.className = "item-short";
    a.href = stats.short_url;
    a.target = "_blank";
    a.rel = "noopener";
    a.textContent = stats.short_url.replace(/^https?:\/\//, "");
    const clicks = document.createElement("span");
    clicks.className = "item-clicks";
    clicks.textContent = stats.click_count;
    const small = document.createElement("small");
    small.textContent = stats.click_count === 1 ? "click" : "clicks";
    clicks.appendChild(small);
    top.append(a, clicks);

    const original = document.createElement("p");
    original.className = "item-original";
    original.textContent = stats.original_url;
    original.title = stats.original_url;

    const meta = document.createElement("p");
    meta.className = "item-meta";
    const parts = [`Created ${fmtDate(stats.created_at)}`];
    parts.push(stats.last_accessed ? `last opened ${fmtDate(stats.last_accessed)}` : "not opened yet");
    meta.textContent = parts.join(", ");
    if (stats.expired) {
      const tag = document.createElement("span");
      tag.className = "expired";
      tag.textContent = ` Expired ${fmtDate(stats.expires_at)}.`;
      meta.appendChild(tag);
    } else if (stats.expires_at) {
      meta.textContent += `, expires ${fmtDate(stats.expires_at)}`;
    }

    li.append(top, original, meta, buildSparkline(stats.last_7_days));
    return li;
  }

  async function renderHistory() {
    const saved = loadSaved();
    emptyMsg.hidden = saved.length > 0;
    clearBtn.hidden = saved.length === 0;
    list.replaceChildren();

    const results = await Promise.all(
      saved.map((item) =>
        fetch(`/api/stats/${encodeURIComponent(item.code)}`)
          .then((r) => (r.ok ? r.json() : null))
          .catch(() => null)
      )
    );

    // Drop links that no longer exist on the server.
    const alive = saved.filter((_, i) => results[i]);
    if (alive.length !== saved.length) saveList(alive);

    results.filter(Boolean).forEach((stats) => list.appendChild(buildItem(stats)));
    emptyMsg.hidden = alive.length > 0;
    clearBtn.hidden = alive.length === 0;
  }

  clearBtn.addEventListener("click", () => {
    saveList([]);
    renderHistory();
  });

  renderHistory();
})();
