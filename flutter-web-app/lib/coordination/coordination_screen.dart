import 'dart:convert';

import 'package:flutter/material.dart';

import '../api/api_client.dart';
import '../config.dart';
import '../e2e_probe_stub.dart' if (dart.library.html) '../e2e_probe_web.dart';
import '../l10n/app_localizations.dart';
import '../locale/locale_controller.dart';
import '../shared/attribution.dart';
import '../theme/components.dart';

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
    final languageCode = LocaleScope.of(context).languageCode;
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
          'language': languageCode,
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
      await _recoverSessionState(selected.sessionId);
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
      await _recoverSessionState(sessionId);
    } catch (e) {
      if (mounted) setState(() => _error = e);
    } finally {
      if (mounted) setState(() => _running = false);
    }
  }

  Future<void> _recoverSessionState(String sessionId) async {
    if (!mounted) return;
    final session = await _api.getSession(sessionId);
    if (!mounted) return;
    setState(() {
      _status = session.status;
      if (_candidates.isEmpty && session.proposedCandidates.isNotEmpty) {
        _candidates
          ..clear()
          ..addAll(session.proposedCandidates);
        if (_selectedCandidateIds.isEmpty) {
          _selectedCandidateIds.add(_candidateId(_candidates.first));
        }
      }
      if (_coordinateImageUrl == null &&
          session.coordinateImageUrl != null &&
          session.coordinateImageUrl!.isNotEmpty) {
        _coordinateImageUrl = session.coordinateImageUrl;
      }
      _reportE2eState();
    });
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
          languageCode: LocaleScope.of(context).languageCode,
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
    required this.languageCode,
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
  final String languageCode;
  final ValueChanged<String> onSourceChanged;
  final ValueChanged<String> onSharedClosetChanged;
  final ValueChanged<String> onGenderChanged;
  final VoidCallback onStart;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final languageLabel =
        languageCode == 'en' ? l10n.languageEnglish : l10n.languageJapanese;
    return SectionCard(
      child: Padding(
        padding: EdgeInsets.zero,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const EyebrowLabel('Studio'),
            const SizedBox(height: 6),
            Text(
              l10n.coordinationTitle,
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 16),
            SegmentedButton<String>(
              segments: [
                ButtonSegment(
                  value: 'SHARED_CLOSET',
                  icon: const Icon(Icons.groups_outlined),
                  label: Text(l10n.sourceShared),
                ),
                ButtonSegment(
                  value: 'CLOSET',
                  icon: const Icon(Icons.checkroom_outlined),
                  label: Text(l10n.sourceMine),
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
                decoration: InputDecoration(
                  labelText: l10n.sharedCloset,
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
            _TextField(controller: occasion, label: l10n.occasion),
            _TextField(controller: style, label: l10n.style),
            _TextField(controller: season, label: l10n.season),
            _TextField(controller: color, label: l10n.colors),
            DropdownButtonFormField<String>(
              initialValue: gender,
              decoration: InputDecoration(
                labelText: l10n.gender,
              ),
              items: [
                DropdownMenuItem(
                  value: 'common',
                  child: Text(l10n.genderCommon),
                ),
                DropdownMenuItem(
                  value: 'female',
                  child: Text(l10n.genderFemale),
                ),
                DropdownMenuItem(value: 'male', child: Text(l10n.genderMale)),
              ],
              onChanged: running
                  ? null
                  : (value) {
                      if (value != null) onGenderChanged(value);
                    },
            ),
            const SizedBox(height: 8),
            EyebrowLabel(l10n.selectedGenerationLanguage(languageLabel)),
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
              label: Text(running ? l10n.running : l10n.start),
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
    final l10n = AppLocalizations.of(context)!;
    return SectionCard(
      child: Padding(
        padding: EdgeInsets.zero,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    l10n.agentTrace,
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
              Text(
                l10n.errorWithMessage('$error'),
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              )
            else if (events.isEmpty)
              SizedBox(
                height: 160,
                child: Center(
                  child: running
                      ? const CircularProgressIndicator()
                      : Text(l10n.noSessionEvents),
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

enum _TraceView { preview, raw }

class AgentEventTile extends StatefulWidget {
  const AgentEventTile({super.key, required this.event});

  final AgentEvent event;

  @override
  State<AgentEventTile> createState() => _AgentEventTileState();
}

class _AgentEventTileState extends State<AgentEventTile> {
  _TraceView _view = _TraceView.preview;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final title = widget.event.summary(l10n);
    return ExpansionTile(
      tilePadding: EdgeInsets.zero,
      leading: Icon(_iconFor(widget.event.eventKind)),
      title: Text(title, overflow: TextOverflow.ellipsis),
      subtitle: widget.event.text == null
          ? null
          : Text(widget.event.text!,
              maxLines: 1, overflow: TextOverflow.ellipsis),
      children: [
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(12),
          color: Theme.of(context).colorScheme.surfaceContainerHighest,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SegmentedButton<_TraceView>(
                segments: [
                  ButtonSegment(
                    value: _TraceView.preview,
                    label: Text(l10n.tracePreview),
                  ),
                  ButtonSegment(
                    value: _TraceView.raw,
                    label: Text(l10n.traceRaw),
                  ),
                ],
                selected: {_view},
                onSelectionChanged: (values) =>
                    setState(() => _view = values.first),
                style: const ButtonStyle(
                  visualDensity: VisualDensity.compact,
                  tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                ),
              ),
              const SizedBox(height: 12),
              if (_view == _TraceView.preview)
                _AgentPreview(event: widget.event)
              else
                SelectableText(
                  const JsonEncoder.withIndent('  ')
                      .convert(widget.event.toJson()),
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        fontFamily: 'SpaceMono',
                      ),
                ),
            ],
          ),
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

// ── MJ: Preview dispatcher ────────────────────────────────────────────────────

class _AgentPreview extends StatelessWidget {
  const _AgentPreview({required this.event});

  final AgentEvent event;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    if (event.toolName == 'search_closet') {
      return _SearchClosetPreview(event: event, l10n: l10n);
    }
    if (event.toolName == 'style_synthesizer') {
      return _StyleSynthesizerPreview(event: event, l10n: l10n);
    }
    if (event.toolName == 'transfer_to_agent') {
      final agentName =
          event.toolArgs?['agent_name'] as String? ?? event.text ?? '—';
      return _PreviewField(label: l10n.traceTargetAgent, child: Text(agentName));
    }
    if (event.eventKind == 'final_answer') {
      return _FinalAnswerPreview(event: event);
    }
    return SelectableText(
      const JsonEncoder.withIndent('  ').convert(event.toJson()),
      style: Theme.of(context).textTheme.bodySmall,
    );
  }
}

class _SearchClosetPreview extends StatelessWidget {
  const _SearchClosetPreview({required this.event, required this.l10n});

  final AgentEvent event;
  final AppLocalizations l10n;

  @override
  Widget build(BuildContext context) {
    if (event.eventKind == 'tool_call') {
      final args = event.toolArgs ?? {};
      final description = args['description'] as String?;
      final category = args['category'] as String?;
      final rawColors = args['colors'];
      final colors =
          rawColors is List ? rawColors.cast<String>() : <String>[];
      final gender = args['gender'] as String?;

      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (description != null)
            _PreviewField(
                label: l10n.traceDescription, child: Text(description)),
          if (category != null)
            _PreviewField(label: l10n.category, child: Text(category)),
          if (colors.isNotEmpty)
            _PreviewField(
                label: l10n.colors, child: _ChipRow(values: colors)),
          if (gender != null)
            _PreviewField(label: l10n.gender, child: Text(gender)),
        ],
      );
    }

    // tool_result: N items found + compact per-item rows
    final raw = event.toolResult?['result'];
    final items = raw is List
        ? raw.cast<Map<String, dynamic>>()
        : <Map<String, dynamic>>[];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          l10n.traceItemsFound(items.length),
          style: Theme.of(context).textTheme.labelMedium,
        ),
        const SizedBox(height: 8),
        ...items.map((item) => _ClosetItemRow(item: item)),
      ],
    );
  }
}

class _StyleSynthesizerPreview extends StatelessWidget {
  const _StyleSynthesizerPreview({required this.event, required this.l10n});

  final AgentEvent event;
  final AppLocalizations l10n;

  @override
  Widget build(BuildContext context) {
    if (event.eventKind == 'tool_call') {
      final args = event.toolArgs ?? {};
      final styleDesc = args['style_description'] as String?;
      final age = args['wearer_age'] as String?;
      final gender = args['gender'] as String?;
      final language = args['language'] as String?;
      final itemCount = (args['item_image_urls'] as List?)?.length ?? 0;
      final wearer = [age, gender].whereType<String>().join(' ');

      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (styleDesc != null)
            _PreviewField(
                label: l10n.traceStyleDirection, child: Text(styleDesc)),
          if (wearer.isNotEmpty)
            _PreviewField(label: l10n.traceWearer, child: Text(wearer)),
          if (language != null)
            _PreviewField(label: l10n.language, child: Text(language)),
          _PreviewField(
              label: l10n.traceItemCount, child: Text('$itemCount')),
        ],
      );
    }

    // tool_result
    final result = event.toolResult ?? {};
    final model = result['model_used'] as String?;
    final language = result['language'] as String?;
    final prompt = result['generation_prompt'] as String?;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (model != null)
          _PreviewField(label: l10n.traceModelUsed, child: Text(model)),
        if (language != null)
          _PreviewField(label: l10n.language, child: Text(language)),
        if (prompt != null)
          _PreviewField(label: l10n.traceGenerationPrompt, child: Text(prompt)),
      ],
    );
  }
}

class _FinalAnswerPreview extends StatelessWidget {
  const _FinalAnswerPreview({required this.event});

  final AgentEvent event;

  @override
  Widget build(BuildContext context) {
    final text = event.text;
    if (text == null || text.isEmpty) {
      return SelectableText(
        const JsonEncoder.withIndent('  ').convert(event.toJson()),
        style: Theme.of(context).textTheme.bodySmall,
      );
    }
    return SelectableText(text);
  }
}

// ── MJ: Shared preview helpers ────────────────────────────────────────────────

class _PreviewField extends StatelessWidget {
  const _PreviewField({required this.label, required this.child});

  final String label;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 88,
            child: Text(
              label,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
            ),
          ),
          Expanded(
            child: DefaultTextStyle.merge(
              style: Theme.of(context).textTheme.bodySmall!,
              child: child,
            ),
          ),
        ],
      ),
    );
  }
}

