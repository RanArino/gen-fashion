import 'package:flutter/material.dart';

import '../api/api_client.dart';
import '../l10n/app_localizations.dart';
import '../shared/attribution.dart';

class SharedClosetGallery extends StatefulWidget {
  const SharedClosetGallery({super.key, ApiClient? api}) : _api = api;

  final ApiClient? _api;

  @override
  State<SharedClosetGallery> createState() => _SharedClosetGalleryState();
}

class _SharedClosetGalleryState extends State<SharedClosetGallery> {
  late final ApiClient _api = widget._api ?? ApiClient();
  List<Map<String, dynamic>> _closets = [];
  List<Map<String, dynamic>> _items = [];
  String? _selectedClosetId;
  Object? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loadClosets();
  }

  Future<void> _loadClosets() async {
    try {
      final closets = await _api.listSharedClosets();
      final selected =
          closets.isEmpty ? null : closets.first['closetId'] as String;
      final items = selected == null
          ? <Map<String, dynamic>>[]
          : await _api.listSharedClosetItems(selected);
      if (!mounted) return;
      setState(() {
        _closets = closets;
        _selectedClosetId = selected;
        _items = items;
        _loading = false;
      });
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = e;
          _loading = false;
        });
      }
    }
  }

  Future<void> _select(String closetId) async {
    setState(() {
      _selectedClosetId = closetId;
      _loading = true;
      _error = null;
    });
    try {
      final items = await _api.listSharedClosetItems(closetId);
      if (mounted) {
        setState(() {
          _items = items;
          _loading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = e;
          _loading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    if (_error != null) {
      return Center(child: Text(l10n.sharedGalleryError('$_error')));
    }
    if (_loading && _closets.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(16),
          child: DropdownButtonFormField<String>(
            initialValue: _selectedClosetId,
            decoration: InputDecoration(
              labelText: l10n.sharedCloset,
            ),
            items: _closets.map((closet) {
              final id = closet['closetId'] as String;
              return DropdownMenuItem(
                value: id,
                child: Text(closet['displayName'] as String? ?? id),
              );
            }).toList(),
            onChanged: _loading
                ? null
                : (value) {
                    if (value != null) _select(value);
                  },
          ),
        ),
        Expanded(
          child: _loading
              ? const Center(child: CircularProgressIndicator())
              : GridView.builder(
                  padding: const EdgeInsets.all(12),
                  gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
                    maxCrossAxisExtent: 240,
                    childAspectRatio: 0.65,
                    mainAxisSpacing: 12,
                    crossAxisSpacing: 12,
                  ),
                  itemCount: _items.length,
                  itemBuilder: (context, index) {
                    final item = _items[index];
                    return Card(
                      clipBehavior: Clip.antiAlias,
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          Expanded(
                            child: Image.network(
                              item['imageUrl'] as String? ?? '',
                              fit: BoxFit.cover,
                              errorBuilder: (_, __, ___) =>
                                  const Icon(Icons.checkroom),
                            ),
                          ),
                          Padding(
                            padding: const EdgeInsets.all(8),
                            child: Text(
                              [
                                item['category'],
                                item['gender'],
                                item['season'],
                                ...((item['colors'] as List?) ?? const []),
                                ...((item['tags'] as List?) ?? const []),
                              ].whereType<String>().join(' · '),
                              maxLines: 4,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ],
                      ),
                    );
                  },
                ),
        ),
        const AttributionFooter(),
      ],
    );
  }
}
