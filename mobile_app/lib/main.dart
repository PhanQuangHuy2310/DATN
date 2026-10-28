import 'package:flutter/material.dart';
import 'eas_api.dart';

const server = String.fromEnvironment('EAS_API_BASE_URL', defaultValue: 'http://10.0.2.2:8000');
void main() => runApp(const EasApplication());

class EasApplication extends StatefulWidget {
  const EasApplication({super.key});
  @override
  State<EasApplication> createState() => _EasApplicationState();
}

class _EasApplicationState extends State<EasApplication> {
  late final EasApi api = EasApi(server);
  Map<String, dynamic>? user;
  @override
  void dispose() { api.close(); super.dispose(); }
  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'EAS Mobile', debugShowCheckedModeBanner: false,
        theme: ThemeData(colorSchemeSeed: const Color(0xff2563eb), useMaterial3: true),
        home: user == null ? LoginPage(api: api, onLogin: (v) => setState(() => user = v)) :
          user!['must_change_password'] == true
            ? PasswordPage(api: api, onChanged: (v) => setState(() => user = v))
            : HomePage(api: api, user: user!, onLogout: () => setState(() => user = null)),
      );
}

class LoginPage extends StatefulWidget {
  const LoginPage({super.key, required this.api, required this.onLogin});
  final EasApi api;
  final ValueChanged<Map<String, dynamic>> onLogin;
  @override State<LoginPage> createState() => _LoginPageState();
}
class _LoginPageState extends State<LoginPage> {
  final username = TextEditingController(), password = TextEditingController();
  bool busy = false, obscure = true;
  String? error;
  @override void dispose() { username.dispose(); password.dispose(); super.dispose(); }
  Future<void> submit() async {
    setState(() { busy = true; error = null; });
    try { widget.onLogin(await widget.api.login(username.text, password.text)); }
    catch (e) { if (mounted) setState(() => error = e.toString()); }
    finally { if (mounted) setState(() => busy = false); }
  }
  @override Widget build(BuildContext context) => Scaffold(
    body: SafeArea(child: Center(child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 440),
      child: Padding(padding: const EdgeInsets.all(24), child: AutofillGroup(child: Column(
        mainAxisAlignment: MainAxisAlignment.center, crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Icon(Icons.fact_check_outlined, size: 64),
          const SizedBox(height: 12),
          const Text('Enterprise Approval System', textAlign: TextAlign.center, style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold)),
          const SizedBox(height: 32),
          TextField(controller: username, decoration: const InputDecoration(labelText: 'Tên đăng nhập', border: OutlineInputBorder()),
            autofillHints: const [AutofillHints.username]),
          const SizedBox(height: 12),
          TextField(controller: password, obscureText: obscure, onSubmitted: (_) => submit(),
            autofillHints: const [AutofillHints.password],
            decoration: InputDecoration(labelText: 'Mật khẩu', border: const OutlineInputBorder(),
              suffixIcon: IconButton(icon: Icon(obscure ? Icons.visibility : Icons.visibility_off),
                onPressed: () => setState(() => obscure = !obscure)))),
          const SizedBox(height: 12),
          if (error != null) Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
          FilledButton(onPressed: busy ? null : submit, child: Text(busy ? 'Đang đăng nhập…' : 'Đăng nhập')),
        ],
      )))))))
  );
}

