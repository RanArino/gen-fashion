import 'package:flutter/material.dart';

import '../api/api_client.dart';
import '../config.dart';
import '../e2e_probe_stub.dart' if (dart.library.html) '../e2e_probe_web.dart';
import '../shared/attribution.dart';

const List<String> _sharedClosets = ['adult-01', 'adult-02', 'child-01'];

class CoordinationScreen extends StatefulWidget {
  const CoordinationScreen({super.key, required this.uid, ApiClient? api})
      : _api = api;

  final String uid;
  final ApiClient? _api;

  @override
  State<CoordinationScreen> createState() => _CoordinationScreenState();
}

class _CoordinationScreenState extends State<CoordinationScreen> {
  late final ApiClient _api = widget._api ?? ApiClient();
  final _occasion = TextEditingController(text: 'casual weekend');
  final _style = TextEditingController(text: 'clean casual');
  final _season = TextEditingController(text: 'spring');
  final _color = TextEditingController(text: 'blue and white');
  final List<AgentEvent> _events = [];
  final List<Map<String, dynamic>> _candidates = [];
  final Set<String> _selectedCandidateIds = {};
  String _source = 'SHARED_CLOSET';
  String _sharedClosetId = _sharedClosets.first;
  String _gender = 'common';
  String? _sessionId;
  String? _status;
  String? _coordinateImageUrl;
  bool _running = false;
  Object? _error;
  bool _autoRunStarted = false;

