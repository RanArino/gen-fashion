import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/material.dart';

import '../api/api_client.dart';
import '../auth/auth_service.dart';
import '../l10n/app_localizations.dart';
import '../shared/attribution.dart';
import '../theme/app_theme.dart';
import 'closet_item.dart';
import 'thumbnail.dart';
import 'upload_service.dart';

const int _kMaxItems = 20;

class ClosetScreen extends StatefulWidget {
  const ClosetScreen({super.key, required this.uid, this.embedded = false});

  final String uid;
  final bool embedded;

  @override
  State<ClosetScreen> createState() => _ClosetScreenState();
}

class _ClosetScreenState extends State<ClosetScreen> {
  late final ApiClient _api = ApiClient();
  late final DownloadUrlCache _cache = DownloadUrlCache(_api);
  late final UploadService _uploads = UploadService(api: _api);
  final AuthService _auth = AuthService();
  bool _busy = false;

  Stream<QuerySnapshot<Map<String, dynamic>>> _stream() {
    return FirebaseFirestore.instance
        .collection('users')
        .doc(widget.uid)
        .collection('closet')
        .orderBy('createdAt', descending: true)
        .snapshots();
  }

  Future<void> _onUploadPressed() async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      final id = await _uploads.upload();
      if (!mounted) return;
      if (id == null) return;
      final l10n = AppLocalizations.of(context)!;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(l10n.uploadQueued)),
      );
    } on ClosetFullException {
      if (!mounted) return;
      final l10n = AppLocalizations.of(context)!;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(l10n.closetFull)),
      );
    } catch (e) {
      if (!mounted) return;
      final l10n = AppLocalizations.of(context)!;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(l10n.uploadFailed('$e'))),
      );
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _onDelete(ClosetItem item) async {
    final l10n = AppLocalizations.of(context)!;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(l10n.deleteItemQuestion),
        content: Text(l10n.deleteItemBody),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: Text(l10n.cancel),
          ),
          FilledButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: Text(l10n.delete),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      await _api.deleteItem(item.id);
      _cache.invalidate(item.id);
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(l10n.deleteFailed('$e'))),
      );
    }
  }

  Future<void> _onEdit(ClosetItem item) async {
    final l10n = AppLocalizations.of(context)!;
    final category = TextEditingController(text: item.category ?? '');
    final colors = TextEditingController(text: item.colors.join(', '));
    final season = TextEditingController(text: item.season ?? '');
    final tags = TextEditingController(text: item.tags.join(', '));
    var gender = item.gender ?? 'common';
    final saved = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: Text(l10n.editMetadata),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                    controller: category,
                    decoration: InputDecoration(labelText: l10n.category)),
                TextField(
                    controller: colors,
                    decoration: InputDecoration(labelText: l10n.colorsComma)),
                TextField(
                    controller: season,
                    decoration: InputDecoration(labelText: l10n.season)),
                TextField(
                    controller: tags,
                    decoration: InputDecoration(labelText: l10n.tagsComma)),
                DropdownButtonFormField<String>(
                  initialValue: gender,
                  decoration: InputDecoration(labelText: l10n.gender),
                  items: [
                    DropdownMenuItem(
                      value: 'common',
                      child: Text(l10n.genderCommon),
                    ),
                    DropdownMenuItem(
                      value: 'female',
                      child: Text(l10n.genderFemale),
                    ),
                    DropdownMenuItem(
                        value: 'male', child: Text(l10n.genderMale)),
                  ],
                  onChanged: (value) {
                    if (value != null) setDialogState(() => gender = value);
                  },
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(ctx, false),
                child: Text(l10n.cancel)),
            FilledButton(
                onPressed: () => Navigator.pop(ctx, true),
                child: Text(l10n.save)),
          ],
        ),
      ),
    );
    if (saved != true) return;
    List<String> values(String raw) => raw
        .split(',')
        .map((value) => value.trim())
        .where((value) => value.isNotEmpty)
        .toList();
    try {
      await _api.updateItemMetadata(item.id, {
        'category': category.text.trim(),
        'colors': values(colors.text),
        'season': season.text.trim(),
        'tags': values(tags.text),
        'gender': gender,
      });
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(l10n.updateFailed('$e'))),
      );
    } finally {
      category.dispose();
      colors.dispose();
      season.dispose();
      tags.dispose();
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final content = Column(
      children: [
        Expanded(child: _buildBody()),
        const AttributionFooter(),
      ],
    );
    if (widget.embedded) {
      return Stack(
        children: [
          content,
          Positioned(
            right: 16,
            bottom: 16,
            child: FloatingActionButton.extended(
              onPressed: _busy ? null : _onUploadPressed,
              icon: const Icon(Icons.add_a_photo),
              label: Text(_busy ? l10n.uploading : l10n.addItem),
            ),
          ),
        ],
      );
    }
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.closetTitle),
        actions: [
          StreamBuilder<QuerySnapshot<Map<String, dynamic>>>(
            stream: _stream(),
            builder: (context, snap) {
              final n = snap.data?.docs.length ?? 0;
              return Padding(
                padding: const EdgeInsets.symmetric(horizontal: 12),
                child: Center(child: Text('$n / $_kMaxItems')),
              );
            },
          ),
          IconButton(
            tooltip: l10n.sharedClosetAbout,
            onPressed: () => showSharedClosetAboutDialog(context),
            icon: const Icon(Icons.info_outline),
          ),
          IconButton(
            tooltip: l10n.signOut,
            onPressed: () => _auth.signOut(),
            icon: const Icon(Icons.logout),
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(child: _buildBody()),
          const AttributionFooter(),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _busy ? null : _onUploadPressed,
        icon: const Icon(Icons.add_a_photo),
        label: Text(_busy ? l10n.uploading : l10n.addItem),
      ),
    );
  }

  Widget _buildBody() {
    return StreamBuilder<QuerySnapshot<Map<String, dynamic>>>(
      stream: _stream(),
      builder: (context, snap) {
        if (snap.connectionState == ConnectionState.waiting) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snap.hasError) {
          return Center(
            child: Text(
              AppLocalizations.of(context)!.errorWithMessage('${snap.error}'),
            ),
          );
        }
        final docs = snap.data?.docs ?? const [];
        if (docs.isEmpty) {
          return const _EmptyState();
        }
        final items =
            docs.map((d) => ClosetItem.fromFirestore(d.id, d.data())).toList();
        return ClosetGrid(
          items: items,
          cache: _cache,
          onDelete: _onDelete,
          onEdit: _onEdit,
        );
      },
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    return Center(
      key: const ValueKey('empty-state'),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.checkroom, size: 64, color: AppColors.muted),
          const SizedBox(height: 12),
          Text(AppLocalizations.of(context)!.emptyCloset),
        ],
      ),
    );
  }
}