class PasswordPage extends StatefulWidget {
  const PasswordPage({super.key, required this.api, required this.onChanged});
  final EasApi api;
  final ValueChanged<Map<String, dynamic>> onChanged;
  @override State<PasswordPage> createState() => _PasswordPageState();
}
class _PasswordPageState extends State<PasswordPage> {
  final oldPassword = TextEditingController(), newPassword = TextEditingController();
  String? error;
  bool saving = false;
  @override void dispose() { oldPassword.dispose(); newPassword.dispose(); super.dispose(); }
  Future<void> save() async {
    setState(() { saving = true; error = null; });
    try {
      await widget.api.changePassword(oldPassword.text, newPassword.text);
      widget.onChanged(await widget.api.me());
    } catch (e) { if (mounted) setState(() => error = e.toString()); }
    finally { if (mounted) setState(() => saving = false); }
  }
  @override Widget build(BuildContext context) => Scaffold(appBar: AppBar(title: const Text('Đổi mật khẩu bắt buộc')),
    body: ListView(padding: const EdgeInsets.all(18), children: [
      const Text('Mật khẩu mới: 15–128 ký tự, chữ hoa, chữ thường, số và ký tự đặc biệt.'),
      TextField(controller: oldPassword, obscureText: true, decoration: const InputDecoration(labelText: 'Mật khẩu hiện tại')),
      TextField(controller: newPassword, obscureText: true, decoration: const InputDecoration(labelText: 'Mật khẩu mới')),
      if (error != null) Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
      FilledButton(onPressed: saving ? null : save, child: const Text('Đổi mật khẩu')),
    ]));
}

class HomePage extends StatefulWidget {
  const HomePage({super.key, required this.api, required this.user, required this.onLogout});
  final EasApi api;
  final Map<String, dynamic> user;
  final VoidCallback onLogout;
  @override State<HomePage> createState() => _HomePageState();
}
class _HomePageState extends State<HomePage> {
  int selected = 0;
  int refresh = 0;
  @override Widget build(BuildContext context) {
    final roles = (widget.user['roles'] as List<dynamic>? ?? []).map((e) => '$e').toSet();
    final menus = <(String, String, IconData)>[
      ('mine', 'Của tôi', Icons.assignment_outlined),
      if (roles.contains('APPROVER')) ('approval', 'Cần duyệt', Icons.how_to_reg_outlined),
      if (roles.contains('EXECUTOR')) ('execution', 'Thực hiện', Icons.build_circle_outlined),
      if (roles.contains('ACCEPTOR')) ('acceptance', 'Nghiệm thu', Icons.check_circle_outline),
      ('notifications', 'Thông báo', Icons.notifications_outlined),
    ];
    if (selected >= menus.length) selected = 0;
    final current = menus[selected];
    return Scaffold(
      appBar: AppBar(title: Text(current.$2), actions: [
        IconButton(tooltip: 'Tải lại', onPressed: () => setState(() => refresh++), icon: const Icon(Icons.refresh)),
        IconButton(tooltip: 'Đăng xuất', onPressed: () async {
          try { await widget.api.logout(); } finally { widget.onLogout(); }
        }, icon: const Icon(Icons.logout)),
      ]),
      body: current.$1 == 'notifications'
        ? NotificationsPage(key: ValueKey('notifications:$refresh'), api: widget.api, user: widget.user)
        : WorklistPage(key: ValueKey('${current.$1}:$refresh'), api: widget.api,
          user: widget.user, tab: current.$1),
      bottomNavigationBar: NavigationBar(selectedIndex: selected,
        onDestinationSelected: (index) => setState(() => selected = index),
        destinations: [for (final menu in menus) NavigationDestination(icon: Icon(menu.$3), label: menu.$2)]),
    );
  }
}

