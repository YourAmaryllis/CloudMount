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
      <td><code>${esc(m.remote_path || "(root)")}</code></td>
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
    alert(
      `Connection OK\n\nTop-level folders:\n${(r.buckets || []).join("\n") || "(none / empty root)"}`
    );
  } catch (e) {
    alert(String(e.message || e));
  }
}

function openPath(p) {
  // best-effort: UI can't open Finder directly; show path
  toast(`Path: ${p} (open in Finder from menu bar or open ${p})`);
}

function updateRemotePathHint() {
  const form = $("#form-mount");
  if (!form) return;
  const cap = $("#remote-path-caption");
  const inp = $("#mount-remote-path");
  // Generic for every backend: rclone path after "remote:" — bucket only for S3-like,
  // folder path or empty root for everything else. Same field either way.
  if (cap) {
    cap.textContent =
      "Path on remote (optional). Empty = entire remote root. For S3-compatible hosts use bucket or bucket/folder; for Drive/Proton/SFTP/etc. use a folder path or leave blank.";
  }
  if (inp) {
    inp.placeholder = "empty = root · or path/on/remote";
  }
}

function openMountDialog(m = null) {
  const dlg = $("#dlg-mount");
  const form = $("#form-mount");
  form.reset();
  $("#dlg-mount-title").textContent = m ? "Edit mount" : "Add mount";
  form.id.value = m?.id || "";
  form.label.value = m?.label || "";
  form.remote_path.value = m?.remote_path || "";
  form.path.value = m?.path || "~/CloudMount/mount";
  form.mount_kind.value = m?.mount_kind || state?.prefs?.default_mount_kind || "nfs";
  form.vfs_cache_mode.value = m?.vfs_cache_mode || "full";
  const sel = form.host_id;
  sel.innerHTML = "";
  for (const h of state.hosts || []) {
    const o = document.createElement("option");
    o.value = h.id;
    o.textContent = `${h.name} (${h.type}${h.provider ? " / " + h.provider : ""})`;
    if (m && m.host_id === h.id) o.selected = true;
    sel.append(o);
  }
  if (!(state.hosts || []).length) {
    alert("Add a host first (Hosts tab).");
    return;
  }
  $("#mount-form-error").textContent = "";
  sel.onchange = updateRemotePathHint;
  updateRemotePathHint();
  if (typeof dlg.showModal === "function") dlg.showModal();
  else dlg.setAttribute("open", "");
}

let backendsCache = null;
let hostEditSnapshot = null; // options when editing

async function loadBackends() {
  if (backendsCache) return backendsCache;
  const r = await api("/api/backends");
  backendsCache = r.backends || [];
  return backendsCache;
}

async function openHostDialog(h = null) {
  const dlg = $("#dlg-host");
  const form = $("#form-host");
  form.reset();
  $("#dlg-host-title").textContent = h ? "Edit host" : "Add host";
  form.id.value = h?.id || "";
  form.name.value = h?.name || "";
  $("#host-form-error").textContent = "";
  hostEditSnapshot = h ? { ...(h.options || {}), provider: h.provider, endpoint: h.endpoint, region: h.region } : {};

  const typeSel = $("#host-type");
  typeSel.innerHTML = "<option value=\"\">Loading…</option>";
  try {
    const list = await loadBackends();
    typeSel.innerHTML = "";
    for (const b of list) {
      const o = document.createElement("option");
      o.value = b.type;
      o.textContent = `${b.type} — ${b.description || ""}`.slice(0, 80);
      typeSel.append(o);
    }
    // Prefer s3 / Wasabi as default for new hosts
    const want = h?.type || "s3";
    if ([...typeSel.options].some((o) => o.value === want)) {
      typeSel.value = want;
    } else if (typeSel.options.length) {
      typeSel.selectedIndex = 0;
    }
  } catch (e) {
    typeSel.innerHTML = "<option value=\"s3\">s3</option>";
    toast("Could not load full backend list");
  }

  await renderHostFields(typeSel.value, hostEditSnapshot);
  if (typeof dlg.showModal === "function") dlg.showModal();
  else dlg.setAttribute("open", "");
}

