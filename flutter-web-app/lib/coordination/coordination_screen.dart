import 'dart:convert';

import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../api/api_client.dart';
import '../closet/closet_item.dart';
import '../closet/thumbnail.dart';
import '../closet/upload_service.dart';
import '../config.dart';
import '../e2e_probe_stub.dart' if (dart.library.html) '../e2e_probe_web.dart';
import '../history/history_item.dart';
import '../l10n/app_localizations.dart';
import '../locale/locale_controller.dart';
import '../theme/components.dart';

const List<String> _sharedClosets = ['adult-01', 'adult-02', 'child-01'];
const int _kMaxAnchorItems = 3;

class CoordinationScreen extends StatefulWidget {
  const CoordinationScreen({
    super.key,
    required this.uid,
    ApiClient? api,
    UploadService? uploads,
    Stream<List<ClosetItem>>? anchorItemsStream,
    this.onSessionTerminal,
    this.recoveryPollInterval = const Duration(seconds: 5),
    this.recoveryPollMaxWait = const Duration(minutes: 5),
  })  : _api = api,
        _uploads = uploads,
        _anchorItemsStream = anchorItemsStream;

  final String uid;
  final ApiClient? _api;
  final UploadService? _uploads;

  /// Injectable READY-closet stream so widget tests avoid Firestore.
  final Stream<List<ClosetItem>>? _anchorItemsStream;

  /// Invoked exactly once per session id when it reaches COMPLETED/ERROR,
  /// even if this happens while the widget is not the visible tab (its
  /// State is kept alive across tab switches by HomeScreen's IndexedStack).
  final void Function(String sessionId, String status)? onSessionTerminal;

  /// How often to re-check session status once the live event stream ends
  /// without a terminal status. Overridable only for tests.
  final Duration recoveryPollInterval;

  /// How long to keep polling before giving up. Overridable only for tests.
  final Duration recoveryPollMaxWait;

  @override
  State<CoordinationScreen> createState() => _CoordinationScreenState();
}

class _CoordinationScreenState extends State<CoordinationScreen> {
  late final ApiClient _api = widget._api ?? ApiClient();
  late final DownloadUrlCache _thumbnailCache = DownloadUrlCache(_api);
  late final UploadService _uploads =
      widget._uploads ?? UploadService(api: _api);
  final Set<String> _selectedOccasions = {'casual_weekend'};
  final Set<String> _selectedStyles = {'clean_casual'};
  final Set<String> _selectedSeasons = {'spring'};
  final Set<String> _selectedColors = {'blue', 'white'};
  final _occasionOther = TextEditingController();
  final _styleOther = TextEditingController();
  final _seasonOther = TextEditingController();
  final _colorOther = TextEditingController();
  final List<AgentEvent> _events = [];
  final List<Map<String, dynamic>> _candidates = [];
  final Set<String> _selectedCandidateIds = {};
  final Set<String> _anchorItemIds = {};
  final Set<String> _pendingUploadedAnchorIds = {};
  final Set<String> _savedCandidateIds = {};
  final Set<String> _importingCandidateIds = {};
  Stream<List<ClosetItem>>? _anchorStream;
  String _mode = 'STANDARD';
  String _source = 'SHARED_CLOSET';
  String _sharedClosetId = _sharedClosets.first;
  String _gender = 'common';
  String? _sessionId;
  String? _status;
  String? _coordinateImageUrl;
  bool _running = false;
  bool _uploadingAnchor = false;
  Object? _error;
  bool _autoRunStarted = false;
  String? _notifiedTerminalSessionId;