  @override
  void initState() {
    super.initState();
    if (AppConfig.e2eAutoRun) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && !_autoRunStarted) {
          _autoRunStarted = true;
          _start();
        }
      });
    }
  }

  @override
  void dispose() {
    _occasion.dispose();
    _style.dispose();
    _season.dispose();
    _color.dispose();
    super.dispose();
  }

  Future<void> _start() async {
    if (_running) return;
    setState(() {
      _running = true;
      _error = null;
      _events.clear();
      _candidates.clear();
      _selectedCandidateIds.clear();
      _coordinateImageUrl = null;
    });
    try {
      final created = await _api.createSession();
      final selected = await _api.selectSource(
        sessionId: created.sessionId,
        source: _source,
        sharedClosetId: _source == 'SHARED_CLOSET' ? _sharedClosetId : null,
        userPreference: {
          'occasion': _occasion.text,
          'style': _style.text,
          'season': _season.text,
          'colorPreference': _color.text,
          'gender': _gender,
        },
      );
      setState(() {
        _sessionId = selected.sessionId;
        _status = selected.status;
      });
      await for (final message
          in _api.streamSessionEvents(selected.sessionId)) {
        if (!mounted) return;
        setState(() {
          if (message.event == 'agent.event') {
            final event = AgentEvent.fromJson(message.data);
            _events.add(event);
            final result = event.toolResult;
            final imageUrl = result?['coordinateImageUrl'] ??
                result?['coordinate_image_url'];
            if (imageUrl is String && imageUrl.isNotEmpty) {
              _coordinateImageUrl = imageUrl;
            }
          } else if (message.event == 'session.proposed') {
            _status = 'PROPOSING';
            _candidates
              ..clear()
              ..addAll(
                (message.data['candidates'] as List? ?? const [])
                    .map((item) => (item as Map).cast<String, dynamic>()),
              );
            if (_candidates.isNotEmpty) {
              _selectedCandidateIds.add(_candidateId(_candidates.first));
            }
          } else if (message.event == 'session.snapshot' ||
              message.event == 'session.completed' ||
              message.event == 'session.error') {
            _status = message.data['status'] as String?;
          }
          _reportE2eState();
        });
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e;
        _reportE2eState();
      });
    } finally {
      if (mounted) {
        setState(() {
          _running = false;
          _reportE2eState();
        });
      }
    }
    if (mounted &&
        AppConfig.e2eAutoRun &&
        _candidates.isNotEmpty &&
        _coordinateImageUrl == null) {
      await _generateSelected();
    }
  }

  Future<void> _generateSelected() async {
    final sessionId = _sessionId;
    if (_running || sessionId == null || _selectedCandidateIds.isEmpty) return;
    setState(() {
      _running = true;
      _error = null;
    });
    try {
      await _api.selectCandidates(
        sessionId: sessionId,
        selectedItemIds: _selectedCandidateIds.toList(),
      );
      await for (final message in _api.streamSessionEvents(sessionId)) {
        if (!mounted) return;
        setState(() {
          if (message.event == 'agent.event') {
            final event = AgentEvent.fromJson(message.data);
            _events.add(event);
            final result = event.toolResult;
            final imageUrl = result?['coordinateImageUrl'] ??
                result?['coordinate_image_url'];
            if (imageUrl is String && imageUrl.isNotEmpty) {
              _coordinateImageUrl = imageUrl;
            }
          } else if (message.event.startsWith('session.')) {
            _status = message.data['status'] as String?;
          }
          _reportE2eState();
        });
      }
    } catch (e) {
      if (mounted) setState(() => _error = e);
    } finally {
      if (mounted) setState(() => _running = false);
    }
  }

  String _candidateId(Map<String, dynamic> candidate) =>
      (candidate['item_id'] ?? candidate['itemId']) as String;

  void _reportE2eState() {
    if (!AppConfig.e2eAutoRun) return;
    final eventKinds = _events.map((event) => event.eventKind).toSet();
    final toolNames =
        _events.map((event) => event.toolName).whereType<String>().toSet();
    reportM5E2eState({
      'sessionId': _sessionId,
      'status': _status,
      'running': _running,
      'eventCount': _events.length,
      'eventKinds': eventKinds.toList(),
      'toolNames': toolNames.toList(),
      'hasResult': _coordinateImageUrl != null,
      'error': _error?.toString(),
    });
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final wide = constraints.maxWidth >= 900;
        final controls = _Controls(
          source: _source,
          sharedClosetId: _sharedClosetId,
          running: _running,
          occasion: _occasion,
          style: _style,
          season: _season,
          color: _color,
          gender: _gender,
          onSourceChanged: (value) => setState(() => _source = value),
          onSharedClosetChanged: (value) =>
              setState(() => _sharedClosetId = value),
          onGenderChanged: (value) => setState(() => _gender = value),
          onStart: _start,
        );
        final trace = _TracePanel(
          sessionId: _sessionId,
          status: _status,
          events: _events,
          running: _running,
          error: _error,
        );
        final result = _ResultPanel(
          source: _source,
          coordinateImageUrl: _coordinateImageUrl,
        );
        final candidates = _CandidatePanel(
          candidates: _candidates,
          selectedIds: _selectedCandidateIds,
          running: _running,
          onChanged: (id, selected) => setState(() {
            selected
                ? _selectedCandidateIds.add(id)
                : _selectedCandidateIds.remove(id);
          }),
          onGenerate: _generateSelected,
        );
        return SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 1180),
              child: wide
                  ? Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        SizedBox(width: 360, child: controls),
                        const SizedBox(width: 16),
                        Expanded(
                          child: Column(
                            children: [
                              trace,
                              const SizedBox(height: 16),
                              if (_candidates.isNotEmpty) ...[
                                candidates,
                                const SizedBox(height: 16),
                              ],
                              result,
                            ],
                          ),
                        ),
                      ],
                    )
                  : Column(
                      children: [
                        controls,
                        const SizedBox(height: 16),
                        trace,
                        const SizedBox(height: 16),
                        if (_candidates.isNotEmpty) ...[
                          candidates,
                          const SizedBox(height: 16),
                        ],
                        result,
                      ],
                    ),
            ),
          ),
        );
      },
    );
  }
}

class _Controls extends StatelessWidget {
  const _Controls({
    required this.source,
    required this.sharedClosetId,
    required this.running,
    required this.occasion,
    required this.style,
    required this.season,
    required this.color,
    required this.gender,
    required this.onSourceChanged,
    required this.onSharedClosetChanged,
    required this.onGenderChanged,
    required this.onStart,
  });