/// Pure grid widget used both by [ClosetScreen] and by widget tests (which
/// inject a list directly, bypassing Firestore).
class ClosetGrid extends StatelessWidget {
  const ClosetGrid({
    super.key,
    required this.items,
    required this.cache,
    this.onDelete,
    this.onEdit,
    this.thumbnailBuilder,
  });

  final List<ClosetItem> items;
  final DownloadUrlCache cache;
  final void Function(ClosetItem item)? onDelete;
  final void Function(ClosetItem item)? onEdit;

  /// Override for tests; defaults to a real network thumbnail.
  final Widget Function(BuildContext, ClosetItem)? thumbnailBuilder;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final cols = (constraints.maxWidth / 220).clamp(2, 6).toInt();
        return GridView.builder(
          padding: const EdgeInsets.all(12),
          gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: cols,
            childAspectRatio: 0.8,
            mainAxisSpacing: 12,
            crossAxisSpacing: 12,
          ),
          itemCount: items.length,
          itemBuilder: (context, i) {
            final item = items[i];
            return ClosetCard(
              item: item,
              thumbnail: thumbnailBuilder?.call(context, item) ??
                  Thumbnail(itemId: item.id, cache: cache),
              onDelete: onDelete == null ? null : () => onDelete!(item),
              onEdit: onEdit == null ? null : () => onEdit!(item),
            );
          },
        );
      },
    );
  }
}