class _ChipRow extends StatelessWidget {
  const _ChipRow({required this.values});

  final List<String> values;

  @override
  Widget build(BuildContext context) {
    if (values.isEmpty) return const SizedBox.shrink();
    return Wrap(
      spacing: 4,
      runSpacing: 2,
      children: values
          .map((v) => RawChip(
                label: Text(v),
                materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                visualDensity: VisualDensity.compact,
                padding: EdgeInsets.zero,
                labelPadding: const EdgeInsets.symmetric(horizontal: 6),
              ))
          .toList(),
    );
  }
}

class _ClosetItemRow extends StatelessWidget {
  const _ClosetItemRow({required this.item});

  final Map<String, dynamic> item;

  @override
  Widget build(BuildContext context) {
    final imageUrl = item['image_url'] as String?;
    final category = item['category'] as String?;
    final colors = (item['colors'] as List?)?.cast<String>() ?? <String>[];
    final tags = (item['tags'] as List?)?.cast<String>() ?? <String>[];
    final season = item['season'] as String?;

    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: SizedBox(
              width: 48,
              height: 48,
              child: imageUrl != null && imageUrl.isNotEmpty
                  ? Image.network(imageUrl, fit: BoxFit.cover,
                      errorBuilder: (_, __, ___) => ColoredBox(
                            color: Theme.of(context)
                                .colorScheme
                                .surfaceContainerHighest,
                            child: const Icon(Icons.checkroom, size: 20),
                          ))
                  : ColoredBox(
                      color: Theme.of(context)
                          .colorScheme
                          .surfaceContainerHighest,
                      child: const Icon(Icons.checkroom, size: 20),
                    ),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (category != null)
                  Text(category,
                      style: Theme.of(context).textTheme.bodySmall),
                if (colors.isNotEmpty) ...[
                  const SizedBox(height: 2),
                  _ChipRow(values: colors),
                ],
                if (tags.isNotEmpty) ...[
                  const SizedBox(height: 2),
                  _ChipRow(values: tags),
                ],
                if (season != null) ...[
                  const SizedBox(height: 2),
                  Text(
                    season,
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color:
                              Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
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
    final l10n = AppLocalizations.of(context)!;
    return SectionCard(
      child: Padding(
        padding: EdgeInsets.zero,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(l10n.chooseItems,
                style: Theme.of(context).textTheme.titleLarge),
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
              label: Text(l10n.generateSelected),
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
    final l10n = AppLocalizations.of(context)!;
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
                title: Text(candidate['category'] as String? ?? l10n.item),
                subtitle: recommended ? Text(l10n.recommended) : null,
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
    final l10n = AppLocalizations.of(context)!;
    return SectionCard(
      child: Padding(
        padding: EdgeInsets.zero,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(l10n.result, style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 12),
            if (coordinateImageUrl == null)
              SizedBox(
                height: 220,
                child: Center(child: Text(l10n.coordinatePlaceholder)),
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

  Map<String, dynamic> toJson() => {
        'seq': seq,
        'agentName': agentName,
        'eventKind': eventKind,
        if (toolName != null) 'toolName': toolName,
        if (text != null) 'text': text,
        if (toolArgs != null) 'toolArgs': toolArgs,
        if (toolResult != null) 'toolResult': toolResult,
      };

  String get detailText =>
      const JsonEncoder.withIndent('  ').convert(toJson());

  String summary(AppLocalizations l10n) {
    if (toolName == 'search_closet' && eventKind == 'tool_result') {
      final raw = toolResult?['result'];
      final count = raw is List ? raw.length : 0;
      return l10n.traceSearchedCloset(agentName, count);
    }
    if (toolName == 'search_closet') {
      return l10n.traceSearchingCloset(agentName);
    }
    if (toolName == 'style_synthesizer') {
      return eventKind == 'tool_result'
          ? l10n.traceGeneratedCoordinate(agentName)
          : l10n.traceGeneratingCoordinate(agentName);
    }
    return text ?? '$agentName · $eventKind';
  }
}