  Stream<List<ClosetItem>> _readyClosetItems() {
    return _anchorStream ??= widget._anchorItemsStream ??
        FirebaseFirestore.instance
            .collection('users')
            .doc(widget.uid)
            .collection('closet')
            .orderBy('createdAt', descending: true)
            .snapshots()
            .map(
              (snapshot) => snapshot.docs
                  .map((doc) => ClosetItem.fromFirestore(doc.id, doc.data()))
                  // Keep PROCESSING items so a freshly uploaded anchor shows
                  // an analyzing placeholder instead of silently missing.
                  .where((item) =>
                      item.status == ItemStatus.ready ||
                      item.status == ItemStatus.processing)
                  .toList(),
            );
  }

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
    _occasionOther.dispose();
    _styleOther.dispose();
    _seasonOther.dispose();
    _colorOther.dispose();
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
      _savedCandidateIds.clear();
      _coordinateImageUrl = null;
    });
    final l10n = AppLocalizations.of(context)!;
    final userPreference = {
      'occasion': _preferenceText(
        _occasionOptions(l10n),
        _selectedOccasions,
        _occasionOther.text,
      ),
      'style': _preferenceText(
        _styleOptions(l10n),
        _selectedStyles,
        _styleOther.text,
      ),
      'season': _preferenceText(
        _seasonOptions(l10n),
        _selectedSeasons,
        _seasonOther.text,
      ),
      'colorPreference': _preferenceText(
        _colorOptions(l10n),
        _selectedColors,
        _colorOther.text,
      ),
      'gender': _gender,
      'language': languageCode,
    };
    try {
      final created = await _api.createSession();
      final selected = _mode == 'ASSISTED'
          ? await _api.assistSession(
              sessionId: created.sessionId,
              anchorItemIds: _anchorItemIds.toList(),
              userPreference: userPreference,
            )
          : await _api.selectSource(
              sessionId: created.sessionId,
              source: _source,
              sharedClosetId:
                  _source == 'SHARED_CLOSET' ? _sharedClosetId : null,
              userPreference: userPreference,
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
            _applyDefaultSelection();
          } else if (message.event == 'session.snapshot' ||
              message.event == 'session.completed' ||
              message.event == 'session.error') {
            _status = message.data['status'] as String?;
          }
          _reportE2eState();
        });
        _maybeNotifyTerminal();
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
        _maybeNotifyTerminal();
      }
      await _recoverSessionState(sessionId);
      if (_status == 'COMPLETED') {
        await _maybeOfferSaveInteresting();
      }
    } catch (e) {
      if (mounted) setState(() => _error = e);
    } finally {
      if (mounted) setState(() => _running = false);
    }
  }

  /// After generation, offer to save the Rakuten items used in this outfit
  /// into the closet as "Interesting" (all pre-checked, user can opt out).
  Future<void> _maybeOfferSaveInteresting() async {
    if (!mounted) return;
    final offerable = _candidates
        .where((candidate) =>
            _selectedCandidateIds.contains(_candidateId(candidate)) &&
            candidate['source'] == 'RAKUTEN' &&
            !_savedCandidateIds.contains(_candidateId(candidate)))
        .toList();
    if (offerable.isEmpty) return;
    final chosen = await showDialog<Set<String>>(
      context: context,
      builder: (ctx) => _SaveInterestingDialog(candidates: offerable),
    );
    if (chosen == null || chosen.isEmpty || !mounted) return;
    await Future.wait(
      offerable
          .where((candidate) => chosen.contains(_candidateId(candidate)))
          .map(_importSuggestion),
    );
  }

  /// Resyncs status/candidates/image from the backend after the live event
  /// stream ends. If the resolved status is still GENERATING (the SSE
  /// stream can close on its own 150s cap before the backend, which keeps
  /// running independently, actually finishes) this keeps polling until it
  /// resolves or [CoordinationScreen.recoveryPollMaxWait] elapses, so a
  /// session that outlives the stream's connection is still eventually
  /// observed (and its completion notified via [_maybeNotifyTerminal]).
  Future<void> _recoverSessionState(String sessionId) async {
    final deadline = DateTime.now().add(widget.recoveryPollMaxWait);
    while (mounted) {
      final SessionHistoryItem session;
      try {
        session = await _api.getSession(sessionId);
      } catch (e) {
        if (mounted) setState(() => _error = e);
        return;
      }
      if (!mounted) return;
      setState(() {
        _status = session.status;
        if (_candidates.isEmpty && session.proposedCandidates.isNotEmpty) {
          _candidates
            ..clear()
            ..addAll(session.proposedCandidates);
          if (_selectedCandidateIds.isEmpty) {
            _applyDefaultSelection();
          }
        }
        if (_coordinateImageUrl == null &&
            session.coordinateImageUrl != null &&
            session.coordinateImageUrl!.isNotEmpty) {
          _coordinateImageUrl = session.coordinateImageUrl;
        }
        _reportE2eState();
      });
      _maybeNotifyTerminal();
      if (session.status != 'GENERATING') return;
      if (DateTime.now().isAfter(deadline)) {
        if (mounted) {
          setState(() => _error = StateError(
              'Still generating after ${widget.recoveryPollMaxWait.inMinutes} '
              'minutes.'));
        }
        return;
      }
      await Future.delayed(widget.recoveryPollInterval);
    }
  }

  /// Fires [CoordinationScreen.onSessionTerminal] exactly once per session
  /// id when it reaches a terminal status, however that status was learned
  /// (live stream event or a recovery poll read).
  void _maybeNotifyTerminal() {
    final sid = _sessionId;
    final status = _status;
    if (sid == null || status == null) return;
    if (status != 'COMPLETED' && status != 'ERROR') return;
    if (_notifiedTerminalSessionId == sid) return;
    _notifiedTerminalSessionId = sid;
    widget.onSessionTerminal?.call(sid, status);
  }

  void _resetCompletedSession() {
    if (_running) return;
    setState(() {
      _events.clear();
      _candidates.clear();
      _selectedCandidateIds.clear();
      _savedCandidateIds.clear();
      _importingCandidateIds.clear();
      _sessionId = null;
      _status = null;
      _coordinateImageUrl = null;
      _error = null;
      _notifiedTerminalSessionId = null;
      _reportE2eState();
    });
  }

  String _candidateId(Map<String, dynamic> candidate) =>
      (candidate['item_id'] ?? candidate['itemId']) as String;

  /// Anchors stay selected, but recommendations are capped to one per outfit
  /// slot so a single-coordinate run does not start with duplicate bottoms,
  /// shoes, or other same-category alternatives selected together.
  void _applyDefaultSelection() {
    _selectedCandidateIds.clear();
    final selectedSlots = <String>{};
    for (final candidate in _candidates) {
      if (candidate['anchor'] != true) continue;
      _selectedCandidateIds.add(_candidateId(candidate));
      final slot = _candidateOutfitSlot(candidate);
      if (slot != null) selectedSlots.add(slot);
    }
    for (final candidate in _candidates) {
      if (candidate['recommended'] != true || candidate['anchor'] == true) {
        continue;
      }
      final slot = _candidateOutfitSlot(candidate);
      if (slot != null && selectedSlots.contains(slot)) continue;
      _selectedCandidateIds.add(_candidateId(candidate));
      if (slot != null) selectedSlots.add(slot);
    }
    if (_selectedCandidateIds.isEmpty && _candidates.isNotEmpty) {
      _selectedCandidateIds.add(_candidateId(_candidates.first));
    }
  }

  String? _candidateOutfitSlot(Map<String, dynamic> candidate) {
    final text = [
      candidate['category'],
      candidate['name'],
    ].whereType<String>().join(' ').toLowerCase();
    if (text.trim().isEmpty) return null;
    if (_containsAny(text, const [
      'pants',
      'pant',
      'trouser',
      'slacks',
      'shorts',
      'skirt',
      'jeans',
      'denim',
      'bottom',
      'ズボン',
      'パンツ',
      'ボトム',
    ])) {
      return 'bottom';
    }
    if (_containsAny(text, const [
      'shoe',
      'shoes',
      'sneaker',
      'sneakers',
      'trainer',
      'boot',
      'sandal',
      '靴',
      'シューズ',
      'スニーカー',
    ])) {
      return 'shoes';
    }
    if (_containsAny(text, const [
      'coat',
      'jacket',
      'blazer',
      'outer',
      'outerwear',
      'outwear',
      'アウター',
      'ジャケット',
      'コート',
    ])) {
      return 'outer';
    }
    if (_containsAny(text, const [
      'hat',
      'cap',
      'bag',
      'belt',
      'watch',
      'scarf',
      'accessory',
      '帽子',
      'バッグ',
      'ベルト',
    ])) {
      return 'accessory';
    }
    if (_containsAny(text, const [
      'top',
      'shirt',
      't-shirt',
      'tee',
      'blouse',
      'polo',
      'hoodie',
      'sweater',
      'knit',
      'inner',
      'トップ',
      'シャツ',
      'インナー',
      'ニット',
    ])) {
      return 'top';
    }
    return text.trim();
  }

  bool _containsAny(String value, List<String> needles) =>
      needles.any((needle) => value.contains(needle));

  void _toggleAnchor(String itemId) {
    setState(() {
      if (_anchorItemIds.contains(itemId)) {
        _anchorItemIds.remove(itemId);
      } else if (_anchorItemIds.length < _kMaxAnchorItems) {
        _anchorItemIds.add(itemId);
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(AppLocalizations.of(context)!.anchorLimitReached),
          ),
        );
      }
    });
  }

  Future<void> _onUploadAnchor() async {
    if (_uploadingAnchor) return;
    setState(() => _uploadingAnchor = true);
    final l10n = AppLocalizations.of(context)!;
    try {
      final id = await _uploads.upload();
      if (!mounted || id == null) return;
      setState(() => _pendingUploadedAnchorIds.add(id));
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(l10n.uploadQueued)),
      );
    } on ClosetFullException {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(l10n.closetFull)),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(l10n.uploadFailed('$e'))),
      );
    } finally {
      if (mounted) setState(() => _uploadingAnchor = false);
    }
  }

  void _selectReadyUploadedAnchors(Iterable<String> itemIds) {
    setState(() {
      for (final itemId in itemIds) {
        _pendingUploadedAnchorIds.remove(itemId);
        if (_anchorItemIds.length < _kMaxAnchorItems) {
          _anchorItemIds.add(itemId);
        }
      }
    });
  }

  Future<void> _importSuggestion(Map<String, dynamic> candidate) async {
    final sessionId = _sessionId;
    final candidateId = _candidateId(candidate);
    if (sessionId == null || _importingCandidateIds.contains(candidateId)) {
      return;
    }
    setState(() => _importingCandidateIds.add(candidateId));
    final l10n = AppLocalizations.of(context)!;
    try {
      await _api.importSuggestedItem(
        sessionId: sessionId,
        candidateId: candidateId,
      );
      if (!mounted) return;
      setState(() => _savedCandidateIds.add(candidateId));
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(l10n.savedAsInteresting)),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(l10n.importFailed('$e'))),
      );
    } finally {
      if (mounted) {
        setState(() => _importingCandidateIds.remove(candidateId));
      }
    }
  }

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
          mode: _mode,
          source: _source,
          sharedClosetId: _sharedClosetId,
          running: _running,
          selectedOccasions: _selectedOccasions,
          selectedStyles: _selectedStyles,
          selectedSeasons: _selectedSeasons,
          selectedColors: _selectedColors,
          occasionOther: _occasionOther,
          styleOther: _styleOther,
          seasonOther: _seasonOther,
          colorOther: _colorOther,
          gender: _gender,
          languageCode: LocaleScope.of(context).languageCode,
          anchorPicker: _mode == 'ASSISTED'
              ? _AnchorPicker(
                  itemsStream: _readyClosetItems(),
                  selectedIds: _anchorItemIds,
                  pendingUploadedIds: _pendingUploadedAnchorIds,
                  cache: _thumbnailCache,
                  running: _running,
                  uploading: _uploadingAnchor,
                  onToggle: _toggleAnchor,
                  onUpload: _onUploadAnchor,
                  onReadyUploadedItems: _selectReadyUploadedAnchors,
                )
              : null,
          startEnabled: _mode == 'STANDARD' || _anchorItemIds.isNotEmpty,
          onModeChanged: (value) => setState(() => _mode = value),
          onSourceChanged: (value) => setState(() => _source = value),
          onSharedClosetChanged: (value) =>
              setState(() => _sharedClosetId = value),
          onOccasionsChanged: (values) => setState(() {
            _selectedOccasions
              ..clear()
              ..addAll(values);
          }),
          onStylesChanged: (values) => setState(() {
            _selectedStyles
              ..clear()
              ..addAll(values);
          }),
          onSeasonsChanged: (values) => setState(() {
            _selectedSeasons
              ..clear()
              ..addAll(values);
          }),
          onColorsChanged: (values) => setState(() {
            _selectedColors
              ..clear()
              ..addAll(values);
          }),
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
          coordinateImageUrl: _coordinateImageUrl,
          completed: _status == 'COMPLETED',
          running: _running,
          onStartNew: _resetCompletedSession,
        );
        final candidates = CandidatePanel(
          candidates: _candidates,
          selectedIds: _selectedCandidateIds,
          savedIds: _savedCandidateIds,
          importingIds: _importingCandidateIds,
          running: _running,
          canGenerate: _status == 'PROPOSING',
          onChanged: (id, selected) => setState(() {
            selected
                ? _selectedCandidateIds.add(id)
                : _selectedCandidateIds.remove(id);
          }),
          onImport: _sessionId == null ? null : _importSuggestion,
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
    required this.mode,
    required this.source,
    required this.sharedClosetId,
    required this.running,
    required this.selectedOccasions,
    required this.selectedStyles,
    required this.selectedSeasons,
    required this.selectedColors,
    required this.occasionOther,
    required this.styleOther,
    required this.seasonOther,
    required this.colorOther,
    required this.gender,
    required this.languageCode,
    required this.startEnabled,
    required this.onModeChanged,
    required this.onSourceChanged,
    required this.onSharedClosetChanged,
    required this.onOccasionsChanged,
    required this.onStylesChanged,
    required this.onSeasonsChanged,
    required this.onColorsChanged,
    required this.onGenderChanged,
    required this.onStart,
    this.anchorPicker,
  });

  final String mode;
  final String source;
  final String sharedClosetId;
  final bool running;
  final Set<String> selectedOccasions;
  final Set<String> selectedStyles;
  final Set<String> selectedSeasons;
  final Set<String> selectedColors;
  final TextEditingController occasionOther;
  final TextEditingController styleOther;
  final TextEditingController seasonOther;
  final TextEditingController colorOther;
  final String gender;
  final String languageCode;
  final bool startEnabled;
  final Widget? anchorPicker;
  final ValueChanged<String> onModeChanged;
  final ValueChanged<String> onSourceChanged;
  final ValueChanged<String> onSharedClosetChanged;
  final ValueChanged<Set<String>> onOccasionsChanged;
  final ValueChanged<Set<String>> onStylesChanged;
  final ValueChanged<Set<String>> onSeasonsChanged;
  final ValueChanged<Set<String>> onColorsChanged;
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
                  value: 'STANDARD',
                  icon: const Icon(Icons.style_outlined),
                  label: Text(l10n.modeStandard),
                  tooltip: l10n.modeStandardHint,
                ),
                ButtonSegment(
                  value: 'ASSISTED',
                  icon: const Icon(Icons.shopping_bag_outlined),
                  label: Text(l10n.modeAssisted),
                  tooltip: l10n.modeAssistedHint,
                ),
              ],
              selected: {mode},
              onSelectionChanged:
                  running ? null : (values) => onModeChanged(values.first),
            ),
            const SizedBox(height: 8),
            Text(
              mode == 'ASSISTED'
                  ? l10n.modeAssistedHint
                  : l10n.modeStandardHint,
              style: Theme.of(context).textTheme.bodySmall,
            ),
            const SizedBox(height: 12),
            if (mode == 'STANDARD') ...[
              SegmentedButton<String>(
                segments: [
                  ButtonSegment(
                    value: 'SHARED_CLOSET',
                    icon: const Icon(Icons.groups_outlined),
                    label: Text(l10n.sourceShared),
                    tooltip: l10n.sourceSharedHint,
                  ),
                  ButtonSegment(
                    value: 'CLOSET',
                    icon: const Icon(Icons.checkroom_outlined),
                    label: Text(l10n.sourceMine),
                    tooltip: l10n.sourceMineHint,
                  ),
                ],
                selected: {source},
                onSelectionChanged:
                    running ? null : (values) => onSourceChanged(values.first),
              ),
              const SizedBox(height: 8),
              Text(
                source == 'SHARED_CLOSET'
                    ? l10n.sourceSharedHint
                    : l10n.sourceMineHint,
                style: Theme.of(context).textTheme.bodySmall,
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
            ] else if (anchorPicker != null)
              anchorPicker!,
            const SizedBox(height: 12),
            _PreferenceMultiSelect(
              fieldKey: 'occasion',
              label: l10n.occasion,
              options: _occasionOptions(l10n),
              selectedIds: selectedOccasions,
              otherController: occasionOther,
              enabled: !running,
              onChanged: onOccasionsChanged,
            ),
            _PreferenceMultiSelect(
              fieldKey: 'style',
              label: l10n.style,
              options: _styleOptions(l10n),
              selectedIds: selectedStyles,
              otherController: styleOther,
              enabled: !running,
              onChanged: onStylesChanged,
            ),
            _PreferenceMultiSelect(
              fieldKey: 'season',
              label: l10n.season,
              options: _seasonOptions(l10n),
              selectedIds: selectedSeasons,
              otherController: seasonOther,
              enabled: !running,
              onChanged: onSeasonsChanged,
            ),
            _PreferenceMultiSelect(
              fieldKey: 'color',
              label: l10n.colors,
              options: _colorOptions(l10n),
              selectedIds: selectedColors,
              otherController: colorOther,
              enabled: !running,
              onChanged: onColorsChanged,
            ),
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
              onPressed: running || !startEnabled ? null : onStart,
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

const String _otherPreferenceId = 'other';

class _PreferenceOption {
  const _PreferenceOption(this.id, this.label);

  final String id;
  final String label;
}

List<_PreferenceOption> _occasionOptions(AppLocalizations l10n) => [
      _PreferenceOption(
        'casual_weekend',
        l10n.preferenceOccasionCasualWeekend,
      ),
      _PreferenceOption('work', l10n.preferenceOccasionWork),
      _PreferenceOption('date', l10n.preferenceOccasionDate),
      _PreferenceOption('formal', l10n.preferenceOccasionFormal),
      _PreferenceOption('travel', l10n.preferenceOccasionTravel),
      _PreferenceOption(_otherPreferenceId, l10n.preferenceOther),
    ];

List<_PreferenceOption> _styleOptions(AppLocalizations l10n) => [
      _PreferenceOption('clean_casual', l10n.preferenceStyleCleanCasual),
      _PreferenceOption('minimal', l10n.preferenceStyleMinimal),
      _PreferenceOption('street', l10n.preferenceStyleStreet),
      _PreferenceOption('elegant', l10n.preferenceStyleElegant),
      _PreferenceOption('sporty', l10n.preferenceStyleSporty),
      _PreferenceOption(_otherPreferenceId, l10n.preferenceOther),
    ];

List<_PreferenceOption> _seasonOptions(AppLocalizations l10n) => [
      _PreferenceOption('spring', l10n.preferenceSeasonSpring),
      _PreferenceOption('summer', l10n.preferenceSeasonSummer),
      _PreferenceOption('autumn', l10n.preferenceSeasonAutumn),
      _PreferenceOption('winter', l10n.preferenceSeasonWinter),
      _PreferenceOption('all_season', l10n.preferenceSeasonAllSeason),
      _PreferenceOption(_otherPreferenceId, l10n.preferenceOther),
    ];

List<_PreferenceOption> _colorOptions(AppLocalizations l10n) => [
      _PreferenceOption('black', l10n.preferenceColorBlack),
      _PreferenceOption('white', l10n.preferenceColorWhite),
      _PreferenceOption('gray', l10n.preferenceColorGray),
      _PreferenceOption('navy', l10n.preferenceColorNavy),
      _PreferenceOption('blue', l10n.preferenceColorBlue),
      _PreferenceOption('red', l10n.preferenceColorRed),
      _PreferenceOption('green', l10n.preferenceColorGreen),
      _PreferenceOption('beige', l10n.preferenceColorBeige),
      _PreferenceOption('brown', l10n.preferenceColorBrown),
      _PreferenceOption('pastel', l10n.preferenceColorPastel),
      _PreferenceOption(_otherPreferenceId, l10n.preferenceOther),
    ];

String _preferenceText(
  List<_PreferenceOption> options,
  Set<String> selectedIds,
  String otherText,
) {
  final optionLabels = {
    for (final option in options) option.id: option.label,
  };
  final labels = [
    for (final id in selectedIds)
      if (id != _otherPreferenceId && optionLabels[id] != null)
        optionLabels[id]!,
    if (selectedIds.contains(_otherPreferenceId) && otherText.trim().isNotEmpty)
      otherText.trim(),
  ];
  if (labels.isEmpty) {
    return options.first.label;
  }
  return labels.join(', ');
}

class _PreferenceMultiSelect extends StatelessWidget {
  const _PreferenceMultiSelect({
    required this.fieldKey,
    required this.label,
    required this.options,
    required this.selectedIds,
    required this.otherController,
    required this.enabled,
    required this.onChanged,
  });

  final String fieldKey;
  final String label;
  final List<_PreferenceOption> options;
  final Set<String> selectedIds;
  final TextEditingController otherController;
  final bool enabled;
  final ValueChanged<Set<String>> onChanged;

  void _toggle(String id) {
    final next = {...selectedIds};
    next.contains(id) ? next.remove(id) : next.add(id);
    onChanged(next);
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final showOther = selectedIds.contains(_otherPreferenceId);
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: InputDecorator(
        decoration: InputDecoration(labelText: label),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final option in options)
                  FilterChip(
                    key: ValueKey('$fieldKey-${option.id}'),
                    label: Text(option.label),
                    selected: selectedIds.contains(option.id),
                    onSelected: enabled ? (_) => _toggle(option.id) : null,
                  ),
              ],
            ),
            if (showOther) ...[
              const SizedBox(height: 10),
              TextField(
                key: ValueKey('$fieldKey-other-input'),
                controller: otherController,
                enabled: enabled,
                decoration: InputDecoration(
                  labelText: l10n.preferenceOtherInputLabel,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _AnchorPicker extends StatelessWidget {
  const _AnchorPicker({
    required this.itemsStream,
    required this.selectedIds,
    required this.pendingUploadedIds,
    required this.cache,
    required this.running,
    required this.uploading,
    required this.onToggle,
    required this.onUpload,
    required this.onReadyUploadedItems,
  });

  final Stream<List<ClosetItem>> itemsStream;
  final Set<String> selectedIds;
  final Set<String> pendingUploadedIds;
  final DownloadUrlCache cache;
  final bool running;
  final bool uploading;
  final ValueChanged<String> onToggle;
  final VoidCallback onUpload;
  final ValueChanged<Iterable<String>> onReadyUploadedItems;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                l10n.anchorItemsLabel,
                style: Theme.of(context).textTheme.labelLarge,
              ),
            ),
            TextButton.icon(
              onPressed: running || uploading ? null : onUpload,
              icon: const Icon(Icons.add_a_photo_outlined, size: 18),
              label: Text(uploading ? l10n.uploading : l10n.addItem),
            ),
          ],
        ),
        const SizedBox(height: 8),
        StreamBuilder<List<ClosetItem>>(
          stream: itemsStream,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return const SizedBox(
                height: 72,
                child: Center(child: CircularProgressIndicator()),
              );
            }
            final items = snapshot.data ?? const <ClosetItem>[];
            final readyUploadedIds = items
                .where((item) =>
                    pendingUploadedIds.contains(item.id) &&
                    item.status == ItemStatus.ready)
                .map((item) => item.id)
                .toList();
            if (readyUploadedIds.isNotEmpty) {
              WidgetsBinding.instance.addPostFrameCallback((_) {
                onReadyUploadedItems(readyUploadedIds);
              });
            }
            if (items.isEmpty) {
              return Text(
                l10n.noReadyAnchorItems,
                style: Theme.of(context).textTheme.bodySmall,
              );
            }
            return Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final item in items)
                  _AnchorTile(
                    key: ValueKey('anchor-${item.id}'),
                    item: item,
                    selected: selectedIds.contains(item.id),
                    processing: item.status == ItemStatus.processing,
                    cache: cache,
                    onTap: running || item.status != ItemStatus.ready
                        ? null
                        : () => onToggle(item.id),
                  ),
              ],
            );
          },
        ),
      ],
    );
  }
}

