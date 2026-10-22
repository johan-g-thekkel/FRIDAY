(function () {
  "use strict";
  const state = {
    view: "overview",
    status: null,
    models: { routes: [] },
    integrations: [],
    bots: [],
    editingBotId: null,
    reviewingSkill: null,
    skills: { skills: [], count: 0 },
    tasks: [],
    selectedTaskId: null,
    taskChanges: null,
    chatMessages: [],
    chatBusy: false,
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
    const labelMap = { overview: "COMMAND CENTRE", tasks: "TASK HISTORY", bots: "BOT STUDIO", models: "MODEL ROUTES", integrations: "AGENTS & INTEGRATIONS", skills: "SKILLS LIBRARY" };
    $("#page-crumb").textContent = labelMap[view] || "COMMAND CENTRE";
    if (view === "tasks") renderAllTasks();
    if (view === "bots") renderBots();
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
    const botRoute = $("#bot-default-route");
    if (botRoute) {
      const botCurrent = botRoute.value || "auto";
      botRoute.innerHTML = state.models.routes.map(function (route) {
        const disabled = !route.available && route.id !== "auto";
        return '<option value="' + escapeHtml(route.id) + '"' + (disabled ? " disabled" : "") + '>' + escapeHtml(route.name + (disabled ? " — setup required" : "")) + '</option>';
      }).join("");
      botRoute.value = state.models.routes.some(function (route) { return route.id === botCurrent && route.available; }) ? botCurrent : "auto";
    }
  }
  function updateRouteHelp() {
    const selected = routeById($("#model-route").value);
    $("#route-help").textContent = selected ? selected.details : "Select an available model route.";
  }
  function renderComposerSkills() {
    renderBotSelect();
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
    const canRun = task.status === "planned" && task.category === "coding" && !task.approval_required && !["high", "critical"].includes(task.risk) && (!task.bot_id || task.bot_runtime === "codex_cli");
    const executionLog = Array.isArray(task.execution_log) ? task.execution_log : [];
    let workerSection = "";
    if (task.status === "planned" && task.category === "coding") {
      workerSection = canRun
        ? (codexReady
            ? '<button class="primary-button run-agent-button" id="run-codex-task" data-task-id="' + escapeHtml(task.id) + '"><span>Run in isolated Codex worktree</span><span class="button-arrow">↗</span></button><p class="worker-explainer">Runs in a separate Git worktree with Codex workspace-write sandbox. Changes are not merged automatically.</p>'
            : '<div class="detail-notice">Codex CLI is not detected in FRIDAY’s environment. In the Codespace terminal, run:<pre>npm install -g @openai/codex@latest\ncodex login</pre>Then restart FRIDAY and refresh status. <a href="https://developers.openai.com/codex/cli/" target="_blank" rel="noreferrer">Official CLI guide ↗</a></div>')
        : '<div class="detail-notice">This coding task is blocked from automatic execution by its risk or approval flags.</div>';
    } else if (task.status === "running") {
      workerSection = '<div class="worker-status"><span class="activity-live-dot"></span><strong>Agent running</strong><span>Refreshing status automatically</span></div>';
    } else if (task.status === "completed" || task.status === "failed") {
      const savedChanges = state.taskChanges && state.taskChanges.task_id === task.id ? state.taskChanges : null;
      const filesMarkup = savedChanges && savedChanges.files.length
        ? '<ul class="changed-file-list">' + savedChanges.files.map(function (file) { return '<li><code>' + escapeHtml(file) + '</code></li>'; }).join("") + '</ul>'
        : (savedChanges ? '<p class="diff-empty">Git reports no changed files.</p>' : '');
      const diffMarkup = savedChanges
        ? '<div class="task-diff-panel"><div class="task-diff-heading"><strong>WORKTREE DIFF</strong><span>' + (savedChanges.truncated ? 'OUTPUT TRUNCATED' : 'READ ONLY') + '</span></div>' + filesMarkup + '<pre>' + escapeHtml(savedChanges.diff || "(No tracked or text-file changes to display.)") + '</pre>' + (savedChanges.truncated ? '<p class="diff-empty">The diff reached the display-size limit; inspect the worktree in the Codespace for the full output.</p>' : '') + '<p class="diff-empty">' + escapeHtml(savedChanges.note || '') + '</p></div>'
        : '';
      workerSection = '<div class="worker-result"><div class="detail-plan-title">AGENT RESULT</div><pre>' + escapeHtml(task.result_text || "No final message was saved.") + '</pre>' +
        (task.workspace_path ? '<div class="workspace-path"><span>WORKTREE</span><code>' + escapeHtml(task.workspace_path) + '</code></div><button type="button" class="secondary-button inspect-changes-button" data-task-action="inspect-changes" data-task-id="' + escapeHtml(task.id) + '">Inspect changed files & diff ↗</button>' : '') +
        '</div>' + diffMarkup;
    }
    target.innerHTML = '<div class="detail-kicker">TASK / ' + escapeHtml(String(task.id).slice(0, 8).toUpperCase()) + '</div>' +
      '<div class="detail-prompt">' + escapeHtml(taskTitle(task)) + '</div>' +
      '<div class="task-row-meta"><span class="mini-status">' + escapeHtml(task.status || "planned") + '</span><span>Created ' + escapeHtml(fullDate(task.created_at)) + '</span></div>' +
      '<div class="detail-meta-grid"><div class="detail-meta"><label>MODEL PROVIDER</label><strong>' + escapeHtml(task.provider || "unknown") + '</strong></div><div class="detail-meta"><label>MODEL</label><strong>' + escapeHtml(task.model || "Deterministic fallback") + '</strong></div><div class="detail-meta"><label>CATEGORY</label><strong>' + escapeHtml(readable(task.category)) + '</strong></div><div class="detail-meta"><label>RISK LEVEL</label><strong>' + escapeHtml(readable(task.risk)) + '</strong></div><div class="detail-meta"><label>BOT PROFILE</label><strong>' + escapeHtml(task.bot_name || "FRIDAY default") + '</strong></div><div class="detail-meta"><label>AGENT RUNTIME</label><strong>' + escapeHtml(task.agent_name || "Not started") + '</strong></div></div>' +
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
      const action = skill.status === "enabled_reviewed"
        ? '<button type="button" class="text-button danger-text" data-skill-action="disable" data-skill-id="' + escapeHtml(skill.id) + '">Disable</button>'
        : '<button type="button" class="secondary-button skill-review-action" data-skill-action="review" data-skill-id="' + escapeHtml(skill.id) + '">Review & enable</button>';
      return '<tr><td><span class="skill-name">' + escapeHtml(skill.name) + '</span><span class="skill-desc">' + escapeHtml(skill.description) + '</span><span class="skill-desc">' + escapeHtml(skill.path) + '</span></td><td>' + escapeHtml(skill.source) + '</td><td>' + statusPill(skill.status) + '</td><td><div class="skill-runtimes">' + (runtimes || '<span class="runtime-chip">Text model</span>') + '</div></td><td>' + action + '</td></tr>';
    }).join("") : '<tr><td colspan="5" class="table-empty">' + (state.skills.count ? "No skills match those filters." : "No local skills discovered. Import a supported ZIP above.") + '</td></tr>';
  }
  async function openSkillReview(skillId) {
    try {
      const detail = await api("/api/v1/skills/" + encodeURIComponent(skillId));
      state.reviewingSkill = detail;
      $("#skill-review-name").textContent = detail.name;
      $("#skill-review-description").textContent = detail.description || "No description provided.";
      $("#skill-review-path").textContent = detail.source + " / " + detail.path;
      $("#skill-review-status").textContent = readable(detail.status);
      $("#skill-review-content").textContent = detail.content;
      $("#skill-review-hash").textContent = detail.content_sha256;
      $("#skill-review-expected").textContent = "ENABLE " + detail.id;
      $("#skill-review-confirm-text").value = "";
      $("#skill-review-consent").checked = false;
      $("#skill-review-enable").disabled = true;
      $("#skill-review-disable").hidden = detail.status === "disabled_pending_review";
      $("#skill-review-modal").hidden = false;
      document.body.classList.add("modal-open");
      $("#skill-review-close").focus();
    } catch (error) {
      toast("Unable to open skill review: " + error.message, true);
    }
  }
  function closeSkillReview() {
    $("#skill-review-modal").hidden = true;
    document.body.classList.remove("modal-open");
    state.reviewingSkill = null;
    $("#skill-review-content").textContent = "";
    $("#skill-review-confirm-text").value = "";
    $("#skill-review-consent").checked = false;
  }
  function validateSkillReviewForm() {
    const detail = state.reviewingSkill;
    const phrase = detail ? "ENABLE " + detail.id : "";
    const correctPhrase = $("#skill-review-confirm-text").value === phrase;
    $("#skill-review-enable").disabled = !(detail && correctPhrase && $("#skill-review-consent").checked);
  }
  async function enableReviewedSkill() {
    const detail = state.reviewingSkill;
    if (!detail) return;
    const button = $("#skill-review-enable");
    button.disabled = true;
    const original = button.innerHTML;
    button.innerHTML = '<span>Saving approval…</span>';
    try {
      await api("/api/v1/skills/" + encodeURIComponent(detail.id) + "/enable", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Accept": "application/json" },
        body: JSON.stringify({
          content_sha256: detail.content_sha256,
          confirmation: $("#skill-review-confirm-text").value
        })
      });
      closeSkillReview();
      await loadAll(false);
      setView("skills");
      toast("Skill enabled for model context. Its content is hash-pinned; changes require another review.");
    } catch (error) {
      toast(error.message, true);
      button.disabled = false;
    } finally {
      button.innerHTML = original;
    }
  }
  async function disableReviewedSkill() {
    const detail = state.reviewingSkill;
    if (!detail) return;
    if (!window.confirm('Disable skill "' + detail.name + '"? It will no longer be selectable for model tasks.')) return;
    try {
      await api("/api/v1/skills/" + encodeURIComponent(detail.id) + "/disable", {
        method: "POST", headers: { "Accept": "application/json" }
      });
      closeSkillReview();
      await loadAll(false);
      setView("skills");
      toast("Skill disabled.");
    } catch (error) {
      toast(error.message, true);
    }
  }
  async function handleSkillAction(action, skillId) {
    if (action === "review") {
      await openSkillReview(skillId);
      return;
    }
    if (action === "disable") {
      const skill = state.skills.skills.find(function (item) { return item.id === skillId; });
      if (!skill || !window.confirm('Disable skill "' + skill.name + '"?')) return;
      try {
        await api("/api/v1/skills/" + encodeURIComponent(skillId) + "/disable", {
          method: "POST", headers: { "Accept": "application/json" }
        });
        await loadAll(false);
        toast("Skill disabled.");
      } catch (error) {
        toast(error.message, true);
      }
    }
  }
  function renderBotSelect() {
    const select = $("#bot-select");
    if (!select) return;
    const current = select.value;
    const enabled = state.bots.filter(function (bot) { return bot.enabled; });
    select.innerHTML = '<option value="">FRIDAY default</option>' + enabled.map(function (bot) {
      return '<option value="' + escapeHtml(bot.id) + '">' + escapeHtml(bot.name) + '</option>';
    }).join("");
    select.value = enabled.some(function (bot) { return bot.id === current; }) ? current : "";
  }
  function renderBotSkillPicker(selectedIds) {
    const root = $("#bot-skill-picker");
    if (!root) return;
    const approved = state.skills.skills.filter(function (skill) { return skill.status === "enabled_reviewed"; });
    if (!approved.length) {
      root.innerHTML = '<span class="muted-small">No reviewed skills enabled. Review skills via the guarded CLI first.</span>';
      return;
    }
    const wanted = new Set(selectedIds || []);
    root.innerHTML = approved.map(function (skill) {
      return '<label class="bot-skill-option"><input type="checkbox" value="' + escapeHtml(skill.id) + '"' + (wanted.has(skill.id) ? " checked" : "") + '><span><strong>' + escapeHtml(skill.name) + '</strong><small>' + escapeHtml(skill.description) + '</small></span></label>';
    }).join("");
  }
  function renderBots() {
    renderBotSelect();
    renderBotSkillPicker(state.editingBotId ? ((state.bots.find(function (bot) { return bot.id === state.editingBotId; }) || {}).skill_ids || []) : []);
    $("#bot-count-label").textContent = state.bots.length + " saved bot" + (state.bots.length === 1 ? "" : "s");
    $("#nav-bot-count").textContent = String(state.bots.length);
    const root = $("#bot-list");
    if (!state.bots.length) {
      root.innerHTML = '<div class="empty-state"><div class="empty-glyph">⌬</div><strong>No Bots created yet</strong><p>Create a profile to give FRIDAY a reusable role and context.</p></div>';
      return;
    }
    root.innerHTML = state.bots.map(function (bot) {
      const skillNames = (bot.skill_ids || []).map(function (id) {
        const skill = state.skills.skills.find(function (candidate) { return candidate.id === id; });
        return skill ? skill.name : "Missing skill";
      });
      return '<article class="bot-card"><div class="bot-card-head"><div class="model-logo">⌬</div><div class="bot-card-identity"><h3>' + escapeHtml(bot.name) + '</h3><p>' + escapeHtml(bot.description || "Specialist Bot") + '</p></div><span class="status-label ' + (bot.enabled ? "good" : "neutral") + '">' + (bot.enabled ? "Enabled" : "Disabled") + '</span></div>' +
        '<div class="bot-card-tags"><span class="bot-tag">' + escapeHtml(readable(bot.runtime)) + '</span><span class="bot-tag">' + escapeHtml((routeById(bot.default_model_route) || {}).name || bot.default_model_route) + '</span><span class="bot-tag">' + skillNames.length + ' skills</span></div>' +
        '<div class="bot-card-copy"><label>INSTRUCTIONS</label><p>' + escapeHtml(bot.instructions) + '</p></div>' +
        (bot.memory ? '<div class="bot-card-memory"><label>LOCAL NOTES</label><p>' + escapeHtml(bot.memory) + '</p></div>' : '') +
        '<div class="bot-card-actions"><button class="secondary-button" data-bot-action="use" data-bot-id="' + escapeHtml(bot.id) + '"' + (!bot.enabled ? " disabled" : "") + '>Use for task</button><button class="secondary-button" data-bot-action="edit" data-bot-id="' + escapeHtml(bot.id) + '">Edit</button><button class="text-button" data-bot-action="toggle" data-bot-id="' + escapeHtml(bot.id) + '">' + (bot.enabled ? "Disable" : "Enable") + '</button><button class="text-button danger-text" data-bot-action="delete" data-bot-id="' + escapeHtml(bot.id) + '">Delete</button></div></article>';
    }).join("");
  }
  function resetBotForm() {
    state.editingBotId = null;
    $("#bot-form").reset();
    $("#bot-enabled").checked = true;
    $("#bot-form-title").textContent = "Create a specialist";
    $("#bot-form-eyebrow").textContent = "NEW BOT PROFILE";
    $("#save-bot-button").innerHTML = '<span>Create Bot</span><span class="button-arrow">↗</span>';
    $("#cancel-bot-edit").hidden = true;
    $("#bot-form-feedback").hidden = true;
    renderBotSkillPicker([]);
  }
  function editBot(botId) {
    const bot = state.bots.find(function (item) { return item.id === botId; });
    if (!bot) return;
    state.editingBotId = botId;
    $("#bot-name").value = bot.name;
    $("#bot-description").value = bot.description || "";
    $("#bot-instructions").value = bot.instructions || "";
    $("#bot-memory").value = bot.memory || "";
    $("#bot-runtime").value = bot.runtime;
    $("#bot-default-route").value = bot.default_model_route || "auto";
    $("#bot-enabled").checked = !!bot.enabled;
    renderBotSkillPicker(bot.skill_ids || []);
    $("#bot-form-title").textContent = "Edit " + bot.name;
    $("#bot-form-eyebrow").textContent = "EDIT BOT PROFILE";
    $("#save-bot-button").innerHTML = '<span>Save changes</span><span class="button-arrow">↗</span>';
    $("#cancel-bot-edit").hidden = false;
    $("#bot-form-feedback").hidden = true;
    $("#bot-form").scrollIntoView({ behavior: "smooth", block: "start" });
  }
  function showBotFeedback(message, isError) {
    const box = $("#bot-form-feedback");
    box.hidden = false;
    box.textContent = message;
    box.classList.toggle("error", !!isError);
  }
  async function saveBot(event) {
    event.preventDefault();
    const payload = {
      name: $("#bot-name").value.trim(),
      description: $("#bot-description").value.trim(),
      instructions: $("#bot-instructions").value.trim(),
      memory: $("#bot-memory").value.trim(),
      runtime: $("#bot-runtime").value,
      default_model_route: $("#bot-default-route").value || "auto",
      skill_ids: $$("#bot-skill-picker input[type=checkbox]:checked").map(function (input) { return input.value; }),
      enabled: $("#bot-enabled").checked
    };
    const button = $("#save-bot-button");
    const original = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<span>Saving Bot…</span>';
    try {
      if (state.editingBotId) {
        await api("/api/v1/bots/" + encodeURIComponent(state.editingBotId), {
          method: "PATCH", headers: { "Content-Type": "application/json", "Accept": "application/json" }, body: JSON.stringify(payload)
        });
        toast("Bot profile updated.");
      } else {
        await api("/api/v1/bots", {
          method: "POST", headers: { "Content-Type": "application/json", "Accept": "application/json" }, body: JSON.stringify(payload)
        });
        toast("Bot profile saved.");
      }
      resetBotForm();
      await loadAll(false);
      setView("bots");
    } catch (error) {
      showBotFeedback(error.message, true);
    } finally {
      button.disabled = false;
      if (!state.editingBotId) button.innerHTML = original;
    }
  }
  async function botAction(action, botId) {
    const bot = state.bots.find(function (item) { return item.id === botId; });
    if (!bot) return;
    try {
      if (action === "edit") { editBot(botId); return; }
      if (action === "use") {
        $("#bot-select").value = botId;
        setView("overview");
        toast("Selected " + bot.name + " for the next task.");
        return;
      }
      if (action === "toggle") {
        await api("/api/v1/bots/" + encodeURIComponent(botId), {
          method: "PATCH", headers: { "Content-Type": "application/json", "Accept": "application/json" }, body: JSON.stringify({ enabled: !bot.enabled })
        });
        await loadAll(false);
        setView("bots");
        toast(bot.enabled ? "Bot disabled." : "Bot enabled.");
        return;
      }
      if (action === "delete") {
        if (!window.confirm('Delete Bot "' + bot.name + '"? Existing task records will remain.')) return;
        await api("/api/v1/bots/" + encodeURIComponent(botId), { method: "DELETE", headers: { "Accept": "application/json" } });
        if (state.editingBotId === botId) resetBotForm();
        await loadAll(false);
        setView("bots");
        toast("Bot deleted.");
      }
    } catch (error) {
      toast(error.message, true);
    }
  }
  async function importSkillArchive(event) {
    event.preventDefault();
    const input = $("#skills-archive");
    const file = input.files && input.files[0];
    if (!file) {
      showSkillImportFeedback("Choose a supported ZIP archive first.", true);
      return;
    }
    const button = $("#skills-import-button");
    const original = button.innerHTML;
    const formData = new FormData();
    formData.append("file", file, file.name);
    button.disabled = true;
    button.innerHTML = '<span>Checking archive…</span>';
    showSkillImportFeedback("Uploading archive. FRIDAY will inspect canonical SKILL.md paths only.", false);
    try {
      const result = await api("/api/v1/skills/import", {
        method: "POST",
        headers: { "Accept": "application/json" },
        body: formData
      });
      input.value = "";
      $("#skills-file-name").textContent = "Choose a ZIP archive";
      showSkillImportFeedback(
        "Imported " + result.imported + " skill metadata file(s); skipped " + result.skipped + ". All imported skills remain disabled pending review.",
        false
      );
      await loadAll(false);
      setView("skills");
      toast("Skill metadata import finished. Review new entries before enabling.");
    } catch (error) {
      showSkillImportFeedback(error.message, true);
      toast("Skill import failed: " + error.message, true);
    } finally {
      button.disabled = false;
      button.innerHTML = original;
    }
  }
  function showSkillImportFeedback(message, isError) {
    const box = $("#skill-import-feedback");
    box.hidden = false;
    box.textContent = message;
    box.classList.toggle("error", !!isError);
  }
  async function loadAll(showErrors) {
    try {
      const results = await Promise.all([
        api("/health"),
        api("/api/v1/status"),
        api("/api/v1/models"),
        api("/api/v1/integrations"),
        api("/api/v1/skills"),
        api("/api/v1/tasks?limit=100"),
        api("/api/v1/bots")
      ]);
      state.status = results[1];
      state.models = results[2];
      state.integrations = results[3].integrations || [];
      state.skills = results[4];
      state.tasks = results[5];
      state.bots = results[6];
      if (!state.tasks.some(function (task) { return task.id === state.selectedTaskId; })) {
        state.selectedTaskId = state.tasks.length ? state.tasks[0].id : null;
      }
      renderSidebarStatus(true);
      renderExecutionStatus();
      renderModelOptions();
      renderFridayRoutes();
      renderComposerSkills();
      renderStats();
      renderRecentTasks();
      renderOverviewModels();
      renderOverviewIntegrations();
      if (state.view === "tasks") renderAllTasks();
      if (state.view === "bots") renderBots();
      if (state.view === "models") renderModels();
      if (state.view === "integrations") renderIntegrations();
      if (state.view === "skills") renderSkills();
      $("#sidebar-api-detail").textContent = state.status.configured_model || state.status.model_provider || "Local fallback available";
      return true;
    } catch (error) {
      renderSidebarStatus(false);
      if (showErrors) toast("Could not load FRIDAY data: " + error.message, true);
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
    showFormFeedback("Sending your task to the FRIDAY backend…", false);
    try {
      const task = await api("/api/v1/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Accept": "application/json" },
        body: JSON.stringify({ prompt: prompt, model_route: route, skill_ids: selectedSkills(), bot_id: $("#bot-select").value || null })
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
  async function inspectTaskChanges(taskId) {
    if (!taskId) return;
    try {
      const changes = await api("/api/v1/tasks/" + encodeURIComponent(taskId) + "/changes");
      state.selectedTaskId = taskId;
      state.taskChanges = changes;
      if (state.view !== "tasks") setView("tasks");
      renderAllTasks();
      toast("Read-only diff loaded. Review the changes before applying them.");
    } catch (error) {
      toast("Could not inspect worktree: " + error.message, true);
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

  function renderFridayRoutes() {
    const select = $("#friday-model-route");
    if (!select) return;
    const current = select.value || "auto";
    const routes = [{ id: "auto", name: "Configured Chinese/local profile", available: true }].concat((state.models.routes || []).filter(function (route) {
      return route.id !== "auto" && route.available && route.provider === "openai-compatible-profile";
    }));
    select.innerHTML = routes.map(function (route) {
      return '<option value="' + escapeHtml(route.id) + '">' +
        escapeHtml(route.name + (route.id === "auto" ? " — recommended" : "")) + '</option>';
    }).join("");
    select.value = routes.some(function (route) { return route.id === current; }) ? current : "auto";
    const realRoutes = routes.filter(function (route) { return route.id !== "auto"; });
    $("#friday-provider-state").textContent = realRoutes.length ? realRoutes.length + " live route(s) configured" : "No Chinese/local profile configured";
    $("#friday-chat-status").textContent = realRoutes.length
      ? "Ready to call a configured provider. Replies come from the selected model."
      : "Configure a Chinese API profile or local model endpoint. FRIDAY will not fake a reply.";
  }
  function renderFridayMessages() {
    const root = $("#friday-chat-messages");
    if (!state.chatMessages.length) {
      root.innerHTML = '<div class="friday-welcome"><div class="friday-welcome-symbol">✳</div><h3>What should we solve?</h3><p>Ask for coding help, architecture, research synthesis, debugging, or planning. FRIDAY will use the selected live model and report provider errors honestly.</p><div class="friday-suggestions"><button type="button" data-friday-prompt="Design a robust local-first AI agent architecture for FRIDAY, with bounded retries and test verification.">Design agent architecture</button><button type="button" data-friday-prompt="Help me debug my Python project. Ask for the necessary files and propose a testable fix.">Debug a project</button><button type="button" data-friday-prompt="Create a multi-source research plan and separate verified facts from assumptions.">Plan research</button></div></div>';
      return;
    }
    root.replaceChildren();
    state.chatMessages.forEach(function (message) {
      const row = document.createElement("article");
      row.className = "friday-message " + (message.role === "user" ? "user" : "assistant");
      const label = document.createElement("div");
      label.className = "friday-message-label";
      label.textContent = message.role === "user" ? "YOU" : "FRIDAY" + (message.provider ? " · " + message.provider + (message.model ? " / " + message.model : "") : "");
      const body = document.createElement("div");
      body.className = "friday-message-body";
      body.textContent = message.content;
      row.append(label, body);
      if (message.role === "assistant" && !message.pending && message.content) {
        const speak = document.createElement("button");
        speak.type = "button";
        speak.className = "text-button friday-speak-button";
        speak.textContent = "▶ Listen";
        speak.setAttribute("data-friday-speak-index", String(state.chatMessages.indexOf(message)));
        row.appendChild(speak);
      }
      root.appendChild(row);
    });
    root.scrollTop = root.scrollHeight;
  }
  function openFridayChat() {
    $("#friday-chat-modal").hidden = false;
    document.body.classList.add("modal-open");
    renderFridayRoutes();
    $("#friday-chat-input").focus();
  }
  function closeFridayChat() {
    $("#friday-chat-modal").hidden = true;
    document.body.classList.remove("modal-open");
  }
  async function speakFridayMessage(index, button) {
    const message = state.chatMessages[index];
    if (!message || message.role !== "assistant" || !message.content) return;
    const original = button.textContent;
    button.disabled = true;
    button.textContent = "Generating voice…";
    try {
      const response = await fetch("/api/v1/voice/speech", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Accept": "audio/mpeg" },
        body: JSON.stringify({ text: message.content })
      });
      if (!response.ok) {
        let detail = "Voice generation failed.";
        try { const data = await response.json(); detail = data.detail || detail; } catch (_) {}
        throw new Error(detail);
      }
      const audioUrl = URL.createObjectURL(await response.blob());
      const audio = new Audio(audioUrl);
      audio.onended = function () { URL.revokeObjectURL(audioUrl); button.disabled = false; button.textContent = original; };
      audio.onerror = function () { URL.revokeObjectURL(audioUrl); button.disabled = false; button.textContent = original; toast("Could not play generated audio."); };
      await audio.play();
      button.textContent = "Playing…";
    } catch (error) {
      button.disabled = false;
      button.textContent = original;
      toast(error.message || "Voice generation failed.");
    }
  }

  function startFridayDictation() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const input = $("#friday-chat-input");
    if (!SpeechRecognition) {
      $("#friday-voice-status").textContent = "Browser speech recognition unavailable. Focus the message box and use your Wispr Flow hotkey to dictate.";
      input.focus();
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.lang = navigator.language || "en-IN";
    recognition.interimResults = true;
    recognition.continuous = false;
    const prior = input.value;
    $("#friday-voice-input").disabled = true;
    $("#friday-voice-status").textContent = "Listening… speak now.";
    recognition.onresult = function (event) {
      let transcript = "";
      for (let i = event.resultIndex; i < event.results.length; i++) transcript += event.results[i][0].transcript;
      input.value = prior ? prior + " " + transcript : transcript;
    };
    recognition.onerror = function (event) {
      $("#friday-voice-status").textContent = "Mic error: " + event.error + ". You can also dictate with Wispr Flow.";
    };
    recognition.onend = function () {
      $("#friday-voice-input").disabled = false;
      if ($("#friday-voice-status").textContent === "Listening… speak now.") $("#friday-voice-status").textContent = "Dictation ready. Review transcript before sending.";
      input.focus();
    };
    try { recognition.start(); }
    catch (_) {
      $("#friday-voice-input").disabled = false;
      $("#friday-voice-status").textContent = "Could not start microphone. Check browser permission or use Wispr Flow.";
    }
  }

  async function sendFridayMessage(event) {
    event.preventDefault();
    if (state.chatBusy) return;
    const input = $("#friday-chat-input");
    const content = input.value.trim();
    if (!content) return;
    state.chatMessages.push({ role: "user", content: content });
    input.value = "";
    state.chatBusy = true;
    const send = $("#friday-chat-send");
    send.disabled = true;
    send.innerHTML = "<span>Thinking…</span><span class=\"button-arrow\">◌</span>";
    state.chatMessages.push({ role: "assistant", content: "Contacting the selected model…", pending: true });
    renderFridayMessages();
    try {
      const messages = state.chatMessages.filter(function (item) { return !item.pending; }).map(function (item) {
        return { role: item.role, content: item.content };
      });
      const result = await api("/api/v1/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Accept": "application/json" },
        body: JSON.stringify({ messages: messages, model_route: $("#friday-model-route").value || "auto" })
      });
      state.chatMessages.pop();
      state.chatMessages.push({ role: "assistant", content: result.answer, provider: result.provider, model: result.model });
      $("#friday-chat-status").textContent = "Answered by " + result.provider + (result.model ? " · " + result.model : "");
      renderFridayMessages();
    } catch (error) {
      state.chatMessages.pop();
      state.chatMessages.push({ role: "assistant", content: "I could not reach a live AI model. " + error.message + "\n\nOpen docs/FRIDAY_LOCAL_SETUP.md and configure a provider. This is an actual connection error, not a generated answer." });
      $("#friday-chat-status").textContent = "Provider request failed — check configuration.";
      renderFridayMessages();
    } finally {
      state.chatBusy = false;
      send.disabled = false;
      send.innerHTML = "<span>Send</span><span class=\"button-arrow\">↗</span>";
      input.focus();
    }
  }

  function bindEvents() {
    document.addEventListener("click", function (event) {
      const viewButton = event.target.closest("[data-view-target]");
      if (viewButton) {
        const view = viewButton.getAttribute("data-view-target");
        if (view) setView(view);
        return;
      }
      const skillActionButton = event.target.closest("[data-skill-action]");
      if (skillActionButton) {
        handleSkillAction(skillActionButton.getAttribute("data-skill-action"), skillActionButton.getAttribute("data-skill-id"));
        return;
      }
      const botActionButton = event.target.closest("[data-bot-action]");
      if (botActionButton) {
        botAction(botActionButton.getAttribute("data-bot-action"), botActionButton.getAttribute("data-bot-id"));
        return;
      }
      if (event.target.closest("#run-codex-task")) {
        const button = event.target.closest("#run-codex-task");
        runCodingTask(button.getAttribute("data-task-id"), button);
        return;
      }
      const taskAction = event.target.closest("[data-task-action]");
      if (taskAction) {
        if (taskAction.getAttribute("data-task-action") === "inspect-changes") {
          inspectTaskChanges(taskAction.getAttribute("data-task-id"));
        }
        return;
      }
      const taskButton = event.target.closest("[data-task-id]");
      if (taskButton) {
        const taskId = taskButton.getAttribute("data-task-id");
        if (state.selectedTaskId !== taskId) state.taskChanges = null;
        state.selectedTaskId = taskId;
        if (state.view !== "tasks") setView("tasks");
        renderAllTasks();
      }
    });
    $("#open-friday-chat").addEventListener("click", openFridayChat);
    $("#close-friday-chat").addEventListener("click", closeFridayChat);
    $("#friday-chat-modal").addEventListener("click", function (event) {
      if (event.target === $("#friday-chat-modal")) closeFridayChat();
      const suggestion = event.target.closest("[data-friday-prompt]");
      if (suggestion) { $("#friday-chat-input").value = suggestion.getAttribute("data-friday-prompt"); $("#friday-chat-input").focus(); }
    });
    $("#friday-chat-form").addEventListener("submit", sendFridayMessage);
    $("#friday-voice-input").addEventListener("click", startFridayDictation);
    $("#friday-chat-messages").addEventListener("click", function (event) {
      const button = event.target.closest("[data-friday-speak-index]");
      if (button) speakFridayMessage(Number(button.getAttribute("data-friday-speak-index")), button);
    });
    $("#friday-chat-input").addEventListener("keydown", function (event) {
      if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); $("#friday-chat-form").requestSubmit(); }
    });
    $("#friday-model-route").addEventListener("change", function () {
      const route = routeById(this.value);
      $("#friday-provider-state").textContent = route && route.available ? "Configured route selected" : "Route needs setup";
    });
    $("#clear-friday-chat").addEventListener("click", function () {
      if (state.chatBusy) return;
      state.chatMessages = [];
      renderFridayMessages();
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && !$("#friday-chat-modal").hidden) closeFridayChat();
    });
    $("#refresh-button").addEventListener("click", function () { loadAll(true).then(function (ok) { if (ok) toast("FRIDAY status refreshed."); }); });
    $("#tasks-refresh").addEventListener("click", function () { loadAll(true); });
    $("#integrations-refresh").addEventListener("click", function () { loadAll(true); });
    $("#task-form").addEventListener("submit", submitTask);
    $("#bot-form").addEventListener("submit", saveBot);
    $("#cancel-bot-edit").addEventListener("click", resetBotForm);
    $("#bots-refresh").addEventListener("click", function () { loadAll(true); });
    $("#task-prompt").addEventListener("input", function () { $("#prompt-counter").textContent = this.value.length + " / 8000"; });
    $("#model-route").addEventListener("change", updateRouteHelp);
    $("#task-search").addEventListener("input", renderAllTasks);
    $("#integration-search").addEventListener("input", renderIntegrations);
    $("#integration-kind-filter").addEventListener("change", renderIntegrations);
    $("#skill-search").addEventListener("input", renderSkills);
    $("#skill-status-filter").addEventListener("change", renderSkills);
    $("#skill-review-close").addEventListener("click", closeSkillReview);
    $("#skill-review-cancel").addEventListener("click", closeSkillReview);
    $("#skill-review-modal").addEventListener("click", function (event) {
      if (event.target === this) closeSkillReview();
    });
    $("#skill-review-confirm-text").addEventListener("input", validateSkillReviewForm);
    $("#skill-review-consent").addEventListener("change", validateSkillReviewForm);
    $("#skill-review-enable").addEventListener("click", enableReviewedSkill);
    $("#skill-review-disable").addEventListener("click", disableReviewedSkill);
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && !$("#skill-review-modal").hidden) closeSkillReview();
    });
    $("#skill-import-form").addEventListener("submit", importSkillArchive);
    $("#skills-archive").addEventListener("change", function () {
      const file = this.files && this.files[0];
      $("#skills-file-name").textContent = file ? file.name : "Choose a ZIP archive";
    });
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