  final String source;
  final String sharedClosetId;
  final bool running;
  final TextEditingController occasion;
  final TextEditingController style;
  final TextEditingController season;
  final TextEditingController color;
  final String gender;
  final ValueChanged<String> onSourceChanged;
  final ValueChanged<String> onSharedClosetChanged;
  final ValueChanged<String> onGenderChanged;
  final VoidCallback onStart;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Coordination', style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 16),
            SegmentedButton<String>(
              segments: const [
                ButtonSegment(
                  value: 'SHARED_CLOSET',
                  icon: Icon(Icons.groups_outlined),
                  label: Text('Shared'),
                ),
                ButtonSegment(
                  value: 'CLOSET',
                  icon: Icon(Icons.checkroom_outlined),
                  label: Text('Mine'),
                ),
              ],
              selected: {source},
              onSelectionChanged:
                  running ? null : (values) => onSourceChanged(values.first),
            ),
            if (source == 'SHARED_CLOSET') ...[
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                initialValue: sharedClosetId,
                decoration: const InputDecoration(
                  labelText: 'Shared closet',
                  border: OutlineInputBorder(),
                ),
                items: _sharedClosets
                    .map((id) => DropdownMenuItem(value: id, child: Text(id)))
                    .toList(),
                onChanged: running || source != 'SHARED_CLOSET'
                    ? null
                    : (value) {
                        if (value != null) onSharedClosetChanged(value);
                      },
              ),
            ],
            const SizedBox(height: 12),
            _TextField(controller: occasion, label: 'Occasion'),
            _TextField(controller: style, label: 'Style'),
            _TextField(controller: season, label: 'Season'),
            _TextField(controller: color, label: 'Colors'),
            DropdownButtonFormField<String>(
              initialValue: gender,
              decoration: const InputDecoration(
                labelText: 'Gender',
                border: OutlineInputBorder(),
              ),
              items: const [
                DropdownMenuItem(value: 'common', child: Text('Common')),
                DropdownMenuItem(value: 'female', child: Text('Female')),
                DropdownMenuItem(value: 'male', child: Text('Male')),
              ],
              onChanged: running
                  ? null
                  : (value) {
                      if (value != null) onGenderChanged(value);
                    },
            ),
            const SizedBox(height: 8),
            FilledButton.icon(
              onPressed: running ? null : onStart,
              icon: running
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.play_arrow),
              label: Text(running ? 'Running' : 'Start'),
            ),
          ],
        ),
      ),
    );
  }
}

class _TextField extends StatelessWidget {
  const _TextField({required this.controller, required this.label});

  final TextEditingController controller;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: TextField(
        controller: controller,
        decoration: InputDecoration(
          labelText: label,
          border: const OutlineInputBorder(),
        ),
      ),
    );
  }
}

class _TracePanel extends StatelessWidget {
  const _TracePanel({
    required this.sessionId,
    required this.status,
    required this.events,
    required this.running,
    required this.error,
  });

  final String? sessionId;
  final String? status;
  final List<AgentEvent> events;
  final bool running;
  final Object? error;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    'Agent trace',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                ),
                if (status != null) Chip(label: Text(status!)),
              ],
            ),
            if (sessionId != null)
              Text(
                sessionId!,
                style: Theme.of(context).textTheme.bodySmall,
                overflow: TextOverflow.ellipsis,
              ),
            const SizedBox(height: 12),
            if (error != null)
              Text('Error: $error', style: const TextStyle(color: Colors.red))
            else if (events.isEmpty)
              SizedBox(
                height: 160,
                child: Center(
                  child: running
                      ? const CircularProgressIndicator()
                      : const Text('No session events yet.'),
                ),
              )
            else
              ...events.map((event) => AgentEventTile(event: event)),
          ],
        ),
      ),
    );
  }
}

class AgentEventTile extends StatelessWidget {
  const AgentEventTile({super.key, required this.event});

  final AgentEvent event;

  @override
  Widget build(BuildContext context) {
    final title = event.summary;
    return ExpansionTile(
      tilePadding: EdgeInsets.zero,
      leading: Icon(_iconFor(event.eventKind)),
      title: Text(title, overflow: TextOverflow.ellipsis),
      subtitle: event.text == null
          ? null
          : Text(event.text!, maxLines: 1, overflow: TextOverflow.ellipsis),
      children: [
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(12),
          color: Theme.of(context).colorScheme.surfaceContainerHighest,
          child: SelectableText(event.detailText),
        ),
      ],
    );
  }

  IconData _iconFor(String kind) {
    return switch (kind) {
      'tool_call' => Icons.call_made,
      'tool_result' => Icons.call_received,
      'final_answer' => Icons.flag_outlined,
      'thinking' => Icons.psychology_outlined,
      _ => Icons.notes_outlined,
    };
  }
}

class _CandidatePanel extends StatelessWidget {
  const _CandidatePanel({
    required this.candidates,
    required this.selectedIds,
    required this.running,
    required this.onChanged,
    required this.onGenerate,
  });