class _AnchorTile extends StatelessWidget {
  const _AnchorTile({
    super.key,
    required this.item,
    required this.selected,
    required this.processing,
    required this.cache,
    required this.onTap,
  });

  final ClosetItem item;
  final bool selected;
  final bool processing;
  final DownloadUrlCache cache;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final l10n = AppLocalizations.of(context)!;
    return Tooltip(
      message: processing ? l10n.analyzingItem : item.category ?? item.id,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(8),
        child: Container(
          width: 72,
          height: 72,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(8),
            border: Border.all(
              width: selected ? 2 : 1,
              color:
                  selected ? colorScheme.primary : colorScheme.outlineVariant,
            ),
          ),
          child: Stack(
            fit: StackFit.expand,
            children: [
              ClipRRect(
                borderRadius: BorderRadius.circular(7),
                child: Thumbnail(itemId: item.id, cache: cache),
              ),
              if (processing)
                Container(
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(7),
                    color: colorScheme.surface.withValues(alpha: 0.7),
                  ),
                  child: const Center(
                    child: SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    ),
                  ),
                ),
              if (selected)
                Positioned(
                  top: 4,
                  right: 4,
                  child: Icon(
                    Icons.check_circle,
                    size: 18,
                    color: colorScheme.primary,
                  ),
                ),
            ],
          ),
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
            const SizedBox(height: 12),
            if (error != null)
              Text(
                l10n.errorWithMessage(
                  userFacingErrorMessage(
                    error!,
                    LocaleScope.of(context).languageCode,
                  ),
                ),
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
    if (event.toolName == 'search_rakuten') {
      return _SearchRakutenPreview(event: event, l10n: l10n);
    }
    if (event.toolName == 'style_synthesizer') {
      return _StyleSynthesizerPreview(event: event, l10n: l10n);
    }
    if (event.toolName == 'transfer_to_agent') {
      final agentName =
          event.toolArgs?['agent_name'] as String? ?? event.text ?? '—';
      return _PreviewField(
          label: l10n.traceTargetAgent, child: Text(agentName));
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
      final colors = rawColors is List ? rawColors.cast<String>() : <String>[];
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
            _PreviewField(label: l10n.colors, child: _ChipRow(values: colors)),
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

class _SearchRakutenPreview extends StatelessWidget {
  const _SearchRakutenPreview({required this.event, required this.l10n});

  final AgentEvent event;
  final AppLocalizations l10n;

  @override
  Widget build(BuildContext context) {
    if (event.eventKind == 'tool_call') {
      final args = event.toolArgs ?? {};
      final query = args['query'] as String?;
      final category = args['category'] as String?;
      final requestedLimit = args['requestedLimit'];
      final effectiveLimit = args['effectiveLimit'] ?? args['limit'];
      final limitLabel = Localizations.localeOf(context).languageCode == 'ja'
          ? '取得上限'
          : 'Limit';
      final rawColors = args['colors'];
      final colors = rawColors is List ? rawColors.cast<String>() : <String>[];
      final rawTags = args['tags'];
      final tags = rawTags is List ? rawTags.cast<String>() : <String>[];

      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (query != null)
            _PreviewField(label: l10n.traceQuery, child: Text(query)),
          if (category != null)
            _PreviewField(label: l10n.category, child: Text(category)),
          if (effectiveLimit != null)
            _PreviewField(
              label: limitLabel,
              child: Text(
                requestedLimit != null && requestedLimit != effectiveLimit
                    ? '$requestedLimit -> $effectiveLimit'
                    : '$effectiveLimit',
              ),
            ),
          if (colors.isNotEmpty)
            _PreviewField(label: l10n.colors, child: _ChipRow(values: colors)),
          if (tags.isNotEmpty)
            _PreviewField(label: l10n.traceTags, child: _ChipRow(values: tags)),
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
        ...items.map((item) => _RakutenItemRow(item: item)),
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
          _PreviewField(label: l10n.traceItemCount, child: Text('$itemCount')),
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
                  ? Image.network(imageUrl,
                      fit: BoxFit.cover,
                      errorBuilder: (_, __, ___) => ColoredBox(
                            color: Theme.of(context)
                                .colorScheme
                                .surfaceContainerHighest,
                            child: const Icon(Icons.checkroom, size: 20),
                          ))
                  : ColoredBox(
                      color:
                          Theme.of(context).colorScheme.surfaceContainerHighest,
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
                  Text(category, style: Theme.of(context).textTheme.bodySmall),
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
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
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

class _RakutenItemRow extends StatelessWidget {
  const _RakutenItemRow({required this.item});

  final Map<String, dynamic> item;

  @override
  Widget build(BuildContext context) {
    final imageUrl = item['image_url'] as String?;
    final name = item['name'] as String?;
    final price = item['price'] as num?;
    final category = item['category'] as String?;
    final shopName = item['shop_name'] as String?;
    final tags = (item['tags'] as List?)?.cast<String>() ?? <String>[];
    final l10n = AppLocalizations.of(context)!;

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
                  ? Image.network(imageUrl,
                      fit: BoxFit.cover,
                      // Rakuten's thumbnail CDN serves images without CORS
                      // headers; see the matching workaround in CandidateCard.
                      webHtmlElementStrategy: WebHtmlElementStrategy.prefer,
                      errorBuilder: (_, __, ___) => ColoredBox(
                            color: Theme.of(context)
                                .colorScheme
                                .surfaceContainerHighest,
                            child: const Icon(Icons.checkroom, size: 20),
                          ))
                  : ColoredBox(
                      color:
                          Theme.of(context).colorScheme.surfaceContainerHighest,
                      child: const Icon(Icons.checkroom, size: 20),
                    ),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (name != null)
                  Text(name,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.bodySmall),
                if (price != null) ...[
                  const SizedBox(height: 2),
                  Text('¥$price', style: Theme.of(context).textTheme.bodySmall),
                ],
                if (category != null) ...[
                  const SizedBox(height: 2),
                  Text(category, style: Theme.of(context).textTheme.bodySmall),
                ],
                if (shopName != null) ...[
                  const SizedBox(height: 2),
                  Text(
                    '${l10n.traceShopName}: $shopName',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                  ),
                ],
                if (tags.isNotEmpty) ...[
                  const SizedBox(height: 2),
                  _ChipRow(values: tags),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class CandidatePanel extends StatelessWidget {
  const CandidatePanel({
    super.key,
    required this.candidates,
    required this.selectedIds,
    required this.savedIds,
    required this.importingIds,
    required this.running,
    required this.onChanged,
    required this.onGenerate,
    this.canGenerate = true,
    this.onImport,
  });

  final List<Map<String, dynamic>> candidates;
  final Set<String> selectedIds;
  final Set<String> savedIds;
  final Set<String> importingIds;
  final bool running;
  final bool canGenerate;
  final void Function(String id, bool selected) onChanged;
  final void Function(Map<String, dynamic> candidate)? onImport;
  final VoidCallback onGenerate;

  bool get _hasFlaggedCandidates => candidates.any(
        (item) => item['recommended'] == true || item['anchor'] == true,
      );

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
                  CandidateCard(
                    candidate: candidates[index],
                    recommended: _hasFlaggedCandidates
                        ? candidates[index]['recommended'] == true ||
                            candidates[index]['anchor'] == true
                        : index == 0,
                    selected: selectedIds.contains(_id(candidates[index])),
                    saved: savedIds.contains(_id(candidates[index])),
                    importing: importingIds.contains(_id(candidates[index])),
                    onChanged: (selected) =>
                        onChanged(_id(candidates[index]), selected),
                    onImport: onImport == null || running
                        ? null
                        : () => onImport!(candidates[index]),
                  ),
              ],
            ),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: running || !canGenerate || selectedIds.isEmpty
                  ? null
                  : onGenerate,
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

String userFacingErrorMessage(Object error, String languageCode) {
  final message = error is ApiException ? error.message : '$error';
  if (message.contains('Cannot select candidates from')) {
    return languageCode == 'ja'
        ? '候補の取得または生成準備に失敗したため、このセッションでは生成できません。もう一度最初から試してください。'
        : 'This session failed before generation could start. Please start again.';
  }
  return message;
}

class CandidateCard extends StatelessWidget {
  const CandidateCard({
    super.key,
    required this.candidate,
    required this.recommended,
    required this.selected,
    required this.onChanged,
    this.saved = false,
    this.importing = false,
    this.onImport,
  });

  final Map<String, dynamic> candidate;
  final bool recommended;
  final bool selected;
  final bool saved;
  final bool importing;
  final ValueChanged<bool> onChanged;
  final VoidCallback? onImport;

  bool get _isRakuten => candidate['source'] == 'RAKUTEN';

  @override
  Widget build(BuildContext context) {
    final imageUrl = candidate['image_url'] ?? candidate['imageUrl'];
    final l10n = AppLocalizations.of(context)!;
    final name = candidate['name'] as String?;
    final price = candidate['price'] as num?;
    final externalUrl = (candidate['affiliate_url'] ??
        candidate['affiliateUrl'] ??
        candidate['external_url'] ??
        candidate['externalUrl']) as String?;
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
                Image.network(
                  imageUrl,
                  height: 150,
                  fit: BoxFit.cover,
                  // Rakuten's thumbnail CDN serves images without CORS headers,
                  // so the CanvasKit byte-fetch path fails (statusCode 0).
                  // Render Rakuten images via an HTML <img>, which does not
                  // require CORS for display.
                  webHtmlElementStrategy: _isRakuten
                      ? WebHtmlElementStrategy.prefer
                      : WebHtmlElementStrategy.never,
                  errorBuilder: (_, __, ___) =>
                      const SizedBox(height: 150, child: Icon(Icons.checkroom)),
                )
              else
                const SizedBox(height: 150, child: Icon(Icons.checkroom)),
              CheckboxListTile(
                value: selected,
                onChanged: (value) => onChanged(value ?? false),
                title: Text(
                  name ?? candidate['category'] as String? ?? l10n.item,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
                subtitle: recommended ? Text(l10n.recommended) : null,
                controlAffinity: ListTileControlAffinity.leading,
                dense: true,
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(8, 0, 8, 8),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Chip(
                          label: Text(
                            _isRakuten ? l10n.sourceRakuten : l10n.myCloset,
                          ),
                          visualDensity: VisualDensity.compact,
                          materialTapTargetSize:
                              MaterialTapTargetSize.shrinkWrap,
                          labelStyle: Theme.of(context).textTheme.labelSmall,
                        ),
                        const Spacer(),
                        if (_isRakuten && externalUrl != null)
                          IconButton(
                            tooltip: l10n.openProductPage,
                            iconSize: 18,
                            visualDensity: VisualDensity.compact,
                            onPressed: () => launchUrl(
                              Uri.parse(externalUrl),
                              mode: LaunchMode.externalApplication,
                            ),
                            icon: const Icon(Icons.open_in_new),
                          ),
                      ],
                    ),
                    if (_isRakuten && price != null)
                      Text(
                        '¥$price',
                        style: Theme.of(context).textTheme.labelMedium,
                      ),
                    if (_isRakuten && onImport != null) ...[
                      const SizedBox(height: 4),
                      OutlinedButton.icon(
                        onPressed: saved || importing ? null : onImport,
                        icon: importing
                            ? const SizedBox(
                                width: 14,
                                height: 14,
                                child:
                                    CircularProgressIndicator(strokeWidth: 2),
                              )
                            : Icon(
                                saved
                                    ? Icons.bookmark_added
                                    : Icons.bookmark_add_outlined,
                                size: 16,
                              ),
                        label: Text(
                          saved ? l10n.savedAsInteresting : l10n.addToCloset,
                          style: Theme.of(context).textTheme.labelSmall,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Post-generation confirmation modal (default: all pre-checked) for saving
/// the Rakuten items used in an outfit into the closet as "Interesting".
class _SaveInterestingDialog extends StatefulWidget {
  const _SaveInterestingDialog({required this.candidates});

  final List<Map<String, dynamic>> candidates;

  static String _id(Map<String, dynamic> item) =>
      (item['item_id'] ?? item['itemId']) as String;

  @override
  State<_SaveInterestingDialog> createState() => _SaveInterestingDialogState();
}

class _SaveInterestingDialogState extends State<_SaveInterestingDialog> {
  late final Set<String> _checked =
      widget.candidates.map(_SaveInterestingDialog._id).toSet();

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    return AlertDialog(
      title: Text(l10n.saveInterestingDialogTitle),
      content: SizedBox(
        width: 360,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(l10n.saveInterestingDialogBody),
              const SizedBox(height: 12),
              for (final candidate in widget.candidates)
                CheckboxListTile(
                  value: _checked.contains(
                    _SaveInterestingDialog._id(candidate),
                  ),
                  onChanged: (value) => setState(() {
                    final id = _SaveInterestingDialog._id(candidate);
                    if (value ?? false) {
                      _checked.add(id);
                    } else {
                      _checked.remove(id);
                    }
                  }),
                  secondary: SizedBox(
                    width: 40,
                    height: 40,
                    child: _thumbnail(candidate),
                  ),
                  title: Text(
                    (candidate['name'] as String?) ??
                        (candidate['category'] as String?) ??
                        l10n.item,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  dense: true,
                  controlAffinity: ListTileControlAffinity.leading,
                ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context, <String>{}),
          child: Text(l10n.saveInterestingSkip),
        ),
        FilledButton(
          onPressed: () => Navigator.pop(context, _checked),
          child: Text(l10n.saveInterestingConfirm),
        ),
      ],
    );
  }

  Widget _thumbnail(Map<String, dynamic> candidate) {
    final imageUrl = candidate['image_url'] ?? candidate['imageUrl'];
    if (imageUrl is! String || imageUrl.isEmpty) {
      return const Icon(Icons.checkroom);
    }
    return ClipRRect(
      borderRadius: BorderRadius.circular(4),
      child: Image.network(
        imageUrl,
        fit: BoxFit.cover,
        // Rakuten's thumbnail CDN serves images without CORS headers; see
        // the matching workaround in CandidateCard.
        webHtmlElementStrategy: WebHtmlElementStrategy.prefer,
        errorBuilder: (_, __, ___) => const Icon(Icons.checkroom),
      ),
    );
  }
}

class _ResultPanel extends StatelessWidget {
  const _ResultPanel({
    required this.coordinateImageUrl,
    required this.completed,
    required this.running,
    required this.onStartNew,
  });

  final String? coordinateImageUrl;
  final bool completed;
  final bool running;
  final VoidCallback onStartNew;

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
              Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
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
                  if (completed) ...[
                    const SizedBox(height: 16),
                    _CompletionActions(
                      running: running,
                      onStartNew: onStartNew,
                    ),
                  ],
                ],
              ),
          ],
        ),
      ),
    );
  }
}

class _CompletionActions extends StatelessWidget {
  const _CompletionActions({
    required this.running,
    required this.onStartNew,
  });

  final bool running;
  final VoidCallback onStartNew;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    return DecoratedBox(
      decoration: BoxDecoration(
        border: Border.all(color: Theme.of(context).colorScheme.outlineVariant),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              l10n.coordinateCompletedTitle,
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 4),
            Text(
              l10n.coordinateCompletedBody,
              style: Theme.of(context).textTheme.bodySmall,
            ),
            const SizedBox(height: 12),
            Align(
              alignment: Alignment.centerRight,
              child: FilledButton.icon(
                onPressed: running ? null : onStartNew,
                icon: const Icon(Icons.add),
                label: Text(l10n.startNewCoordinate),
              ),
            ),
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

  String get detailText => const JsonEncoder.withIndent('  ').convert(toJson());

  String summary(AppLocalizations l10n) {
    if (toolName == 'search_closet' && eventKind == 'tool_result') {
      final raw = toolResult?['result'];
      final count = raw is List ? raw.length : 0;
      return l10n.traceSearchedCloset(agentName, count);
    }
    if (toolName == 'search_closet') {
      return l10n.traceSearchingCloset(agentName);
    }
    if (toolName == 'search_rakuten' && eventKind == 'tool_result') {
      final raw = toolResult?['result'];
      final count = raw is List ? raw.length : 0;
      return l10n.traceSearchedRakuten(agentName, count);
    }
    if (toolName == 'search_rakuten') {
      return l10n.traceSearchingRakuten(agentName);
    }
    if (toolName == 'style_synthesizer') {
      return eventKind == 'tool_result'
          ? l10n.traceGeneratedCoordinate(agentName)
          : l10n.traceGeneratingCoordinate(agentName);
    }
    return text ?? '$agentName · $eventKind';
  }
}