/** Build dynamic option inputs from rclone backend schema */
async function renderHostFields(typeName, existing = {}) {
  const box = $("#host-dynamic-fields");
  box.innerHTML = "<p class=\"hint\">Loading fields…</p>";
  if (!typeName) {
    box.innerHTML = "";
    return;
  }
  try {
    const schema = await api(`/api/backends/${encodeURIComponent(typeName)}`);
    const all = schema.fields || [];
    const byName = Object.fromEntries(all.map((f) => [f.name, f]));
    // [] is truthy in JS — only use setup_fields when non-empty
    let setup =
      Array.isArray(schema.setup_fields) && schema.setup_fields.length
        ? schema.setup_fields.slice()
        : all.filter((f) => f.show_in_setup && !f.internal);
    const advanced = (
      Array.isArray(schema.advanced_fields) && schema.advanced_fields.length
        ? schema.advanced_fields
        : all.filter((f) => !f.internal && !f.show_in_setup)
    ).filter((f) => !f.internal && f.name !== "2fa");

    // Always show core auth fields when the backend defines them
    const mustShow = [
      "username",
      "user",
      "password",
      "pass",
      "otp_secret_key",
      "mailbox_password",
      "provider",
      "access_key_id",
      "secret_access_key",
      "endpoint",
      "region",
      "host",
      "port",
    ];
    for (const name of mustShow) {
      if (byName[name] && !byName[name].internal && !setup.find((f) => f.name === name)) {
        setup.push(byName[name]);
      }
    }
    // Hide runtime / internal (6-digit 2fa code, client tokens, …)
    setup = setup.filter((f) => f.name !== "2fa" && !f.internal);

    const priority = [
      "provider",
      "username",
      "user",
      "password",
      "pass",
      "otp_secret_key",
      "mailbox_password",
      "env_auth",
      "access_key_id",
      "secret_access_key",
      "endpoint",
      "region",
      "host",
      "port",
      "client_id",
      "client_secret",
      "service_account_file",
      "scope",
      "acl",
    ];
    const ordered = [];
    for (const p of priority) {
      const f = setup.find((x) => x.name === p);
      if (f) ordered.push(f);
    }
    for (const f of setup) {
      if (!priority.includes(f.name)) ordered.push(f);
    }

    box.innerHTML = "";
    if (typeName === "protondrive") {
      const tip = document.createElement("p");
      tip.className = "hint";
      tip.innerHTML =
        "Proton Drive: enter <strong>username</strong>, <strong>password</strong>, and the long <strong>authenticator secret</strong> from 2FA setup " +
        "(not the 6-digit codes). The changing 6-digit code is runtime-only and is not shown here.";
      box.append(tip);
    }

    const appendField = (f, container) => {
      if (!f || !f.name || f.internal || f.name === "2fa") return;
      if (["alternate_export"].includes(f.name)) return;
      const label = document.createElement("label");
      label.dataset.field = f.name;
      const title = (f.label || f.name) + (f.required ? " *" : "");
      const val =
        existing[f.name] !== undefined && existing[f.name] !== null
          ? String(existing[f.name])
          : "";
      const isSecret = !!f.is_secret || !!f.is_password;
      const examples = f.examples || [];

      if (examples.length > 0 && examples.length < 80) {
        label.append(document.createTextNode(title));
        const sel = document.createElement("select");
        sel.name = `opt_${f.name}`;
        sel.dataset.opt = f.name;
        sel.dataset.secret = isSecret ? "1" : "0";
        const blank = document.createElement("option");
        blank.value = "";
        blank.textContent = "—";
        sel.append(blank);
        for (const ex of examples) {
          const o = document.createElement("option");
          o.value = ex.value;
          o.textContent = ex.help ? `${ex.value} — ${ex.help}` : ex.value;
          if (val && val === ex.value) o.selected = true;
          if (!val && f.name === "provider" && ex.value === "Wasabi" && !hostEditSnapshot?.id) {
            o.selected = true;
          }
          sel.append(o);
        }
        label.append(sel);
      } else if (f.type === "bool" || f.type === "boolean") {
        label.className = "row";
        const cb = document.createElement("input");
        cb.type = "checkbox";
        cb.name = `opt_${f.name}`;
        cb.dataset.opt = f.name;
        cb.dataset.secret = "0";
        cb.checked = val === "true" || val === "1" || val === true;
        if (!val && f.name === "env_auth" && typeName === "s3") cb.checked = true;
        label.append(cb);
        label.append(document.createTextNode(" " + title));
      } else {
        label.append(document.createTextNode(title));
        const inp = document.createElement("input");
        inp.name = `opt_${f.name}`;
        inp.dataset.opt = f.name;
        inp.dataset.secret = isSecret ? "1" : "0";
        inp.autocomplete = "off";
        if (isSecret) {
          inp.type = "password";
          const editing = !!(hostEditSnapshot && Object.keys(hostEditSnapshot).length);
          if (f.name === "otp_secret_key") {
            inp.placeholder = editing
              ? "(unchanged if blank — Keychain)"
              : "Long secret from authenticator setup (not the 6-digit code)";
          } else if (f.name === "password" || f.name === "pass" || f.name === "mailbox_password") {
            inp.placeholder = editing ? "(unchanged if blank — Keychain)" : "";
          } else {
            inp.placeholder = editing ? "(unchanged if blank — Keychain)" : "";
          }
        } else {
          inp.type = "text";
          inp.value = val;
          if (f.name === "endpoint" && typeName === "s3" && !val) {
            inp.placeholder = "https://s3.us-east-1.wasabisys.com";
          }
          if (f.name === "region" && typeName === "s3" && !val) {
            inp.placeholder = "us-east-1";
          }
        }
        label.append(inp);
      }
      if (f.help && !String(f.help).toLowerCase().includes("internal use")) {
        const help = document.createElement("div");
        help.className = "field-help";
        help.textContent = f.help.slice(0, 200);
        label.append(help);
      }
      container.append(label);
    };

    for (const f of ordered) appendField(f, box);
    // Advanced: non-internal only, collapsed
    if (advanced.length) {
      const det = document.createElement("details");
      det.innerHTML = `<summary class="hint">Advanced options (${advanced.length})</summary>`;
      const inner = document.createElement("div");
      inner.className = "host-dynamic";
      for (const f of advanced) appendField(f, inner);
      det.append(inner);
      box.append(det);
    }
    if (!ordered.length && !advanced.length) {
      box.innerHTML =
        "<p class=\"hint\">No setup fields from rclone for this type — save with name/type only, or check rclone docs.</p>";
    }
  } catch (e) {
    box.innerHTML = `<p class="error">${esc(e.message || e)}</p>`;
  }
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
    ev.preventDefault();
    const fd = new FormData(form);
    const body = Object.fromEntries(fd.entries());
    // Allow empty remote_path (= remote root) for Drive / Proton / SFTP / etc.
    body.remote_path = (body.remote_path || "").trim();
    try {
      await api("/api/mount", { method: "POST", body: JSON.stringify(body) });
      $("#dlg-mount").close();
      toast("Mount saved");
      await refresh();
    } catch (e) {
      $("#mount-form-error").textContent = String(e.message || e);
    }
  });

  $("#host-type")?.addEventListener("change", async (ev) => {
    await renderHostFields(ev.target.value, hostEditSnapshot || {});
  });
  $("#host-cancel")?.addEventListener("click", () => {
    $("#dlg-host")?.close();
  });
  $("#mount-cancel")?.addEventListener("click", () => {
    $("#dlg-mount")?.close();
  });

  $("#form-host").addEventListener("submit", async (ev) => {
    const form = ev.target;
    ev.preventDefault();
    const type = form.type.value;
    const options = {};
    const secrets = {};
    for (const el of form.querySelectorAll("[data-opt]")) {
      const name = el.dataset.opt;
      const isSecret = el.dataset.secret === "1";
      let val;
      if (el.type === "checkbox") {
        val = el.checked ? "true" : "false";
      } else {
        val = (el.value || "").trim();
      }
      if (val === "" || val === undefined) continue;
      if (isSecret) secrets[name] = val;
      else options[name] = val;
    }
    // Convenience aliases for s3
    const body = {
      id: form.id.value || undefined,
      name: form.name.value,
      type,
      options,
      secrets,
      provider: options.provider,
      endpoint: options.endpoint,
      region: options.region,
      access_key: secrets.access_key_id || secrets.access_key,
      secret_key: secrets.secret_access_key || secrets.secret_key,
    };
    try {
      await api("/api/host", { method: "POST", body: JSON.stringify(body) });
      $("#dlg-host").close();
      toast("Host saved");
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
  $("#browse-prefix").textContent = browseState.prefix
    ? `/${browseState.prefix}`
    : "/ (remote root)";
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
