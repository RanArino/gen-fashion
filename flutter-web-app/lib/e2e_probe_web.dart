// ignore_for_file: avoid_web_libraries_in_flutter, deprecated_member_use

import 'dart:convert';
import 'dart:html' as html;

void reportM5E2eState(Map<String, Object?> state) {
  final encoded = jsonEncode(state);
  html.window.localStorage['m5_e2e_state'] = encoded;
  final status = state['status'] ?? 'UNKNOWN';
  html.document.title = 'M5_E2E:$status';
}
