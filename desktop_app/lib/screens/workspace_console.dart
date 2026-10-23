import 'dart:async';
import 'dart:convert';

import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

const _cyan = Color(0xFF77E9F4);
const _violet = Color(0xFFA99CFF);
const _muted = Color(0xFF92A4C8);
const _panel = Color(0xCC111A30);
const _line = Color(0xFF273654);

enum _Section { overview, tasks, bots, skills, models, connections }

class WorkspaceConsole extends StatefulWidget {
  const WorkspaceConsole({super.key, required this.apiBaseUrl});
  final String apiBaseUrl;

  @override
  State<WorkspaceConsole> createState() => _WorkspaceConsoleState();
}

class _WorkspaceConsoleState extends State<WorkspaceConsole> {
  final http.Client _client = http.Client();
  _Section _section = _Section.overview;
  bool _loading = true;
  bool _busy = false;
  String? _error;
  List<Map<String, dynamic>> _tasks = [];
  List<Map<String, dynamic>> _bots = [];
  List<Map<String, dynamic>> _skills = [];
  List<Map<String, dynamic>> _routes = [];
  List<Map<String, dynamic>> _integrations = [];
  String get _base => widget.apiBaseUrl.trim().replaceFirst(RegExp(r'/+$'), '');

  @override
  void initState() {
    super.initState();
    unawaited(_reload());
  }

  @override
  void dispose() {
    _client.close();
    super.dispose();
  }

  Future<dynamic> _request(String path, {String method = 'GET', Object? body, Duration timeout = const Duration(seconds: 20)}) async {
    final uri = Uri.parse('$_base$path');
    final headers = <String, String>{'Accept': 'application/json'};
    if (body != null) headers['Content-Type'] = 'application/json';
    late http.Response response;
    switch (method) {
      case 'POST':
        response = await _client.post(uri, headers: headers, body: body == null ? null : jsonEncode(body)).timeout(timeout);
        break;
      case 'PATCH':
        response = await _client.patch(uri, headers: headers, body: body == null ? null : jsonEncode(body)).timeout(timeout);
        break;
      case 'DELETE':
        response = await _client.delete(uri, headers: headers).timeout(timeout);
        break;
      default:
        response = await _client.get(uri, headers: headers).timeout(timeout);
        break;
    }
    dynamic data;
    try {
      data = jsonDecode(response.body);
    } catch (_) {
      data = {'detail': response.body};
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      final detail = data is Map ? data['detail']?.toString() : null;
      throw Exception(detail?.isNotEmpty == true ? detail : 'API request failed (${response.statusCode}).');
    }
    return data;
  }

  Map<String, dynamic> _map(dynamic value) => value is Map ? Map<String, dynamic>.from(value) : <String, dynamic>{};
  List<Map<String, dynamic>> _maps(dynamic value) => value is List ? value.whereType<Map>().map((e) => Map<String, dynamic>.from(e)).toList() : <Map<String, dynamic>>[];
  List<String> _strings(dynamic value) => value is List ? value.map((e) => e.toString()).toList() : <String>[];

  Future<void> _reload() async {
    if (mounted) setState(() { _loading = true; _error = null; });
    try {
      final data = await Future.wait<dynamic>([
        _request('/api/v1/tasks?limit=60'),
        _request('/api/v1/bots'),
        _request('/api/v1/skills'),
        _request('/api/v1/models'),
        _request('/api/v1/integrations'),
      ]);
      if (!mounted) return;
      setState(() {
        _tasks = _maps(data[0]);
        _bots = _maps(data[1]);
        _skills = _maps(_map(data[2])['skills']);
        _routes = _maps(_map(data[3])['routes']);
        _integrations = _maps(_map(data[4])['integrations']);
        _loading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() { _loading = false; _error = error.toString().replaceFirst('Exception: ', ''); });
    }
  }

  void _notify(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)..hideCurrentSnackBar()..showSnackBar(SnackBar(content: Text(message)));
  }

