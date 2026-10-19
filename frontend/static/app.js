(function () {
  "use strict";
  const state = {
    view: "overview",
    status: null,
    models: { routes: [] },
    integrations: [],
    skills: { skills: [], count: 0 },
    tasks: [],
    selectedTaskId: null,
    toastTimer: null,
    refreshTimer: null
  };
  const $ = function (selector, root) { return (root || document).querySelector(selector); };
  const $$ = function (selector, root) { return Array.prototype.slice.call((root || document).querySelectorAll(selector)); };

  function escapeHtml(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (char) {
      return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char];
    });
  }
  function readable(value) {
    return String(value || "unknown").replace(/[_-]+/g, " ").replace(/\s+/g, " ").replace(/\b\w/g, function (m) { return m.toUpperCase(); });
  }
  function dateLabel(value) {
    if (!value) return "Just now";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    const seconds = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000));
    if (seconds < 60) return "Just now";
    if (seconds < 3600) return Math.floor(seconds / 60) + "m ago";
    if (seconds < 86400) return Math.floor(seconds / 3600) + "h ago";
    return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  }
  function fullDate(value) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "Unknown" : date.toLocaleString();
  }
  async function api(path, options) {
    const response = await fetch(path, Object.assign({ headers: { "Accept": "application/json" } }, options || {}));
    const type = response.headers.get("content-type") || "";
    const body = type.indexOf("application/json") >= 0 ? await response.json() : await response.text();
    if (!response.ok) {
      const detail = body && typeof body === "object" && body.detail ? body.detail : "Request failed (" + response.status + ")";
      throw new Error(detail);
    }
    return body;
  }
  function toast(message, isError) {
    const element = $("#toast");
    element.textContent = message;
    element.classList.toggle("error", !!isError);
    element.classList.add("show");
    clearTimeout(state.toastTimer);
    state.toastTimer = setTimeout(function () { element.classList.remove("show"); }, 3600);
  }
  function statusClass(status) {
    const s = String(status || "").toLowerCase();
    if (["failed", "quarantined", "changed_since_review", "not_installed", "awaiting_correct_source"].some(function (needle) { return s.indexOf(needle) >= 0; })) return "bad";
    if (s === "completed" || s === "available" || s === "enabled_reviewed" || s === "connected" || s === "ready") return "good";
    if (s === "running" || ["needs_setup", "pending", "disabled", "configured_not_tested", "installed_needs_verification", "runtime_detected_needs_test", "installed_needs_test", "source_received", "not_installed", "adapter_pending", "awaiting", "package_not_installed", "evaluation_required", "auth_and_docs_verification_pending", "firmware_library_received_backend_adapter_pending", "source_and_skills_received_weights_not_in_archive", "metadata_only_inventory_available", "disabled_by_default"].some(function (needle) { return s.indexOf(needle) >= 0; })) return "warn";
    return "neutral";
  }
  function statusPill(status) {
    return '<span class="status-label ' + statusClass(status) + '">' + escapeHtml(readable(status)) + '</span>';
  }
  function compactIcon(kind) {
    const k = String(kind || "").toLowerCase();
    if (k.indexOf("model") >= 0) return "⌘";
    if (k.indexOf("agent") >= 0 || k.indexOf("runtime") >= 0) return "⌬";
    if (k.indexOf("skill") >= 0) return "◇";
    if (k.indexOf("iot") >= 0 || k.indexOf("device") >= 0) return "⌁";
    return "◈";
  }
  function taskTitle(task) {
    return (task.prompt || "Untitled task").replace(/\s+/g, " ").trim();
  }
  function routeById(id) {
    return state.models.routes.find(function (route) { return route.id === id; });
  }
  function selectedSkills() {
    return $$("#composer-skills input[type=checkbox]:checked").map(function (input) { return input.value; });
  }
  function setView(view) {
    state.view = view;
    $$(".view-section").forEach(function (element) { element.classList.toggle("active", element.id === "view-" + view); });
    $$(".nav-item").forEach(function (element) { element.classList.toggle("active", element.getAttribute("data-view-target") === view); });
    const labelMap = { overview: "COMMAND CENTRE", tasks: "TASK HISTORY", models: "MODEL ROUTES", integrations: "AGENTS & INTEGRATIONS", skills: "SKILLS LIBRARY" };
    $("#page-crumb").textContent = labelMap[view] || "COMMAND CENTRE";
    if (view === "tasks") renderAllTasks();
    if (view === "models") renderModels();
    if (view === "integrations") renderIntegrations();
    if (view === "skills") renderSkills();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
  function renderModelOptions() {
    const select = $("#model-route");
    const current = select.value || "auto";
    select.innerHTML = state.models.routes.map(function (route) {
      const disabled = !route.available && route.id !== "auto";
      const label = route.name + (disabled ? " — setup required" : route.id === "auto" ? " — recommended" : "");
      return '<option value="' + escapeHtml(route.id) + '"' + (disabled ? " disabled" : "") + '>' + escapeHtml(label) + '</option>';
    }).join("");
    const valid = state.models.routes.find(function (route) { return route.id === current && route.available; });
    select.value = valid ? current : (state.models.default_route || "auto");
    updateRouteHelp();
  }
  function updateRouteHelp() {
    const selected = routeById($("#model-route").value);
    $("#route-help").textContent = selected ? selected.details : "Select an available model route.";
  }
  function renderComposerSkills() {
    const approved = state.skills.skills.filter(function (skill) { return skill.status === "enabled_reviewed"; });
    const wrap = $("#composer-skills");
    if (!approved.length) {
      wrap.innerHTML = '<span class="muted-small">No reviewed skills enabled</span>';
      return;
    }
    wrap.innerHTML = approved.slice(0, 12).map(function (skill) {
      return '<label class="skill-chip" title="' + escapeHtml(skill.description) + '"><input type="checkbox" value="' + escapeHtml(skill.id) + '"><span>' + escapeHtml(skill.name) + '</span></label>';
    }).join("");
  }
  function renderStats() {
    $("#stat-tasks").textContent = String(state.tasks.length);
    const configured = state.models.routes.filter(function (route) { return route.id !== "auto" && route.available; });
    $("#stat-models").textContent = String(configured.length);
    $("#stat-models-note").textContent = configured.length ? "Configured, not health-checked" : "No cloud model configured yet";
    const ready = state.integrations.filter(function (item) { return ["available", "configured", "connected", "ready"].includes(String(item.status).toLowerCase()); });
    $("#stat-runtimes").textContent = String(ready.length);
    $("#stat-skills").textContent = String(state.skills.count || 0);
    const enabled = state.skills.skills.filter(function (skill) { return skill.status === "enabled_reviewed"; }).length;
    $("#stat-skills-note").textContent = enabled + " reviewed and enabled";
    $("#nav-task-count").textContent = state.tasks.length > 99 ? "99+" : String(state.tasks.length);
    $("#activity-sync").textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    $("#last-updated").textContent = "Synced " + new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    $("#footer-clock").textContent = new Date().toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  }
  function renderSidebarStatus(ok) {
    $("#sidebar-pulse").classList.toggle("disconnected", !ok);
    $("#sidebar-api-label").textContent = ok ? "Backend connected" : "API disconnected";
    $("#sidebar-api-detail").textContent = ok ? "Polling live task data" : "Retrying connection…";
  }
  function renderExecutionStatus() {
    const enabled = !!(state.status && state.status.execution_enabled);
    $("#runtime-mode").textContent = enabled ? "EXECUTION ENABLED" : "PLANNER MODE";
    $("#execution-notice").classList.toggle("execution-enabled", enabled);
    if (enabled) {
      $("#execution-notice").innerHTML = '<div class="notice-icon">✓</div><div><strong>Execution mode reported enabled by backend.</strong><p>Confirm that the selected worker and approval policies are configured before relying on automated actions.</p></div><a href="/docs" target="_blank" rel="noreferrer">API docs ↗</a>';
    }
  }
  function renderRecentTasks() {
    const root = $("#recent-tasks");
    if (!state.tasks.length) {
      root.innerHTML = '<div class="empty-state compact"><div class="empty-glyph">◇</div><strong>Waiting for your first task</strong><p>New task plans will appear here.</p></div>';
      return;
    }
    root.innerHTML = state.tasks.slice(0, 5).map(function (task) {
      return '<div class="task-row"><div class="task-status-icon">↗</div><div class="task-row-main"><button class="task-row-title" data-task-id="' + escapeHtml(task.id) + '">' + escapeHtml(taskTitle(task)) + '</button><div class="task-row-meta"><span>' + escapeHtml(readable(task.category)) + '</span><span>·</span><span>' + escapeHtml(dateLabel(task.created_at)) + '</span><span class="mini-status">' + escapeHtml(task.status || "planned") + '</span></div></div><span class="task-row-arrow">›</span></div>';
    }).join("");
  }
  function renderOverviewModels() {
    const items = state.models.routes.filter(function (route) { return route.id !== "auto"; }).slice(0, 4);
    $("#overview-models").innerHTML = items.length ? items.map(function (route) {
      return '<div class="compact-row"><div class="compact-icon">⌘</div><div class="compact-main"><strong>' + escapeHtml(route.name) + '</strong><small>' + escapeHtml(route.model || route.id) + '</small></div>' + statusPill(route.available ? "configured_not_tested" : "needs_setup") + '</div>';
    }).join("") : '<div class="empty-state compact"><strong>No model routes returned</strong><p>Check the backend model endpoint.</p></div>';
  }
  function renderOverviewIntegrations() {
    const preferred = ["hermes_agent", "codex_cli", "claude_code", "tmux", "livekit_agents", "blynk"];
    const items = preferred.map(function (id) { return state.integrations.find(function (item) { return item.id === id; }); }).filter(Boolean);
    $("#overview-integrations").innerHTML = items.map(function (item) {
      return '<div class="compact-row"><div class="compact-icon">' + compactIcon(item.kind) + '</div><div class="compact-main"><strong>' + escapeHtml(item.name) + '</strong><small>' + escapeHtml(item.purpose || item.details || "") + '</small></div>' + statusPill(item.status) + '</div>';
    }).join("") || '<div class="empty-state compact"><strong>No integrations returned</strong><p>Check the backend integrations endpoint.</p></div>';
  }
  function renderTaskDetail(task) {
    const target = $("#task-detail");
    if (!task) {
      target.innerHTML = '<div class="empty-state"><div class="empty-glyph">◈</div><strong>Select a task</strong><p>Task plan, route, category, risk, and approved skills will appear here.</p></div>';
      return;
    }
    const plan = Array.isArray(task.plan) ? task.plan : [];
    const codexItem = state.integrations.find(function (item) { return item.id === "codex_cli"; });
    const codexReady = !!(codexItem && String(codexItem.status).indexOf("installed_needs_verification") >= 0);
    const canRun = task.status === "planned" && task.category === "coding" && !task.approval_required && !["high", "critical"].includes(task.risk);
    const executionLog = Array.isArray(task.execution_log) ? task.execution_log : [];
    let workerSection = "";
    if (task.status === "planned" && task.category === "coding") {
      workerSection = canRun
        ? (codexReady
            ? '<button class="primary-button run-agent-button" id="run-codex-task" data-task-id="' + escapeHtml(task.id) + '"><span>Run in isolated Codex worktree</span><span class="button-arrow">↗</span></button><p class="worker-explainer">Runs in a separate Git worktree with Codex workspace-write sandbox. Changes are not merged automatically.</p>'
            : '<div class="detail-notice">Codex CLI is not detected in TEDDY’s environment. Install and authenticate Codex CLI, restart the backend, and refresh status to enable the coding worker.</div>')
        : '<div class="detail-notice">This coding task is blocked from automatic execution by its risk or approval flags.</div>';
    } else if (task.status === "running") {
      workerSection = '<div class="worker-status"><span class="activity-live-dot"></span><strong>Agent running</strong><span>Refreshing status automatically</span></div>';
    } else if (task.status === "completed" || task.status === "failed") {
      workerSection = '<div class="worker-result"><div class="detail-plan-title">AGENT RESULT</div><pre>' + escapeHtml(task.result_text || "No final message was saved.") + '</pre>' + (task.workspace_path ? '<div class="workspace-path"><span>WORKTREE</span><code>' + escapeHtml(task.workspace_path) + '</code></div>' : '') + '</div>';
    }
    target.innerHTML = '<div class="detail-kicker">TASK / ' + escapeHtml(String(task.id).slice(0, 8).toUpperCase()) + '</div>' +
      '<div class="detail-prompt">' + escapeHtml(taskTitle(task)) + '</div>' +
      '<div class="task-row-meta"><span class="mini-status">' + escapeHtml(task.status || "planned") + '</span><span>Created ' + escapeHtml(fullDate(task.created_at)) + '</span></div>' +
      '<div class="detail-meta-grid"><div class="detail-meta"><label>MODEL PROVIDER</label><strong>' + escapeHtml(task.provider || "unknown") + '</strong></div><div class="detail-meta"><label>MODEL</label><strong>' + escapeHtml(task.model || "Deterministic fallback") + '</strong></div><div class="detail-meta"><label>CATEGORY</label><strong>' + escapeHtml(readable(task.category)) + '</strong></div><div class="detail-meta"><label>RISK LEVEL</label><strong>' + escapeHtml(readable(task.risk)) + '</strong></div><div class="detail-meta"><label>AGENT RUNTIME</label><strong>' + escapeHtml(task.agent_name || "Not started") + '</strong></div></div>' +
      '<div class="detail-plan-title">GENERATED PLAN · ' + plan.length + ' STEPS</div>' +
      '<ol class="plan-list">' + plan.map(function (step) { return '<li>' + escapeHtml(step) + '</li>'; }).join("") + '</ol>' +
      workerSection +
      (executionLog.length ? '<div class="execution-events"><div class="detail-plan-title">EVENT LOG</div><ol>' + executionLog.map(function (entry) { return '<li>' + escapeHtml(entry) + '</li>'; }).join("") + '</ol></div>' : '') +
      (task.execution_mode === "plan_only" ? '<div class="detail-notice">Plan saved. No command has run yet.</div>' : '<div class="detail-notice">An agent run was explicitly requested. Review its worktree before applying any changes.</div>');
  }
  function selectTask(taskId) {
    const task = state.tasks.find(function (item) { return item.id === taskId; });
    if (!task) return;
    state.selectedTaskId = task.id;
    renderAllTasks();
    renderTaskDetail(task);
  }
  function renderAllTasks() {
    const search = ($("#task-search").value || "").trim().toLowerCase();
    const filtered = state.tasks.filter(function (task) { return taskTitle(task).toLowerCase().includes(search) || String(task.category || "").includes(search); });
    $("#task-results-count").textContent = filtered.length + " task" + (filtered.length === 1 ? "" : "s");
    const root = $("#all-tasks");
    if (!filtered.length) {
      root.innerHTML = '<div class="empty-state"><div class="empty-glyph">▤</div><strong>' + (search ? "No matching tasks" : "No tasks yet") + '</strong><p>' + (search ? "Try another search phrase." : "Create a plan from the command centre to see it here.") + '</p></div>';
    } else {
      root.innerHTML = filtered.map(function (task) {
        return '<div class="task-row ' + (state.selectedTaskId === task.id ? "selected" : "") + '"><div class="task-status-icon">↗</div><div class="task-row-main"><button class="task-row-title" data-task-id="' + escapeHtml(task.id) + '">' + escapeHtml(taskTitle(task)) + '</button><div class="task-row-meta"><span>' + escapeHtml(readable(task.category)) + '</span><span>·</span><span>' + escapeHtml(dateLabel(task.created_at)) + '</span><span class="mini-status">' + escapeHtml(task.status || "planned") + '</span></div></div><span class="task-row-arrow">›</span></div>';
      }).join("");
    }
    const selected = state.tasks.find(function (task) { return task.id === state.selectedTaskId; });
    renderTaskDetail(selected || null);
  }
  function renderModels() {
    const routes = state.models.routes || [];
    $("#model-route-count").textContent = routes.length + " routes";
    const auto = routeById(state.models.default_route || "auto") || routes[0];
    $("#default-route-title").textContent = auto ? auto.name : "Automatic route selection";
    $("#default-route-description").textContent = auto ? auto.details : "Uses whichever configured model provider is available under the backend's routing policy.";
    $("#model-grid").innerHTML = routes.map(function (route) {
      const isAuto = route.id === "auto";
      return '<article class="model-card"><div class="model-card-top"><div class="model-logo">' + (isAuto ? "✳" : "⌘") + '</div><div><h3>' + escapeHtml(route.name) + '</h3><div class="model-id">' + escapeHtml(route.model || route.id) + '</div></div>' + statusPill(route.available ? "configured_not_tested" : "needs_setup") + '</div><p>' + escapeHtml(route.details || "No description provided by backend.") + '</p><div class="model-card-footer"><span class="card-foot-label">' + (isAuto ? "Backend policy route" : "Explicit selection") + '</span><span class="card-foot-label">' + (route.available ? "Selectable" : "Setup required") + '</span></div></article>';
    }).join("") || '<div class="empty-state"><strong>No model routes returned</strong></div>';
  }
  function renderIntegrationSummary() {
    const all = state.integrations;
    const ready = all.filter(function (item) { return ["available", "configured", "connected", "ready"].includes(String(item.status).toLowerCase()); }).length;
    const configured = all.filter(function (item) { return String(item.status || "").indexOf("configured_not_tested") >= 0; }).length;
    const needsSetup = all.filter(function (item) { return /needs_setup|not_installed|adapter_pending|awaiting|pending/.test(String(item.status || "")); }).length;
    const quarantined = all.filter(function (item) { return String(item.status || "").indexOf("quarantined") >= 0; }).length;
    $("#integration-summary").innerHTML = '<div class="summary-mini"><strong>' + all.length + '</strong><span>Inventory entries</span></div><div class="summary-mini"><strong>' + ready + '</strong><span>Available / ready</span></div><div class="summary-mini"><strong>' + configured + '</strong><span>Configured, not tested</span></div><div class="summary-mini"><strong>' + quarantined + '</strong><span>Quarantined</span></div>';
    const kinds = Array.from(new Set(all.map(function (item) { return item.kind || "other"; }))).sort();
    const select = $("#integration-kind-filter");
    const before = select.value || "all";
    select.innerHTML = '<option value="all">All types</option>' + kinds.map(function (kind) { return '<option value="' + escapeHtml(kind) + '">' + escapeHtml(readable(kind)) + '</option>'; }).join("");
    select.value = kinds.indexOf(before) >= 0 ? before : "all";
    return needsSetup;
  }
  function renderIntegrations() {
    renderIntegrationSummary();
    const search = ($("#integration-search").value || "").trim().toLowerCase();
    const kind = $("#integration-kind-filter").value;
    const items = state.integrations.filter(function (item) {
      const blob = [item.name, item.id, item.kind, item.status, item.purpose, item.details].join(" ").toLowerCase();
      return (!search || blob.includes(search)) && (kind === "all" || item.kind === kind);
    });
    $("#integration-results-count").textContent = items.length + " entries";
    $("#integration-grid").innerHTML = items.map(function (item) {
      return '<article class="integration-card"><div class="integration-card-top"><div class="compact-icon">' + compactIcon(item.kind) + '</div><div><div class="integration-kind">' + escapeHtml(readable(item.kind)) + '</div><h3>' + escapeHtml(item.name) + '</h3></div></div><p>' + escapeHtml(item.purpose || item.details || "No description provided.") + '</p>' + statusPill(item.status) + '<p>' + escapeHtml(item.details || "") + '</p></article>';
    }).join("") || '<div class="empty-state"><strong>No matching integrations</strong><p>Try another search or category.</p></div>';
  }
  function renderSkills() {
    const search = ($("#skill-search").value || "").trim().toLowerCase();
    const statusFilter = $("#skill-status-filter").value;
    const skills = state.skills.skills.filter(function (skill) {
      const blob = [skill.name, skill.description, skill.source, skill.path, (skill.compatible_runtimes || []).join(" ")].join(" ").toLowerCase();
      return (!search || blob.includes(search)) && (statusFilter === "all" || skill.status === statusFilter);
    });
    $("#skill-count-label").textContent = state.skills.count + " skills";
    $("#skill-results-count").textContent = skills.length + " shown";
    $("#skills-note").textContent = state.skills.note || "Metadata endpoint response received.";
    $("#skills-table-body").innerHTML = skills.length ? skills.map(function (skill) {
      const runtimes = (skill.compatible_runtimes || []).map(function (runtime) { return '<span class="runtime-chip">' + escapeHtml(readable(runtime)) + '</span>'; }).join("");
      return '<tr><td><span class="skill-name">' + escapeHtml(skill.name) + '</span><span class="skill-desc">' + escapeHtml(skill.description) + '</span><span class="skill-desc">' + escapeHtml(skill.path) + '</span></td><td>' + escapeHtml(skill.source) + '</td><td>' + statusPill(skill.status) + '</td><td><div class="skill-runtimes">' + (runtimes || '<span class="runtime-chip">Text model</span>') + '</div></td></tr>';
    }).join("") : '<tr><td colspan="4" class="table-empty">' + (state.skills.count ? "No skills match those filters." : "No local skills discovered. Import skills into skills/imported and refresh.") + '</td></tr>';
  }
  async function loadAll(showErrors) {
    try {
      const results = await Promise.all([
        api("/health"),
        api("/api/v1/status"),
        api("/api/v1/models"),
        api("/api/v1/integrations"),
        api("/api/v1/skills"),
        api("/api/v1/tasks?limit=100")
      ]);
      state.status = results[1];
      state.models = results[2];
      state.integrations = results[3].integrations || [];
      state.skills = results[4];
      state.tasks = results[5];
      if (!state.tasks.some(function (task) { return task.id === state.selectedTaskId; })) {
        state.selectedTaskId = state.tasks.length ? state.tasks[0].id : null;
      }
      renderSidebarStatus(true);
      renderExecutionStatus();
      renderModelOptions();
      renderComposerSkills();
      renderStats();
      renderRecentTasks();
      renderOverviewModels();
      renderOverviewIntegrations();
      if (state.view === "tasks") renderAllTasks();
      if (state.view === "models") renderModels();
      if (state.view === "integrations") renderIntegrations();
      if (state.view === "skills") renderSkills();
      $("#sidebar-api-detail").textContent = state.status.configured_model || state.status.model_provider || "Local fallback available";
      return true;
    } catch (error) {
      renderSidebarStatus(false);
      if (showErrors) toast("Could not load TEDDY data: " + error.message, true);
      return false;
    }
  }
  async function submitTask(event) {
    event.preventDefault();
    const prompt = $("#task-prompt").value.trim();
    if (!prompt) {
      showFormFeedback("Enter a task description first.", true);
      return;
    }
    const route = $("#model-route").value || "auto";
    const button = $("#submit-task");
    const original = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<span>Planning task…</span><span class="button-arrow">◌</span>';
    showFormFeedback("Sending your task to the TEDDY backend…", false);
    try {
      const task = await api("/api/v1/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Accept": "application/json" },
        body: JSON.stringify({ prompt: prompt, model_route: route, skill_ids: selectedSkills() })
      });
      $("#task-prompt").value = "";
      $("#prompt-counter").textContent = "0 / 8000";
      $$("#composer-skills input[type=checkbox]").forEach(function (input) { input.checked = false; });
      showFormFeedback("Plan saved successfully. Provider: " + task.provider + (task.model ? " · Model: " + task.model : " · deterministic local fallback"), false);
      await loadAll(false);
      state.selectedTaskId = task.id;
      renderRecentTasks();
      renderAllTasks();
      toast("Task plan created and saved.");
      if (state.view !== "overview") setView("overview");
      const card = $("#recent-tasks");
      card.scrollIntoView({ behavior: "smooth", block: "nearest" });
    } catch (error) {
      showFormFeedback(error.message, true);
      toast("Task could not be created: " + error.message, true);
    } finally {
      button.disabled = false;
      button.innerHTML = original;
    }
  }
  async function runCodingTask(taskId, button) {
    if (!taskId || !button) return;
    const original = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<span>Starting Codex…</span><span class="button-arrow">◌</span>';
    try {
      const task = await api("/api/v1/tasks/" + encodeURIComponent(taskId) + "/run", {
        method: "POST",
        headers: { "Accept": "application/json" }
      });
      state.selectedTaskId = task.id;
      await loadAll(false);
      setView("tasks");
      renderAllTasks();
      toast("Codex worker started in a separate Git worktree. Watch task status here.");
    } catch (error) {
      toast(error.message, true);
      button.disabled = false;
      button.innerHTML = original;
    }
  }
  function showFormFeedback(message, isError) {
    const element = $("#form-feedback");
    element.hidden = false;
    element.textContent = message;
    element.classList.toggle("error", !!isError);
  }
  function bindEvents() {
    document.addEventListener("click", function (event) {
      const viewButton = event.target.closest("[data-view-target]");
      if (viewButton) {
        const view = viewButton.getAttribute("data-view-target");
        if (view) setView(view);
        return;
      }
      if (event.target.closest("#run-codex-task")) {
        const button = event.target.closest("#run-codex-task");
        runCodingTask(button.getAttribute("data-task-id"), button);
        return;
      }
      const taskButton = event.target.closest("[data-task-id]");
      if (taskButton) {
        const taskId = taskButton.getAttribute("data-task-id");
        state.selectedTaskId = taskId;
        if (state.view !== "tasks") setView("tasks");
        renderAllTasks();
      }
    });
    $("#refresh-button").addEventListener("click", function () { loadAll(true).then(function (ok) { if (ok) toast("TEDDY status refreshed."); }); });
    $("#tasks-refresh").addEventListener("click", function () { loadAll(true); });
    $("#integrations-refresh").addEventListener("click", function () { loadAll(true); });
    $("#task-form").addEventListener("submit", submitTask);
    $("#task-prompt").addEventListener("input", function () { $("#prompt-counter").textContent = this.value.length + " / 8000"; });
    $("#model-route").addEventListener("change", updateRouteHelp);
    $("#task-search").addEventListener("input", renderAllTasks);
    $("#integration-search").addEventListener("input", renderIntegrations);
    $("#integration-kind-filter").addEventListener("change", renderIntegrations);
    $("#skill-search").addEventListener("input", renderSkills);
    $("#skill-status-filter").addEventListener("change", renderSkills);
    $("#copy-skill-command").addEventListener("click", async function () {
      const command = "python scripts/skill_admin.py list\npython scripts/skill_admin.py show SKILL_ID\npython scripts/skill_admin.py enable SKILL_ID";
      try {
        await navigator.clipboard.writeText(command);
        toast("Skill review commands copied.");
      } catch (_) {
        toast(command);
      }
    });
  }

  bindEvents();
  loadAll(true);
  state.refreshTimer = setInterval(function () {
    if (!document.hidden) loadAll(false);
  }, 8000);
  document.addEventListener("visibilitychange", function () {
    if (!document.hidden) loadAll(false);
  });
})();