class WorklistPage extends StatefulWidget {
  const WorklistPage({super.key, required this.api, required this.user, required this.tab});
  final EasApi api;
  final Map<String, dynamic> user;
  final String tab;
  @override State<WorklistPage> createState() => _WorklistPageState();
}
class _WorklistPageState extends State<WorklistPage> {
  late Future<List<dynamic>> items = widget.api.worklist(widget.tab);
  Future<void> refresh() async => setState(() => items = widget.api.worklist(widget.tab));
  @override Widget build(BuildContext context) => RefreshIndicator(onRefresh: refresh,
      child: FutureBuilder<List<dynamic>>(future: items, builder: (context, snapshot) {
        if (snapshot.hasError) return ListView(children: [ListTile(title: Text('${snapshot.error}'),
          trailing: TextButton(onPressed: refresh, child: const Text('Thử lại')))]);
        if (!snapshot.hasData) return const Center(child: CircularProgressIndicator());
        final rows = snapshot.data!;
        if (rows.isEmpty) return ListView(children: const [ListTile(title: Text('Chưa có hồ sơ thuộc nhóm này.'))]);
        return ListView.builder(itemCount: rows.length, itemBuilder: (context, index) {
          final row = rows[index] as Map<String, dynamic>;
          return ListTile(
            title: Text('${row['code'] ?? 'Hồ sơ'}'),
            subtitle: Text('${row['type_code']} · ${row['status']}'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () async {
              await Navigator.of(context).push(MaterialPageRoute<void>(builder: (context) =>
                DetailPage(api: widget.api, user: widget.user, id: '${row['id']}')));
              if (mounted) refresh();
            },
          );
        });
      }));
}

class DetailPage extends StatefulWidget {
  const DetailPage({super.key, required this.api, required this.user, required this.id});
  final EasApi api;
  final Map<String, dynamic> user;
  final String id;
  @override State<DetailPage> createState() => _DetailPageState();
}
class _DetailPageState extends State<DetailPage> {
  late Future<Map<String, dynamic>> request = widget.api.detail(widget.id);
  bool busy = false;
  String? error;
  Future<void> reload() async => setState(() => request = widget.api.detail(widget.id));

  Future<void> act(Map<String, dynamic> record, String action) async {
    final mustReason = {'REJECT', 'NEEDS_INFO', 'REWORK', 'CANCEL', 'UNABLE_TO_CLAIM', 'BLOCKED'}.contains(action);
    final controller = TextEditingController();
    final confirmation = await showDialog<bool>(context: context, builder: (context) => AlertDialog(
      title: Text('Xác nhận $action'),
      content: mustReason ? TextField(controller: controller, maxLines: 3, maxLength: 2000,
        decoration: const InputDecoration(labelText: 'Lý do (10–2000 ký tự)', border: OutlineInputBorder()))
        : const Text('Thao tác sẽ được ghi nhận và không thể hoàn tác.'),
      actions: [TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Đóng')),
        FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Xác nhận'))],
    ));
    final reason = controller.text.trim();
    controller.dispose();
    if (confirmation != true || (mustReason && (reason.length < 10 || reason.length > 2000))) {
      if (confirmation == true && mounted) setState(() => error = 'Lý do phải có 10–2000 ký tự.');
      return;
    }
    setState(() { busy = true; error = null; });
    try { await widget.api.requestAction(record, action, reason); await reload(); }
    catch (e) { if (mounted) setState(() => error = e.toString()); }
    finally { if (mounted) setState(() => busy = false); }
  }

  @override Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Chi tiết hồ sơ'), actions: [
      IconButton(onPressed: reload, icon: const Icon(Icons.refresh), tooltip: 'Tải lại'),
    ]),
    body: FutureBuilder<Map<String, dynamic>>(future: request, builder: (context, snapshot) {
      if (snapshot.hasError) return Center(child: Text('${snapshot.error}'));
      if (!snapshot.hasData) return const Center(child: CircularProgressIndicator());
      final record = snapshot.data!;
      final payload = record['payload'] is Map ? record['payload'] as Map : {};
      final roles = (widget.user['roles'] as List<dynamic>? ?? []).toSet();
      final own = record['requester_id'] == widget.user['id'];
      final steps = (record['approval_steps'] as List<dynamic>? ?? []);
      final active = steps.where((step) => step['state'] == 'ACTIVE').toList();
      final workflow = record['workflow'] as Map<String, dynamic>?;
      final attempt = workflow?['attempt'] as Map<String, dynamic>?;
      final status = record['status'];
      final approve = roles.contains('APPROVER') && !own && status == 'PENDING_APPROVAL' &&
        active.any((step) => step['assignee_id'] == widget.user['id']);
      final earlierApprover = steps.any((step) => step['assignee_id'] == widget.user['id']);
      final execute = roles.contains('EXECUTOR') && !own && !earlierApprover &&
        attempt?['executor_id'] == widget.user['id'];
      final accept = roles.contains('ACCEPTOR') && status == 'WAITING_FOR_ACCEPTANCE' &&
        workflow?['lifecycle'] == 'C' && workflow?['acceptor_id'] == widget.user['id'] &&
        attempt?['executor_id'] != widget.user['id'] && attempt?['state'] == 'SUBMITTED';
      final actions = <(String, String)>[
        if (approve) ...[
          ('APPROVE','Phê duyệt'), ('NEEDS_INFO','Yêu cầu bổ sung'), ('REJECT','Từ chối'),
        ],
        if (execute && status == 'READY_FOR_EXECUTION' && attempt?['state'] == 'READY') ...[
          ('CLAIM', 'Tiếp nhận'), ('UNABLE_TO_CLAIM', 'Không thể nhận việc'),
        ],
        if (execute && status == 'IN_PROGRESS' && attempt?['state'] == 'RUNNING')
          ('BLOCKED', 'Báo vướng mắc'),
        if (accept) ...[('ACCEPT','Nghiệm thu đạt'),('REWORK','Yêu cầu làm lại')],
        if (own && roles.contains('REQUESTER') &&
          ['DRAFT','NEEDS_INFO','PENDING_APPROVAL'].contains(status)) ('CANCEL','Rút hồ sơ'),
      ];
      return ListView(padding: const EdgeInsets.all(16), children: [
        Text('${record['code']}', style: Theme.of(context).textTheme.titleLarge),
        Text('${record['type_code']} · ${record['status']}', style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 18),
        ...payload.entries.map((entry) => ListTile(dense: true,
          title: Text('${entry.key}'), subtitle: Text('${entry.value}'))),
        const Divider(),
        const Text('Tiến trình duyệt', style: TextStyle(fontWeight: FontWeight.bold)),
        for (final step in steps) ListTile(dense: true,
          title: Text('Cấp ${step['step_no']} · ${step['state']}'),
          subtitle: Text('Người được gán: ${step['assignee_id']}')),
        if (attempt != null) ListTile(title: Text('Thực hiện #${attempt['attempt_no']}'),
          subtitle: Text('${attempt['state']} · ${attempt['result_note'] ?? 'Chưa có kết quả'}')),
        if (error != null) Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
        for (final action in actions) Padding(padding: const EdgeInsets.only(bottom: 8),
          child: OutlinedButton(onPressed: busy ? null : () => act(record, action.$1), child: Text(action.$2))),
        if (actions.isEmpty) const Text('Chỉ có quyền xem trong trạng thái hiện tại.'),
      ]);
    }),
  );
}

