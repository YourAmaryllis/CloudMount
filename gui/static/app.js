/* CloudMount UI */
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];

let state = null;

function toast(msg, ms = 3500) {
  const t = $("#toast");
  t.hidden = false;
  t.textContent = msg;
  clearTimeout(toast._tm);
  toast._tm = setTimeout(() => { t.hidden = true; }, ms);
}

async function api(path, opts = {}) {
  const r = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
    ...opts,
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok && data.error) throw new Error(data.error);
  if (data.ok === false && data.error) throw new Error(data.error);
  return data;
}

function showTab(name) {
  $$(".tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  $$(".tab").forEach((s) => s.classList.toggle("active", s.id === `tab-${name}`));
}

async function refresh() {
  state = await api("/api/status");
  const s = state.summary || {};
  $("#summary").textContent = `☁ ${s.mounts_up || 0}/${s.mounts_total || 0} · ${s.hosts || 0} hosts`;
  renderMounts();
  renderHosts();
  renderSetup();
}

function renderMounts() {
  const list = state.mounts || [];
  const empty = $("#mounts-empty");
  const table = $("#mounts-table");
  const tb = table.querySelector("tbody");
  tb.innerHTML = "";
  if (!list.length) {
    empty.classList.remove("hidden");
    table.classList.add("hidden");
    return;
  }
  empty.classList.add("hidden");
  table.classList.remove("hidden");
  for (const m of list) {
    const tr = document.createElement("tr");
    const stClass = m.mounted ? "state-on" : "state-off";
    const stText = m.mounted ? "mounted" : "—";
    tr.innerHTML = `
      <td>${esc(m.label)}</td>
      <td>${esc(m.host_name || m.host_id)}</td>
      <td><code>${esc(m.remote_path)}</code></td>
      <td><code>${esc(m.path)}</code></td>
      <td>${esc(m.mount_kind || "nfs")}</td>
      <td class="${stClass}">${stText}</td>
      <td class="actions"></td>`;
    const actions = tr.querySelector(".actions");
    if (m.mounted) {
      actions.append(btn("Unmount", () => doUnmount(m.id)));
      actions.append(btn("Open", () => openPath(m.path), "secondary"));
    } else {
      actions.append(btn("Mount", () => doMount(m.id), "primary"));
    }
    actions.append(btn("Edit", () => openMountDialog(m), "secondary"));
    actions.append(btn("Remove", () => doRemoveMount(m.id), "secondary"));
    tb.append(tr);
  }
}

function renderHosts() {
  const list = state.hosts || [];
  const empty = $("#hosts-empty");
  const table = $("#hosts-table");
  const tb = table.querySelector("tbody");
  tb.innerHTML = "";
  if (!list.length) {
    empty.classList.remove("hidden");
    table.classList.add("hidden");
    return;
  }
  empty.classList.add("hidden");
  table.classList.remove("hidden");
  for (const h of list) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><code>${esc(h.name)}</code></td>
      <td>${esc(h.type)} / ${esc(h.provider || "")}</td>
      <td>${esc(h.endpoint || "")}</td>
      <td>${h.has_secrets ? "Keychain ✓" : "missing"}</td>
      <td class="actions"></td>`;
    const actions = tr.querySelector(".actions");
    actions.append(btn("Test", () => doTestHost(h.id)));
    actions.append(btn("Edit", () => openHostDialog(h), "secondary"));
    actions.append(btn("Remove", () => doRemoveHost(h.id), "secondary"));
    tb.append(tr);
  }
}

function renderSetup() {
  const c = state.capabilities || {};
  $("#caps-json").textContent = JSON.stringify(c, null, 2);
  $("#paths-json").textContent = JSON.stringify(state.paths || {}, null, 2);
  const prefs = state.prefs || {};
  $("#pref-fuse").checked = !!prefs.enable_fuse;
  $("#pref-nfs").checked = !!prefs.enable_nfs;
  $("#pref-default-kind").value = prefs.default_mount_kind || "nfs";
}

function btn(label, onClick, cls = "") {
  const b = document.createElement("button");
  b.type = "button";
  b.textContent = label;
  if (cls) b.className = cls;
  b.addEventListener("click", onClick);
  return b;
}

function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

async function doMount(id) {
  toast("Mounting…");
  try {
    const r = await api("/api/mount/up", { method: "POST", body: JSON.stringify({ id }) });
    if (!r.ok) throw new Error(r.error || "mount failed");
    toast(`Mounted (${r.kind || ""})`);
    await refresh();
  } catch (e) {
    toast(String(e.message || e));
    alert(String(e.message || e));
  }
}

async function doUnmount(id) {
  try {
    const r = await api("/api/mount/down", { method: "POST", body: JSON.stringify({ id }) });
    if (!r.ok) throw new Error(r.error || "unmount failed");
    toast("Unmounted");
    await refresh();
  } catch (e) {
    toast(String(e.message || e));
  }
}

async function doRemoveMount(id) {
  if (!confirm("Remove this mount definition? (Will unmount if needed)")) return;
  await api("/api/mount/delete", { method: "POST", body: JSON.stringify({ id }) });
  toast("Removed");
  await refresh();
}

async function doRemoveHost(id) {
  if (!confirm("Remove this host and Keychain secrets?")) return;
  try {
    await api("/api/host/delete", { method: "POST", body: JSON.stringify({ id }) });
    toast("Host removed");
    await refresh();
  } catch (e) {
    alert(String(e.message || e));
  }
}

async function doTestHost(id) {
  toast("Testing…");
  try {
    const r = await api("/api/host/test", { method: "POST", body: JSON.stringify({ id }) });
    if (!r.ok) throw new Error(r.error || "failed");
    toast(`OK — ${(r.buckets || []).length} top-level entries`);
    alert(`Connection OK\n\nBuckets / folders:\n${(r.buckets || []).join("\n") || "(none)"}`);
  } catch (e) {
    alert(String(e.message || e));
  }
}

function openPath(p) {
  // best-effort: UI can't open Finder directly; show path
  toast(`Path: ${p} (open in Finder from menu bar or open ${p})`);
}

function openMountDialog(m = null) {
  const dlg = $("#dlg-mount");
  const form = $("#form-mount");
  form.reset();
  $("#dlg-mount-title").textContent = m ? "Edit mount" : "Add mount";
  form.id.value = m?.id || "";
  form.label.value = m?.label || "";
  form.remote_path.value = m?.remote_path || "";
  form.path.value = m?.path || "~/";
  form.mount_kind.value = m?.mount_kind || state?.prefs?.default_mount_kind || "nfs";
  form.vfs_cache_mode.value = m?.vfs_cache_mode || "full";
  const sel = form.host_id;
  sel.innerHTML = "";
  for (const h of state.hosts || []) {
    const o = document.createElement("option");
    o.value = h.id;
    o.textContent = `${h.name} (${h.provider || h.type})`;
    if (m && m.host_id === h.id) o.selected = true;
    sel.append(o);
  }
  if (!(state.hosts || []).length) {
    alert("Add a host first (Hosts tab).");
    return;
  }
  $("#mount-form-error").textContent = "";
  dlg.showModal();
}

function openHostDialog(h = null) {
  const dlg = $("#dlg-host");
  const form = $("#form-host");
  form.reset();
  $("#dlg-host-title").textContent = h ? "Edit host" : "Add host";
  form.id.value = h?.id || "";
  form.name.value = h?.name || "wasabi";
  form.type.value = h?.type || "s3";
  form.provider.value = h?.provider || "Wasabi";
  form.endpoint.value = h?.endpoint || "https://s3.us-east-1.wasabisys.com";
  form.region.value = h?.region || "us-east-1";
  form.access_key.value = "";
  form.secret_key.value = "";
  $("#host-form-error").textContent = "";
  dlg.showModal();
}

function wire() {
  $$(".tabs button").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.tab)));
  $("#btn-refresh").onclick = () => refresh().then(() => toast("Refreshed"));
  $("#btn-setup").onclick = async () => {
    toast("Setup…");
    const r = await api("/api/setup");
    toast(r.ok ? "Setup OK" : r.error);
    await refresh();
  };
  $("#btn-add-mount").onclick = () => openMountDialog();
  const browseBtn = $("#btn-browse-add");
  if (browseBtn) {
    browseBtn.addEventListener("click", (ev) => {
      ev.preventDefault();
      openBrowseDialog();
    });
  }
  $("#btn-add-host").onclick = () => openHostDialog();
  $("#browse-cancel").onclick = () => $("#dlg-browse").close();
  $("#browse-up").onclick = () => browseLoad(browseState.parent);
  $("#browse-host").onchange = () => browseLoad("");
  $("#browse-add").onclick = () => browseAddSelected();
  $("#btn-mount-all").onclick = async () => {
    await api("/api/mount/all-up", { method: "POST", body: "{}" });
    await refresh();
    toast("Mount all done");
  };
  $("#btn-unmount-all").onclick = async () => {
    await api("/api/mount/all-down", { method: "POST", body: "{}" });
    await refresh();
    toast("Unmount all done");
  };
  $("#btn-caps").onclick = async () => {
    const c = await api("/api/capabilities");
    $("#caps-json").textContent = JSON.stringify(c, null, 2);
  };
  $("#btn-macfuse-help").onclick = async () => {
    const r = await api("/api/macfuse/help", { method: "POST", body: "{}" });
    alert((r.steps || []).join("\n"));
  };
  $("#btn-macfuse-brew").onclick = async () => {
    if (!confirm("Run: brew install --cask macfuse ?")) return;
    toast("Installing… (may need terminal approval)");
    const r = await api("/api/macfuse/brew", { method: "POST", body: "{}" });
    alert(r.ok ? "brew finished — re-detect capabilities" : (r.error || r.stderr || "failed"));
    await refresh();
  };
  $("#btn-save-prefs").onclick = async () => {
    await api("/api/prefs", {
      method: "POST",
      body: JSON.stringify({
        enable_fuse: $("#pref-fuse").checked,
        enable_nfs: $("#pref-nfs").checked,
        default_mount_kind: $("#pref-default-kind").value,
      }),
    });
    toast("Prefs saved");
    await refresh();
  };

  $("#form-mount").addEventListener("submit", async (ev) => {
    const form = ev.target;
    if (ev.submitter?.value === "cancel") return;
    ev.preventDefault();
    const fd = new FormData(form);
    const body = Object.fromEntries(fd.entries());
    try {
      await api("/api/mount", { method: "POST", body: JSON.stringify(body) });
      $("#dlg-mount").close();
      toast("Mount saved");
      await refresh();
    } catch (e) {
      $("#mount-form-error").textContent = String(e.message || e);
    }
  });

  $("#form-host").addEventListener("submit", async (ev) => {
    const form = ev.target;
    if (ev.submitter?.value === "cancel") return;
    ev.preventDefault();
    const fd = new FormData(form);
    const body = Object.fromEntries(fd.entries());
    if (!body.access_key) delete body.access_key;
    if (!body.secret_key) delete body.secret_key;
    try {
      await api("/api/host", { method: "POST", body: JSON.stringify(body) });
      $("#dlg-host").close();
      toast("Host saved (Keychain)");
      await refresh();
    } catch (e) {
      $("#host-form-error").textContent = String(e.message || e);
    }
  });

  $("#btn-lsd").onclick = async () => {
    const form = $("#form-mount");
    const hostId = form.host_id.value;
    const prefix = (form.remote_path.value || "").trim();
    try {
      const r = await api("/api/host/lsd", {
        method: "POST",
        body: JSON.stringify({ id: hostId, prefix }),
      });
      if (!r.ok) throw new Error(r.error || "lsd failed");
      const entries = r.entries || [];
      const names = entries.map((e) => (typeof e === "string" ? e : e.name));
      const fulls = entries.map((e) =>
        typeof e === "string"
          ? prefix
            ? `${prefix}/${e}`
            : e
          : e.remote_path
      );
      const pick = prompt(
        `Folders under “${prefix || "(root)"}” — enter one name or full path:\n\n` +
          names.join("\n"),
        fulls[0] || ""
      );
      if (pick) {
        // if user typed basename only, join with current prefix
        if (prefix && !pick.includes("/") && names.includes(pick)) {
          form.remote_path.value = `${prefix}/${pick}`;
        } else {
          form.remote_path.value = pick;
        }
        // suggest local path from basename
        const base = form.remote_path.value.split("/").pop();
        if (!form.path.value || form.path.value === "~/" || form.path.value === "~") {
          form.path.value = `~/${base}`;
        }
      }
    } catch (e) {
      alert(String(e.message || e));
    }
  };
}

/* —— Browse remote & bulk-add folder mounts —— */
const browseState = { prefix: "", parent: null, hostId: "" };

function openBrowseDialog() {
  try {
    if (!state) {
      toast("Still loading… try again");
      return;
    }
    if (!(state.hosts || []).length) {
      alert("Add a host first (Hosts tab).");
      showTab("hosts");
      return;
    }
    const dlg = $("#dlg-browse");
    const sel = $("#browse-host");
    if (!dlg || !sel) {
      alert("Browse UI missing — hard-refresh the page (Cmd+Shift+R).");
      return;
    }
    sel.innerHTML = "";
    for (const h of state.hosts) {
      const o = document.createElement("option");
      o.value = h.id;
      o.textContent = h.name;
      sel.append(o);
    }
    $("#browse-kind").value = state?.prefs?.default_mount_kind || "nfs";
    $("#browse-local-root").value = "~/CloudMount";
    $("#browse-full-path").checked = false;
    $("#browse-error").textContent = "";
    browseState.hostId = sel.value;
    // Dialog must not be inside a display:none tab
    if (typeof dlg.showModal === "function") {
      dlg.showModal();
    } else {
      dlg.setAttribute("open", "");
    }
    browseLoad("");
  } catch (e) {
    console.error(e);
    alert("Could not open browse: " + (e.message || e));
  }
}

async function browseLoad(prefix) {
  browseState.hostId = $("#browse-host").value;
  browseState.prefix = prefix || "";
  $("#browse-prefix").textContent = browseState.prefix ? `/${browseState.prefix}` : "/ (buckets & roots)";
  $("#browse-error").textContent = "";
  const list = $("#browse-list");
  list.innerHTML = "<div class='browse-item'>Loading…</div>";
  try {
    const r = await api("/api/host/lsd", {
      method: "POST",
      body: JSON.stringify({ id: browseState.hostId, prefix: browseState.prefix }),
    });
    if (!r.ok) throw new Error(r.error || "list failed");
    browseState.parent = r.parent === undefined ? null : r.parent;
    $("#browse-up").disabled = !browseState.prefix;
    list.innerHTML = "";
    const entries = r.entries || [];
    if (!entries.length) {
      list.innerHTML = "<div class='browse-item'>No folders here</div>";
      return;
    }
    for (const e of entries) {
      const name = typeof e === "string" ? e : e.name;
      const remotePath =
        typeof e === "string"
          ? browseState.prefix
            ? `${browseState.prefix}/${e}`
            : e
          : e.remote_path;
      const row = document.createElement("div");
      row.className = "browse-item";
      row.innerHTML = `
        <input type="checkbox" data-remote="${esc(remotePath)}" />
        <span class="name" title="Open folder">📁 ${esc(name)}</span>
        <code style="color:var(--muted);font-size:0.75rem">${esc(remotePath)}</code>`;
      const nameEl = row.querySelector(".name");
      nameEl.addEventListener("dblclick", () => browseLoad(remotePath));
      nameEl.addEventListener("click", (ev) => {
        // single click also navigates for convenience
        if (ev.detail === 1) {
          clearTimeout(nameEl._t);
          nameEl._t = setTimeout(() => browseLoad(remotePath), 250);
        }
      });
      list.append(row);
    }
  } catch (e) {
    list.innerHTML = "";
    $("#browse-error").textContent = String(e.message || e);
  }
}

async function browseAddSelected() {
  const boxes = $$("#browse-list input[type=checkbox]:checked");
  const paths = boxes.map((b) => b.dataset.remote).filter(Boolean);
  if (!paths.length) {
    alert("Select one or more folders (checkboxes).");
    return;
  }
  try {
    const r = await api("/api/mount/bulk", {
      method: "POST",
      body: JSON.stringify({
        host_id: $("#browse-host").value,
        remote_paths: paths,
        local_root: $("#browse-local-root").value || "~",
        mount_kind: $("#browse-kind").value || "nfs",
        label_from: $("#browse-full-path").checked ? "full" : "basename",
      }),
    });
    const n = (r.created || []).length;
    const s = (r.skipped || []).length;
    toast(`Added ${n} mount(s)${s ? `, skipped ${s}` : ""}`);
    $("#dlg-browse").close();
    await refresh();
    showTab("mounts");
  } catch (e) {
    $("#browse-error").textContent = String(e.message || e);
  }
}

wire();
refresh().catch((e) => {
  toast("Failed to load status");
  console.error(e);
});
