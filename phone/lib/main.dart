import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:webview_flutter/webview_flutter.dart';

const kTitle = 'Aether Desk';
const kDefaultPort = 8791;
const kPaper = 'PAPER TRADING ONLY — read-only blotter, no live orders.';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const DeskPhoneApp());
}

class DeskPhoneApp extends StatelessWidget {
  const DeskPhoneApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: kTitle,
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        colorScheme: const ColorScheme.dark(
          primary: Color(0xFFD4A24A),
          surface: Color(0xFF12141A),
        ),
        scaffoldBackgroundColor: const Color(0xFF12141A),
      ),
      home: const DeskHome(),
    );
  }
}

class DeskHome extends StatefulWidget {
  const DeskHome({super.key});

  @override
  State<DeskHome> createState() => _DeskHomeState();
}

class _DeskHomeState extends State<DeskHome> {
  String host = '';
  String token = '';
  int port = kDefaultPort;
  bool ready = false;
  bool showSettings = false;
  WebViewController? web;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final prefs = await SharedPreferences.getInstance();
    var h = prefs.getString('host') ?? '';
    var t = prefs.getString('token') ?? '';
    var p = prefs.getInt('port') ?? kDefaultPort;
    if (h.isEmpty) {
      try {
        final raw = await rootBundle.loadString('assets/bootstrap.json');
        final j = jsonDecode(raw) as Map<String, dynamic>;
        h = (j['host'] as String?) ?? '';
        t = (j['token'] as String?) ?? t;
        p = (j['port'] as num?)?.toInt() ?? p;
      } catch (_) {}
    }
    setState(() {
      host = h;
      token = t;
      port = p;
      ready = true;
      showSettings = h.isEmpty;
    });
    if (h.isNotEmpty) _open();
  }

  String get url {
    final q = token.isEmpty ? '' : '?k=${Uri.encodeQueryComponent(token)}';
    return 'http://$host:$port/$q';
  }

  void _open() {
    final c = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(const Color(0xFF12141A))
      ..loadRequest(Uri.parse(url));
    setState(() => web = c);
  }

  Future<void> _save() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('host', host.trim());
    await prefs.setString('token', token.trim());
    await prefs.setInt('port', port);
    setState(() {
      showSettings = false;
    });
    _open();
  }

  @override
  Widget build(BuildContext context) {
    if (!ready) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    return Scaffold(
      appBar: AppBar(
        title: const Text(kTitle),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings),
            onPressed: () => setState(() => showSettings = !showSettings),
          ),
          if (web != null)
            IconButton(
              icon: const Icon(Icons.refresh),
              onPressed: () => web!.reload(),
            ),
        ],
      ),
      body: Column(
        children: [
          const Material(
            color: Color(0xFF5A1F1F),
            child: SizedBox(
              width: double.infinity,
              child: Padding(
                padding: EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                child: Text(kPaper, style: TextStyle(fontWeight: FontWeight.w700, fontSize: 12)),
              ),
            ),
          ),
          if (showSettings) _settings(),
          Expanded(
            child: web == null
                ? const Center(child: Text('Set the PC address (Wi-Fi or Tailscale) and open.'))
                : WebViewWidget(controller: web!),
          ),
        ],
      ),
    );
  }

  Widget _settings() {
    return Material(
      color: const Color(0xFF1B1F29),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TextField(
              controller: TextEditingController(text: host),
              decoration: const InputDecoration(
                labelText: 'PC address (LAN IP or Tailscale name)',
                hintText: '192.168.7.252',
              ),
              onChanged: (v) => host = v,
            ),
            TextField(
              controller: TextEditingController(text: '$port'),
              decoration: const InputDecoration(labelText: 'Port'),
              keyboardType: TextInputType.number,
              onChanged: (v) => port = int.tryParse(v) ?? kDefaultPort,
            ),
            TextField(
              controller: TextEditingController(text: token),
              decoration: const InputDecoration(labelText: 'Phone token (from PC ledger/state file)'),
              obscureText: true,
              onChanged: (v) => token = v,
            ),
            const SizedBox(height: 8),
            FilledButton(onPressed: _save, child: const Text('Save and open blotter')),
          ],
        ),
      ),
    );
  }
}