class ClosetCard extends StatelessWidget {
  const ClosetCard({
    super.key,
    required this.item,
    required this.thumbnail,
    this.onDelete,
    this.onEdit,
  });

  final ClosetItem item;
  final Widget thumbnail;
  final VoidCallback? onDelete;
  final VoidCallback? onEdit;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    return Card(
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Expanded(
            child: Stack(
              children: [
                Positioned.fill(child: thumbnail),
                Positioned(
                  top: 8,
                  left: 8,
                  child: StatusBadge(status: item.status),
                ),
                if (onDelete != null)
                  Positioned(
                    top: 4,
                    right: 4,
                    child: IconButton(
                      tooltip: l10n.deleteTooltip,
                      iconSize: 20,
                      onPressed: onDelete,
                      icon:
                          const Icon(Icons.delete_outline, color: Colors.white),
                    ),
                  ),
                if (onEdit != null && item.status == ItemStatus.ready)
                  Positioned(
                    top: 4,
                    right: 44,
                    child: IconButton(
                      tooltip: l10n.editMetadataTooltip,
                      iconSize: 20,
                      onPressed: onEdit,
                      icon:
                          const Icon(Icons.edit_outlined, color: Colors.white),
                    ),
                  ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(8),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (item.status == ItemStatus.ready) ...[
                  Text(
                    item.category ?? l10n.unknown,
                    style: Theme.of(context).textTheme.titleSmall,
                  ),
                  if (item.tags.isNotEmpty)
                    Text(
                      item.tags.take(3).join(', '),
                      style: Theme.of(context).textTheme.bodySmall,
                      overflow: TextOverflow.ellipsis,
                    ),
                  Text(
                    [
                      if (item.gender != null) item.gender,
                      if (item.season != null) item.season,
                      if (item.colors.isNotEmpty) item.colors.join('/'),
                    ].whereType<String>().join(' · '),
                    style: Theme.of(context).textTheme.bodySmall,
                    overflow: TextOverflow.ellipsis,
                  ),
                ] else if (item.status == ItemStatus.processing)
                  Text(l10n.analyzing)
                else if (item.status == ItemStatus.error)
                  Text(l10n.analysisFailed),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class StatusBadge extends StatelessWidget {
  const StatusBadge({super.key, required this.status});
  final ItemStatus status;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    late final Color bg;
    late final String label;
    late final Widget icon;
    switch (status) {
      case ItemStatus.processing:
        bg = AppColors.accent;
        label = l10n.statusProcessing;
        icon = const SizedBox(
          width: 12,
          height: 12,
          child: CircularProgressIndicator(
            strokeWidth: 2,
            valueColor: AlwaysStoppedAnimation(Colors.white),
          ),
        );
        break;
      case ItemStatus.ready:
        bg = AppColors.success;
        label = l10n.statusReady;
        icon = const Icon(Icons.check_circle, size: 14, color: Colors.white);
        break;
      case ItemStatus.error:
        bg = AppColors.error;
        label = l10n.statusError;
        icon = const Icon(Icons.error, size: 14, color: Colors.white);
        break;
      case ItemStatus.unknown:
        bg = AppColors.tertiary;
        label = l10n.statusUnknown;
        icon = const Icon(Icons.help, size: 14, color: Colors.white);
        break;
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          icon,
          const SizedBox(width: 6),
          Text(
            label,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 11,
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
    );
  }
}