class NotificationsPage extends StatefulWidget {
  const NotificationsPage({super.key, required this.api, required this.user});
  final EasApi api;
  final Map<String, dynamic> user;
  @override State<NotificationsPage> createState() => _NotificationsPageState();
}
class _NotificationsPageState extends State<NotificationsPage> {
  late Future<Map<String, dynamic>> notifications = widget.api.notifications();
  Future<void> refresh() async => setState(() => notifications = widget.api.notifications());
  @override Widget build(BuildContext context) => RefreshIndicator(onRefresh: refresh,
    child: FutureBuilder<Map<String, dynamic>>(future: notifications, builder: (context, snapshot) {
      if (snapshot.hasError) return ListView(children: [ListTile(title: Text('${snapshot.error}'))]);
      if (!snapshot.hasData) return const Center(child: CircularProgressIndicator());
      final rows = snapshot.data!['items'] as List<dynamic>? ?? [];
      if (rows.isEmpty) return ListView(children: const [ListTile(title: Text('Chưa có thông báo.'))]);
      return ListView.builder(itemCount: rows.length, itemBuilder: (context, i) {
        final item = rows[i] as Map<String, dynamic>;
        return ListTile(title: Text('${item['label']}'),
          subtitle: Text('${item['created_at']}'),
          leading: Icon(item['read_at'] == null ? Icons.notifications_active : Icons.notifications_none),
          onTap: () async {
            try { await widget.api.markRead('${item['id']}');
              if (context.mounted && item['request_id'] != null) {
                await Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) =>
                  DetailPage(api: widget.api, user: widget.user, id: '${item['request_id']}')));
              }
              await refresh();
            } catch (e) { if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e'))); }
          });
      });
    }));
}