  Future<void> _perform(Future<void> Function() action, {String? success}) async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      await action();
      if (success != null && mounted) _notify(success);
      await _reload();
    } catch (error) {
      _notify(error.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _createTask() async {
    final prompt = TextEditingController();
    String route = 'auto';
    String? botId;
    final created = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(builder: (context, setDialogState) => AlertDialog(
        title: const Text('Create a task plan'),
        content: SizedBox(
          width: 520,
          child: SingleChildScrollView(child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('Describe the outcome you want FRIDAY to plan.', style: TextStyle(color: _muted, fontSize: 12)),
            const SizedBox(height: 9),
            TextField(controller: prompt, minLines: 4, maxLines: 8, maxLength: 8000, decoration: const InputDecoration(hintText: 'Build a Python calculator with unit tests.', border: OutlineInputBorder())),
            const SizedBox(height: 10),
            DropdownButtonFormField<String?>(
              initialValue: botId,
              isExpanded: true,
              decoration: const InputDecoration(labelText: 'Bot profile', border: OutlineInputBorder()),
              items: [
                const DropdownMenuItem<String?>(value: null, child: Text('FRIDAY defaults')),
                ..._bots.where((b) => b['enabled'] == true).map((b) => DropdownMenuItem<String?>(value: b['id']?.toString(), child: Text(b['name']?.toString() ?? 'Unnamed bot'))),
              ],
              onChanged: (value) => setDialogState(() => botId = value),
            ),
            const SizedBox(height: 10),
            DropdownButtonFormField<String>(
              initialValue: _routes.any((r) => r['id'] == route) ? route : 'auto',
              isExpanded: true,
              decoration: const InputDecoration(labelText: 'Model route', border: OutlineInputBorder()),
              items: _routes.map((r) {
                final id = r['id']?.toString() ?? 'auto';
                final ready = r['available'] == true;
                return DropdownMenuItem<String>(value: id, enabled: ready, child: Text('${r['name'] ?? id}${ready ? '' : ' · needs setup'}', overflow: TextOverflow.ellipsis));
              }).toList(),
              onChanged: (value) => setDialogState(() => route = value ?? 'auto'),
            ),
            const SizedBox(height: 8),
            const Text('Creating a task makes a plan only. Running code is a separate, guarded action.', style: TextStyle(color: _muted, fontSize: 11)),
          ])),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(dialogContext), child: const Text('Cancel')),
          FilledButton.icon(onPressed: () {
            if (prompt.text.trim().isEmpty) return;
            Navigator.pop(dialogContext, {'prompt': prompt.text.trim(), 'model_route': route, if (botId != null) 'bot_id': botId});
          }, icon: const Icon(Icons.playlist_add), label: const Text('Create plan')),
        ],
      )),
    );
    prompt.dispose();
    if (created == null) return;
    await _perform(() async {
      await _request('/api/v1/tasks', method: 'POST', body: created, timeout: const Duration(minutes: 3));
    }, success: 'Task plan created. No commands have been run.');
  }

  Future<void> _showTask(Map<String, dynamic> task) async {
    final plan = _strings(task['plan']);
    final log = _strings(task['execution_log']);
    final id = task['id']?.toString() ?? '';
    final canRun = task['status'] == 'planned' && task['category'] == 'coding' &&
        !{'high', 'critical'}.contains(task['risk']) && task['approval_required'] != true &&
        (task['bot_id'] == null || task['bot_runtime'] == 'codex_cli');
    await showDialog<void>(context: context, builder: (dialogContext) => AlertDialog(
      title: Text((task['prompt'] ?? 'Task details').toString(), maxLines: 3, overflow: TextOverflow.ellipsis),
      content: SizedBox(width: 620, child: SingleChildScrollView(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Wrap(spacing: 7, runSpacing: 7, children: [
          _pill('STATUS · ${task['status'] ?? 'unknown'}'),
          _pill('RISK · ${task['risk'] ?? 'unknown'}'),
          _pill('CATEGORY · ${task['category'] ?? 'general'}'),
          _pill('PROVIDER · ${task['provider'] ?? 'unknown'}'),
        ]),
        const SizedBox(height: 17),
        const Text('Plan', style: TextStyle(fontWeight: FontWeight.w800, color: _cyan)),
        const SizedBox(height: 8),
        if (plan.isEmpty) const Text('No plan details supplied.'),
        ...plan.asMap().entries.map((e) => Padding(padding: const EdgeInsets.only(bottom: 7), child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('${e.key + 1}. ', style: const TextStyle(color: _cyan)),
          Expanded(child: Text(e.value)),
        ]))),
        if ((task['result_text'] ?? '').toString().isNotEmpty) ...[
          const SizedBox(height: 14),
          const Text('Result', style: TextStyle(fontWeight: FontWeight.w800, color: _cyan)),
          const SizedBox(height: 6),
          SelectableText(task['result_text'].toString()),
        ],
        const SizedBox(height: 14),
        const Text('Execution log', style: TextStyle(fontWeight: FontWeight.w800, color: _cyan)),
        const SizedBox(height: 6),
        SelectableText(log.isEmpty ? 'No execution events yet.' : log.join('\n')),
        if (task['approval_required'] == true) const Padding(padding: EdgeInsets.only(top: 12), child: Text('This plan requires approval; it cannot be auto-dispatched.', style: TextStyle(color: Color(0xFFFFC17B)))),
      ]))),
      actions: [
        if (canRun) FilledButton.icon(onPressed: _busy ? null : () async {
          Navigator.pop(dialogContext);
          await _perform(() async {
            await _request('/api/v1/tasks/$id/run', method: 'POST', timeout: const Duration(seconds: 30));
          }, success: 'Submitted to the isolated Codex worker. Refresh task status for updates.');
        }, icon: const Icon(Icons.terminal), label: const Text('Run in isolated Codex worktree')),
        TextButton(onPressed: () => Navigator.pop(dialogContext), child: const Text('Close')),
      ],
    ));
  }

  Future<void> _editBot([Map<String, dynamic>? bot]) async {
    final name = TextEditingController(text: bot?['name']?.toString() ?? '');
    final description = TextEditingController(text: bot?['description']?.toString() ?? '');
    final instructions = TextEditingController(text: bot?['instructions']?.toString() ?? '');
    final memory = TextEditingController(text: bot?['memory']?.toString() ?? '');
    var route = bot?['default_model_route']?.toString() ?? 'auto';
    var runtime = bot?['runtime']?.toString() ?? 'plan_only';
    final saved = await showDialog<Map<String, dynamic>>(context: context, builder: (dialogContext) => StatefulBuilder(builder: (context, setDialogState) => AlertDialog(
      title: Text(bot == null ? 'Create bot profile' : 'Edit ${bot['name']}'),
      content: SizedBox(width: 580, child: SingleChildScrollView(child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
        TextField(controller: name, maxLength: 80, decoration: const InputDecoration(labelText: 'Bot name', border: OutlineInputBorder())),
        const SizedBox(height: 9),
        TextField(controller: description, maxLength: 300, decoration: const InputDecoration(labelText: 'Description', border: OutlineInputBorder())),
        const SizedBox(height: 9),
        TextField(controller: instructions, maxLength: 6000, minLines: 3, maxLines: 6, decoration: const InputDecoration(labelText: 'Instructions *', border: OutlineInputBorder())),
        const SizedBox(height: 9),
        TextField(controller: memory, maxLength: 4000, minLines: 2, maxLines: 4, decoration: const InputDecoration(labelText: 'Persistent memory / notes', border: OutlineInputBorder())),
        const SizedBox(height: 11),
        DropdownButtonFormField<String>(
          initialValue: _routes.any((r) => r['id'] == route) ? route : 'auto',
          decoration: const InputDecoration(labelText: 'Preferred model route', border: OutlineInputBorder()),
          items: _routes.map((r) => DropdownMenuItem<String>(value: r['id']?.toString() ?? 'auto', enabled: r['available'] == true, child: Text(r['name']?.toString() ?? 'auto', overflow: TextOverflow.ellipsis))).toList(),
          onChanged: (value) => setDialogState(() => route = value ?? 'auto'),
        ),
        const SizedBox(height: 10),
        DropdownButtonFormField<String>(
          initialValue: runtime,
          decoration: const InputDecoration(labelText: 'Runtime', border: OutlineInputBorder()),
          items: const [
            DropdownMenuItem(value: 'plan_only', child: Text('Plan only (safe default)')),
            DropdownMenuItem(value: 'codex_cli', child: Text('Codex CLI (guarded coding tasks)')),
          ],
          onChanged: (value) => setDialogState(() => runtime = value ?? 'plan_only'),
        ),
        const SizedBox(height: 8),
        const Text('Saving a profile does not launch an agent. Codex dispatch still requires the authenticated CLI and backend safeguards.', style: TextStyle(color: _muted, fontSize: 11)),
      ]))),
      actions: [
        TextButton(onPressed: () => Navigator.pop(dialogContext), child: const Text('Cancel')),
        FilledButton.icon(onPressed: () {
          if (name.text.trim().isEmpty || instructions.text.trim().isEmpty) return;
          Navigator.pop(dialogContext, {
            'name': name.text.trim(), 'description': description.text.trim(),
            'instructions': instructions.text.trim(), 'memory': memory.text.trim(),
            'default_model_route': route, 'runtime': runtime,
            'enabled': bot == null ? true : bot['enabled'] == true,
            'skill_ids': _strings(bot?['skill_ids']),
          });
        }, icon: const Icon(Icons.save_outlined), label: const Text('Save bot')),
      ],
    )));
    name.dispose(); description.dispose(); instructions.dispose(); memory.dispose();
    if (saved == null) return;
    await _perform(() async {
      if (bot == null) {
        await _request('/api/v1/bots', method: 'POST', body: saved);
      } else {
        await _request('/api/v1/bots/${bot['id']}', method: 'PATCH', body: saved);
      }
    }, success: 'Bot profile saved.');
  }

  Future<void> _setBotEnabled(Map<String, dynamic> bot, bool enabled) async {
    await _perform(() async {
      await _request('/api/v1/bots/${bot['id']}', method: 'PATCH', body: {'enabled': enabled});
    }, success: enabled ? 'Bot enabled.' : 'Bot disabled.');
  }

  Future<void> _deleteBot(Map<String, dynamic> bot) async {
    final yes = await showDialog<bool>(context: context, builder: (context) => AlertDialog(
      title: Text('Delete ${bot['name']}?'),
      content: const Text('The saved profile will be removed; task history remains.'),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
        FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Delete')),
      ],
    ));
    if (yes != true) return;
    await _perform(() async {
      await _request('/api/v1/bots/${bot['id']}', method: 'DELETE');
    }, success: 'Bot profile deleted.');
  }

  Future<void> _importSkills() async {
    final file = await openFile(acceptedTypeGroups: const [XTypeGroup(label: 'Skill archive ZIP', extensions: ['zip'])]);
    if (file == null) return;
    const supported = {'ECC-main.zip', 'Desktop2222.zip', 'teddy-skill-candidates.zip'};
    if (!supported.contains(file.name)) {
      _notify('Rename the archive to ECC-main.zip, Desktop2222.zip or teddy-skill-candidates.zip before importing.');
      return;
    }
    await _perform(() async {
      final request = http.MultipartRequest('POST', Uri.parse('$_base/api/v1/skills/import'));
      request.files.add(await http.MultipartFile.fromPath('file', file.path, filename: file.name));
      final streamed = await _client.send(request).timeout(const Duration(minutes: 5));
      final response = await http.Response.fromStream(streamed);
      dynamic data;
      try { data = jsonDecode(response.body); } catch (_) { data = {'detail': response.body}; }
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw Exception(data is Map ? data['detail']?.toString() ?? 'Skill import failed.' : 'Skill import failed.');
      }
      _notify('Imported ${data['imported'] ?? 0} skills; ${data['skipped'] ?? 0} skipped. Review each skill before enabling.');
    }, success: 'Skill inventory refreshed.');
  }

  Future<void> _reviewSkill(Map<String, dynamic> skill) async {
    Map<String, dynamic> detail;
    try {
      detail = _map(await _request('/api/v1/skills/${skill['id']}'));
    } catch (error) {
      _notify(error.toString().replaceFirst('Exception: ', ''));
      return;
    }
    final confirmation = TextEditingController();
    final result = await showDialog<String>(context: context, builder: (dialogContext) => StatefulBuilder(builder: (context, setDialogState) => AlertDialog(
      title: Text((detail['name'] ?? 'Skill review').toString()),
      content: SizedBox(width: 740, height: 500, child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('${detail['path'] ?? ''} · ${detail['status'] ?? ''}', style: const TextStyle(color: _muted, fontSize: 11)),
        const SizedBox(height: 8),
        const Text('Treat this file as untrusted. Read it before approving; FRIDAY does not execute imported skill code.', style: TextStyle(color: Color(0xFFFFC17B), fontSize: 11)),
        const SizedBox(height: 8),
        Expanded(child: Container(width: double.infinity, padding: const EdgeInsets.all(12), decoration: BoxDecoration(color: const Color(0xFF080C18), borderRadius: BorderRadius.circular(10), border: Border.all(color: _line)), child: SingleChildScrollView(child: SelectableText((detail['content'] ?? '').toString(), style: const TextStyle(fontFamily: 'Consolas', fontSize: 11, height: 1.4))))),
        const SizedBox(height: 10),
        TextField(controller: confirmation, decoration: InputDecoration(labelText: 'Type ENABLE ${detail['id']} to approve', border: const OutlineInputBorder()), onChanged: (_) => setDialogState(() {})),
      ])),
      actions: [
        if (detail['status'] == 'enabled_reviewed') TextButton(onPressed: () => Navigator.pop(dialogContext, 'disable'), child: const Text('Disable skill')),
        TextButton(onPressed: () => Navigator.pop(dialogContext), child: const Text('Close')),
        FilledButton.icon(
          onPressed: confirmation.text == 'ENABLE ${detail['id']}' ? () => Navigator.pop(dialogContext, 'enable') : null,
          icon: const Icon(Icons.verified_user_outlined), label: const Text('Approve skill'),
        ),
      ],
    )));
    confirmation.dispose();
    if (result == null) return;
    await _perform(() async {
      if (result == 'disable') {
        await _request('/api/v1/skills/${detail['id']}/disable', method: 'POST');
      } else {
        await _request('/api/v1/skills/${detail['id']}/enable', method: 'POST', body: {
          'content_sha256': detail['content_sha256'],
          'confirmation': 'ENABLE ${detail['id']}',
        });
      }
    }, success: result == 'enable' ? 'Skill approved for planning.' : 'Skill disabled.');
  }

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.sizeOf(context).width >= 900;
    return Scaffold(
      appBar: AppBar(
        title: const Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('FRIDAY OPERATIONS', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w900, letterSpacing: 1.4)),
          Text('Tasks · Bots · Skills · Model routes · Connections', style: TextStyle(fontSize: 10, color: _muted)),
        ]),
        actions: [
          Padding(padding: const EdgeInsets.only(right: 8), child: Center(child: Text(_base, style: const TextStyle(color: _muted, fontSize: 10)))),
          IconButton(tooltip: 'Refresh all data', onPressed: _busy ? null : _reload, icon: const Icon(Icons.refresh_rounded)),
          const SizedBox(width: 8),
        ],
      ),
      body: Row(children: [
        if (wide) NavigationRail(
          extended: true, backgroundColor: const Color(0xAA0B1121),
          selectedIndex: _section.index,
          onDestinationSelected: (i) => setState(() => _section = _Section.values[i]),
          destinations: const [
            NavigationRailDestination(icon: Icon(Icons.dashboard_outlined), selectedIcon: Icon(Icons.dashboard), label: Text('Overview')),
            NavigationRailDestination(icon: Icon(Icons.checklist_rounded), selectedIcon: Icon(Icons.checklist), label: Text('Tasks')),
            NavigationRailDestination(icon: Icon(Icons.smart_toy_outlined), selectedIcon: Icon(Icons.smart_toy), label: Text('Bots / Agents')),
            NavigationRailDestination(icon: Icon(Icons.extension_outlined), selectedIcon: Icon(Icons.extension), label: Text('Skills')),
            NavigationRailDestination(icon: Icon(Icons.hub_outlined), selectedIcon: Icon(Icons.hub), label: Text('Models')),
            NavigationRailDestination(icon: Icon(Icons.cable_outlined), selectedIcon: Icon(Icons.cable), label: Text('Connections')),
          ],
        ),
        Expanded(child: Column(children: [
          if (!wide) SizedBox(height: 56, child: ListView(scrollDirection: Axis.horizontal, padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8), children: _Section.values.map((s) => Padding(
            padding: const EdgeInsets.only(right: 8),
            child: ChoiceChip(label: Text(_label(s)), selected: _section == s, onSelected: (_) => setState(() => _section = s)),
          )).toList())),
          Expanded(child: _loading ? const Center(child: CircularProgressIndicator()) : _error != null ? _errorView() : RefreshIndicator(onRefresh: _reload, child: _content())),
        ])),
      ]),
      floatingActionButton: _section == _Section.tasks
          ? FloatingActionButton.extended(onPressed: _busy ? null : _createTask, icon: const Icon(Icons.add_task), label: const Text('New task'))
          : _section == _Section.bots
              ? FloatingActionButton.extended(onPressed: _busy ? null : () => _editBot(), icon: const Icon(Icons.smart_toy_outlined), label: const Text('New bot'))
              : null,
    );
  }

  String _label(_Section section) => switch (section) {
    _Section.overview => 'Overview', _Section.tasks => 'Tasks', _Section.bots => 'Bots',
    _Section.skills => 'Skills', _Section.models => 'Models', _Section.connections => 'Connections',
  };

  Widget _errorView() => ListView(padding: const EdgeInsets.all(28), children: [
    const Icon(Icons.cloud_off_outlined, size: 48, color: Color(0xFFFFA1AE)),
    const SizedBox(height: 12),
    const Text('The FRIDAY API is unavailable', textAlign: TextAlign.center, style: TextStyle(fontWeight: FontWeight.w800, fontSize: 20)),
    const SizedBox(height: 8),
    Text(_error!, textAlign: TextAlign.center, style: const TextStyle(color: _muted)),
    const SizedBox(height: 16),
    Center(child: FilledButton.icon(onPressed: _reload, icon: const Icon(Icons.refresh), label: const Text('Retry'))),
  ]);

  Widget _content() => switch (_section) {
    _Section.overview => _overview(), _Section.tasks => _tasksView(),
    _Section.bots => _botsView(), _Section.skills => _skillsView(),
    _Section.models => _modelsView(), _Section.connections => _connectionsView(),
  };

  Widget _overview() {
    final planned = _tasks.where((t) => t['status'] == 'planned').length;
    final active = _tasks.where((t) => t['status'] == 'running').length;
    final enabledBots = _bots.where((b) => b['enabled'] == true).length;
    final approved = _skills.where((s) => s['status'] == 'enabled_reviewed').length;
    return ListView(physics: const AlwaysScrollableScrollPhysics(), padding: const EdgeInsets.all(24), children: [
      const Text('Workspace pulse', style: TextStyle(fontSize: 25, fontWeight: FontWeight.w800)),
      const SizedBox(height: 6),
      const Text('One native control room for planning, bot profiles, reviewed skills and runtime readiness.', style: TextStyle(color: _muted)),
      const SizedBox(height: 22),
      Wrap(spacing: 12, runSpacing: 12, children: [
        _stat('Task history', '${_tasks.length}', Icons.checklist_rounded, _cyan),
        _stat('Plans waiting', '$planned', Icons.hourglass_top_rounded, const Color(0xFFFFC17B)),
        _stat('Active workers', '$active', Icons.precision_manufacturing_outlined, _violet),
        _stat('Enabled bots', '$enabledBots / ${_bots.length}', Icons.smart_toy_outlined, _cyan),
        _stat('Approved skills', '$approved / ${_skills.length}', Icons.verified_user_outlined, const Color(0xFF85EDC3)),
        _stat('Model routes', '${_routes.length}', Icons.hub_outlined, _violet),
      ]),
      const SizedBox(height: 24),
      _heading('Recent task plans', onTap: () => setState(() => _section = _Section.tasks)),
      if (_tasks.isEmpty) const _Empty(icon: Icons.checklist, title: 'No task history yet', subtitle: 'Create a plan in Tasks.'),
      ..._tasks.take(4).map((t) => _taskCard(t, compact: true)),
      const SizedBox(height: 18),
      _heading('Runtime integrations', onTap: () => setState(() => _section = _Section.connections)),
      ..._integrations.take(5).map(_integrationCard),
      const SizedBox(height: 75),
    ]);
  }

  Widget _tasksView() => ListView(physics: const AlwaysScrollableScrollPhysics(), padding: const EdgeInsets.fromLTRB(24, 24, 24, 100), children: [
    _heading('Task history', onTap: _reload),
    const Text('Planning creates a record. Agent dispatch is a separate guarded operation.', style: TextStyle(color: _muted, fontSize: 12)),
    const SizedBox(height: 14),
    if (_tasks.isEmpty) const _Empty(icon: Icons.playlist_add, title: 'Nothing planned', subtitle: 'Create a task and FRIDAY will prepare a plan using the selected route.'),
    ..._tasks.map((t) => _taskCard(t)),
  ]);

  Widget _taskCard(Map<String, dynamic> task, {bool compact = false}) {
    final status = task['status']?.toString() ?? 'unknown';
    final risk = task['risk']?.toString() ?? 'unknown';
    final canRun = status == 'planned' && task['category'] == 'coding' &&
        !{'high', 'critical'}.contains(risk) && task['approval_required'] != true &&
        (task['bot_id'] == null || task['bot_runtime'] == 'codex_cli');
    final plan = _strings(task['plan']);
    return Card(color: _panel, margin: const EdgeInsets.only(bottom: 10), shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(15), side: const BorderSide(color: _line)), child: Padding(
      padding: const EdgeInsets.all(15),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Container(width: 38, height: 38, decoration: BoxDecoration(color: _cyan.withValues(alpha: .08), borderRadius: BorderRadius.circular(12)), child: const Icon(Icons.task_alt_rounded, color: _cyan)),
          const SizedBox(width: 12),
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text((task['prompt'] ?? 'Untitled task').toString(), maxLines: compact ? 2 : 4, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w700)),
            const SizedBox(height: 7),
            Wrap(spacing: 6, runSpacing: 5, children: [
              _pill(status.toUpperCase()), _pill('RISK · ${risk.toUpperCase()}'),
              _pill((task['category'] ?? 'general').toString().toUpperCase()),
              if (task['bot_name'] != null) _pill('BOT · ${task['bot_name']}'),
            ]),
          ])),
          IconButton(tooltip: 'Open task details', onPressed: () => _showTask(task), icon: const Icon(Icons.open_in_new_rounded)),
        ]),
        if (!compact && plan.isNotEmpty) ...[
          const SizedBox(height: 10),
          ...plan.take(3).map((line) => Padding(padding: const EdgeInsets.only(bottom: 4), child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Icon(Icons.chevron_right_rounded, size: 16, color: _cyan),
            Expanded(child: Text(line, style: const TextStyle(fontSize: 12, color: Color(0xFFD2DCF1)))),
          ]))),
          if (plan.length > 3) Text('+ ${plan.length - 3} more steps', style: const TextStyle(color: _muted, fontSize: 11)),
        ],
        if (canRun) Align(alignment: Alignment.centerRight, child: OutlinedButton.icon(onPressed: _busy ? null : () => _showTask(task), icon: const Icon(Icons.terminal, size: 16), label: const Text('Inspect & dispatch'))),
      ]),
    ));
  }

  Widget _botsView() => ListView(physics: const AlwaysScrollableScrollPhysics(), padding: const EdgeInsets.fromLTRB(24, 24, 24, 100), children: [
    _heading('Bot profiles', onTap: () => _editBot()),
    const Text('Save role instructions, model preference, memory notes and runtime preference for reusable assistants.', style: TextStyle(color: _muted, fontSize: 12)),
    const SizedBox(height: 14),
    if (_bots.isEmpty) const _Empty(icon: Icons.smart_toy_outlined, title: 'No custom bots yet', subtitle: 'Create named assistants for coding, research, IoT or repeatable workflows.'),
    ..._bots.map((bot) => Card(color: _panel, margin: const EdgeInsets.only(bottom: 10), shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(15), side: const BorderSide(color: _line)), child: Padding(
      padding: const EdgeInsets.all(15),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Container(width: 42, height: 42, decoration: BoxDecoration(color: _violet.withValues(alpha: .11), borderRadius: BorderRadius.circular(13)), child: const Icon(Icons.smart_toy_outlined, color: _violet)),
          const SizedBox(width: 12),
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text((bot['name'] ?? 'Unnamed bot').toString(), style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 16)),
            Text((bot['description'] ?? '').toString(), style: const TextStyle(color: _muted, fontSize: 12)),
          ])),
          Switch(value: bot['enabled'] == true, onChanged: _busy ? null : (v) => _setBotEnabled(bot, v)),
          PopupMenuButton<String>(onSelected: (value) {
            if (value == 'edit') unawaited(_editBot(bot));
            if (value == 'delete') unawaited(_deleteBot(bot));
          }, itemBuilder: (context) => const [
            PopupMenuItem(value: 'edit', child: Text('Edit profile')),
            PopupMenuItem(value: 'delete', child: Text('Delete profile')),
          ]),
        ]),
        const SizedBox(height: 10),
        Wrap(spacing: 6, runSpacing: 6, children: [
          _pill('ROUTE · ${bot['default_model_route'] ?? 'auto'}'),
          _pill('RUNTIME · ${bot['runtime'] ?? 'plan_only'}'),
          _pill(bot['enabled'] == true ? 'ENABLED' : 'DISABLED'),
          ..._strings(bot['skill_ids']).map((id) => _pill('SKILL · $id')),
        ]),
        if ((bot['instructions'] ?? '').toString().isNotEmpty) Padding(padding: const EdgeInsets.only(top: 10), child: Text(bot['instructions'].toString(), maxLines: 3, overflow: TextOverflow.ellipsis, style: const TextStyle(color: Color(0xFFD2DCF1), fontSize: 12))),
      ]),
    ))),
  ]);

  Widget _skillsView() => ListView(physics: const AlwaysScrollableScrollPhysics(), padding: const EdgeInsets.fromLTRB(24, 24, 24, 100), children: [
    _heading('Skill library', onTap: _reload),
    Align(alignment: Alignment.centerLeft, child: FilledButton.tonalIcon(onPressed: _busy ? null : _importSkills, icon: const Icon(Icons.upload_file, size: 16), label: const Text('Import skill ZIP'))),
    const SizedBox(height: 10),
    const _Note(text: 'Supported archive names: ECC-main.zip, Desktop2222.zip, teddy-skill-candidates.zip. Imported files are untrusted and stay disabled until you inspect and approve them. Scripts and binaries are not run.'),
    const SizedBox(height: 12),
    if (_skills.isEmpty) const _Empty(icon: Icons.extension_outlined, title: 'No skills imported', subtitle: 'Import a supported skill archive to populate the inventory.'),
    ..._skills.map((skill) {
      final status = skill['status']?.toString() ?? 'unknown';
      final enabled = status == 'enabled_reviewed';
      return Card(color: _panel, margin: const EdgeInsets.only(bottom: 10), shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(15), side: const BorderSide(color: _line)), child: ListTile(
        contentPadding: const EdgeInsets.symmetric(horizontal: 15, vertical: 9),
        leading: CircleAvatar(backgroundColor: enabled ? const Color(0x223AE6A2) : const Color(0x22A99CFF), child: Icon(enabled ? Icons.verified_user : Icons.extension, color: enabled ? const Color(0xFF85EDC3) : _violet)),
        title: Text((skill['name'] ?? 'Unnamed skill').toString(), style: const TextStyle(fontWeight: FontWeight.w700)),
        subtitle: Padding(padding: const EdgeInsets.only(top: 5), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text((skill['description'] ?? '').toString(), maxLines: 3, overflow: TextOverflow.ellipsis),
          const SizedBox(height: 7),
          Wrap(spacing: 5, runSpacing: 5, children: [
            _pill((skill['source'] ?? 'imported').toString()),
            _pill(status.replaceAll('_', ' ').toUpperCase()),
            _pill('HASH · ${skill['content_hash'] ?? 'unknown'}'),
          ]),
          const SizedBox(height: 5),
          Text((skill['path'] ?? '').toString(), style: const TextStyle(color: _muted, fontSize: 10)),
        ])),
        trailing: IconButton(tooltip: 'Read and review skill', onPressed: _busy ? null : () => _reviewSkill(skill), icon: const Icon(Icons.rate_review_outlined, color: _cyan)),
      ));
    }),
  ]);

  Widget _modelsView() => ListView(physics: const AlwaysScrollableScrollPhysics(), padding: const EdgeInsets.all(24), children: [
    _heading('Configured model routes', onTap: _reload),
    const Text('Availability comes from the backend. A provider is not considered ready just because it appears in the list.', style: TextStyle(color: _muted, fontSize: 12)),
    const SizedBox(height: 15),
    if (_routes.isEmpty) const _Empty(icon: Icons.hub_outlined, title: 'No model routes', subtitle: 'Check the backend model registry.'),
    ..._routes.map((route) {
      final ready = route['available'] == true;
      return Card(color: _panel, margin: const EdgeInsets.only(bottom: 9), shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14), side: const BorderSide(color: _line)), child: Padding(
        padding: const EdgeInsets.all(14),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Icon(ready ? Icons.check_circle_outline : Icons.hourglass_empty_rounded, color: ready ? const Color(0xFF85EDC3) : const Color(0xFFFFC17B), size: 25),
          const SizedBox(width: 12),
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text((route['name'] ?? route['id'] ?? 'Unknown route').toString(), style: const TextStyle(fontWeight: FontWeight.w800)),
            const SizedBox(height: 5),
            Text((route['details'] ?? '').toString(), style: const TextStyle(color: _muted, fontSize: 12)),
            if ((route['model'] ?? '').toString().isNotEmpty) Padding(padding: const EdgeInsets.only(top: 7), child: Text('Model: ${route['model']}', style: const TextStyle(color: _cyan, fontSize: 11))),
          ])),
          const SizedBox(width: 7),
          _pill(ready ? 'AVAILABLE' : 'NEEDS SETUP'),
        ]),
      ));
    }),
  ]);

  Widget _connectionsView() => ListView(physics: const AlwaysScrollableScrollPhysics(), padding: const EdgeInsets.all(24), children: [
    _heading('Service connections', onTap: _reload),
    const Text('Readiness metadata only. Credentials are not displayed and this panel does not claim an integration works without backend evidence.', style: TextStyle(color: _muted, fontSize: 12)),
    const SizedBox(height: 15),
    if (_integrations.isEmpty) const _Empty(icon: Icons.cable_outlined, title: 'No integrations returned', subtitle: 'The backend registry did not return any entries.'),
    ..._integrations.map(_integrationCard),
  ]);

  Widget _integrationCard(Map<String, dynamic> item) {
    final status = item['status']?.toString() ?? 'unknown';
    final ready = {'available', 'reachable_models_detected', 'configured_not_tested', 'installed_needs_verification'}.contains(status);
    return Card(color: _panel, margin: const EdgeInsets.only(bottom: 9), shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14), side: const BorderSide(color: _line)), child: Padding(
      padding: const EdgeInsets.all(14),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Container(width: 40, height: 40, decoration: BoxDecoration(color: (ready ? const Color(0xFF85EDC3) : _violet).withValues(alpha: .12), borderRadius: BorderRadius.circular(12)), child: Icon(Icons.cable_outlined, color: ready ? const Color(0xFF85EDC3) : _violet)),
        const SizedBox(width: 12),
        Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text((item['name'] ?? item['id'] ?? 'Integration').toString(), style: const TextStyle(fontWeight: FontWeight.w800)),
          const SizedBox(height: 4),
          Text((item['purpose'] ?? '').toString(), style: const TextStyle(color: Color(0xFFD2DCF1), fontSize: 12)),
          if ((item['details'] ?? '').toString().isNotEmpty) Padding(padding: const EdgeInsets.only(top: 7), child: Text(item['details'].toString(), style: const TextStyle(color: _muted, fontSize: 11))),
        ])),
        const SizedBox(width: 7),
        _pill(status.replaceAll('_', ' ').toUpperCase()),
      ]),
    ));
  }

  Widget _heading(String title, {VoidCallback? onTap}) => Padding(
    padding: const EdgeInsets.only(bottom: 10),
    child: Row(children: [
      Expanded(child: Text(title, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800))),
      if (onTap != null) TextButton.icon(onPressed: onTap, icon: Icon(title == 'Bot profiles' ? Icons.add : Icons.refresh, size: 16), label: Text(title == 'Bot profiles' ? 'Add bot' : 'Refresh')),
    ]),
  );

  Widget _stat(String title, String value, IconData icon, Color color) => Container(
    width: 185,
    padding: const EdgeInsets.all(17),
    decoration: BoxDecoration(color: _panel, border: Border.all(color: _line), borderRadius: BorderRadius.circular(16)),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Icon(icon, color: color, size: 21),
      const SizedBox(height: 15),
      Text(value, style: const TextStyle(fontSize: 25, fontWeight: FontWeight.w900)),
      const SizedBox(height: 3),
      Text(title, style: const TextStyle(color: _muted, fontSize: 11)),
    ]),
  );

  Widget _pill(String text) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
    decoration: BoxDecoration(color: const Color(0xFF1A2640), border: Border.all(color: _line), borderRadius: BorderRadius.circular(20)),
    child: Text(text, style: const TextStyle(fontSize: 9, color: Color(0xFFD8E4FB), letterSpacing: .25)),
  );
}

class _Empty extends StatelessWidget {
  const _Empty({required this.icon, required this.title, required this.subtitle});
  final IconData icon;
  final String title;
  final String subtitle;
  @override
  Widget build(BuildContext context) => Padding(padding: const EdgeInsets.symmetric(vertical: 30, horizontal: 18), child: Column(children: [
    Icon(icon, size: 38, color: _muted),
    const SizedBox(height: 12),
    Text(title, style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 16)),
    const SizedBox(height: 6),
    Text(subtitle, textAlign: TextAlign.center, style: const TextStyle(color: _muted, fontSize: 12)),
  ]));
}

class _Note extends StatelessWidget {
  const _Note({required this.text});
  final String text;
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(13),
    decoration: BoxDecoration(color: const Color(0x22FFC17B), border: Border.all(color: const Color(0x55FFC17B)), borderRadius: BorderRadius.circular(12)),
    child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const Icon(Icons.info_outline, color: Color(0xFFFFC17B), size: 18),
      const SizedBox(width: 9),
      Expanded(child: Text(text, style: const TextStyle(fontSize: 11, color: Color(0xFFECE0C9), height: 1.4))),
    ]),
  );
}