  final List<Map<String, dynamic>> candidates;
  final Set<String> selectedIds;
  final bool running;
  final void Function(String id, bool selected) onChanged;
  final VoidCallback onGenerate;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Choose items', style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 12),
            Wrap(
              spacing: 12,
              runSpacing: 12,
              children: [
                for (var index = 0; index < candidates.length; index++)
                  _CandidateCard(
                    candidate: candidates[index],
                    recommended: index == 0,
                    selected: selectedIds.contains(_id(candidates[index])),
                    onChanged: (selected) =>
                        onChanged(_id(candidates[index]), selected),
                  ),
              ],
            ),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: running || selectedIds.isEmpty ? null : onGenerate,
              icon: const Icon(Icons.auto_awesome),
              label: const Text('Generate selected'),
            ),
          ],
        ),
      ),
    );
  }

  static String _id(Map<String, dynamic> item) =>
      (item['item_id'] ?? item['itemId']) as String;
}

class _CandidateCard extends StatelessWidget {
  const _CandidateCard({
    required this.candidate,
    required this.recommended,
    required this.selected,
    required this.onChanged,
  });

  final Map<String, dynamic> candidate;
  final bool recommended;
  final bool selected;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) {
    final imageUrl = candidate['image_url'] ?? candidate['imageUrl'];
    return SizedBox(
      width: 180,
      child: Card.outlined(
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: () => onChanged(!selected),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (imageUrl is String && imageUrl.isNotEmpty)
                Image.network(imageUrl, height: 150, fit: BoxFit.cover)
              else
                const SizedBox(height: 150, child: Icon(Icons.checkroom)),
              CheckboxListTile(
                value: selected,
                onChanged: (value) => onChanged(value ?? false),
                title: Text(candidate['category'] as String? ?? 'Item'),
                subtitle: recommended ? const Text('Recommended') : null,
                controlAffinity: ListTileControlAffinity.leading,
                dense: true,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ResultPanel extends StatelessWidget {
  const _ResultPanel({
    required this.source,
    required this.coordinateImageUrl,
  });

  final String source;
  final String? coordinateImageUrl;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Result', style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 12),
            if (coordinateImageUrl == null)
              const SizedBox(
                height: 220,
                child:
                    Center(child: Text('Coordinate image will appear here.')),
              )
            else
              ClipRRect(
                borderRadius: BorderRadius.circular(8),
                child: Image.network(
                  coordinateImageUrl!,
                  height: 360,
                  fit: BoxFit.contain,
                  errorBuilder: (context, error, stackTrace) =>
                      SelectableText(coordinateImageUrl!),
                ),
              ),
            if (source == 'SHARED_CLOSET') ...[
              const SizedBox(height: 12),
              const AttributionFooter(),
            ],
          ],
        ),
      ),
    );
  }
}

class AgentEvent {
  AgentEvent({
    required this.seq,
    required this.agentName,
    required this.eventKind,
    this.toolName,
    this.toolArgs,
    this.toolResult,
    this.text,
  });

  final int seq;
  final String agentName;
  final String eventKind;
  final String? toolName;
  final Map<String, dynamic>? toolArgs;
  final Map<String, dynamic>? toolResult;
  final String? text;

  factory AgentEvent.fromJson(Map<String, dynamic> json) {
    return AgentEvent(
      seq: (json['seq'] as num?)?.toInt() ?? 0,
      agentName: json['agentName'] as String? ?? 'unknown',
      eventKind: json['eventKind'] as String? ?? 'unknown',
      toolName: json['toolName'] as String?,
      toolArgs: (json['toolArgs'] as Map?)?.cast<String, dynamic>(),
      toolResult: (json['toolResult'] as Map?)?.cast<String, dynamic>(),
      text: json['text'] as String?,
    );
  }

  String get detailText {
    final parts = <String>[
      'seq: $seq',
      'agent: $agentName',
      'kind: $eventKind',
      if (toolName != null) 'tool: $toolName',
      if (text != null) 'text: $text',
      if (toolArgs != null) 'args: $toolArgs',
      if (toolResult != null) 'result: $toolResult',
    ];
    return parts.join('\n');
  }

  String get summary {
    if (toolName == 'search_closet' && eventKind == 'tool_result') {
      final raw = toolResult?['result'];
      final count = raw is List ? raw.length : 0;
      return '$agentName searched closet — $count candidates';
    }
    if (toolName == 'search_closet') {
      return '$agentName is searching the closet';
    }
    if (toolName == 'style_synthesizer') {
      return eventKind == 'tool_result'
          ? '$agentName generated the coordinate'
          : '$agentName is generating the coordinate';
    }
    return text ?? '$agentName · $eventKind';
  }
}
