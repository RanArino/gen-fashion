import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/material.dart';

import '../api/api_client.dart';
import '../auth/auth_service.dart';
import '../shared/attribution.dart';
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
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Upload queued; analyzing…')),
      );
    } on ClosetFullException {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Closet is full (20 items).')),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Upload failed: $e')),
      );
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _onDelete(ClosetItem item) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete item?'),
        content: const Text('This removes the item from your closet.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('Delete'),
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
        SnackBar(content: Text('Delete failed: $e')),
      );
    }
  }

  Future<void> _onEdit(ClosetItem item) async {
    final category = TextEditingController(text: item.category ?? '');
    final colors = TextEditingController(text: item.colors.join(', '));
    final season = TextEditingController(text: item.season ?? '');
    final tags = TextEditingController(text: item.tags.join(', '));
    var gender = item.gender ?? 'common';
    final saved = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('Edit item metadata'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                    controller: category,
                    decoration: const InputDecoration(labelText: 'Category')),
                TextField(
                    controller: colors,
                    decoration: const InputDecoration(
                        labelText: 'Colors (comma separated)')),
                TextField(
                    controller: season,
                    decoration: const InputDecoration(labelText: 'Season')),
                TextField(
                    controller: tags,
                    decoration: const InputDecoration(
                        labelText: 'Tags (comma separated)')),
                DropdownButtonFormField<String>(
                  initialValue: gender,
                  decoration: const InputDecoration(labelText: 'Gender'),
                  items: const [
                    DropdownMenuItem(value: 'common', child: Text('Common')),
                    DropdownMenuItem(value: 'female', child: Text('Female')),
                    DropdownMenuItem(value: 'male', child: Text('Male')),
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
                child: const Text('Cancel')),
            FilledButton(
                onPressed: () => Navigator.pop(ctx, true),
                child: const Text('Save')),
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
        SnackBar(content: Text('Update failed: $e')),
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
              label: _busy ? const Text('Uploading…') : const Text('Add item'),
            ),
          ),
        ],
      );
    }
    return Scaffold(
      appBar: AppBar(
        title: const Text('Closet'),
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
            tooltip: '共有クローゼットについて',
            onPressed: () => showSharedClosetAboutDialog(context),
            icon: const Icon(Icons.info_outline),
          ),
          IconButton(
            tooltip: 'Sign out',
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
        label: _busy ? const Text('Uploading…') : const Text('Add item'),
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
          return Center(child: Text('Error: ${snap.error}'));
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
    return const Center(
      key: ValueKey('empty-state'),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.checkroom, size: 64, color: Colors.grey),
          SizedBox(height: 12),
          Text('Add your first item to get started.'),
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
                      tooltip: 'Delete',
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
                      tooltip: 'Edit metadata',
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
                    item.category ?? 'Unknown',
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
                  const Text('Analyzing…')
                else if (item.status == ItemStatus.error)
                  const Text('Analysis failed'),
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
    late final Color bg;
    late final String label;
    late final Widget icon;
    switch (status) {
      case ItemStatus.processing:
        bg = Colors.amber.shade700;
        label = 'PROCESSING';
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
        bg = Colors.green.shade600;
        label = 'READY';
        icon = const Icon(Icons.check_circle, size: 14, color: Colors.white);
        break;
      case ItemStatus.error:
        bg = Colors.red.shade600;
        label = 'ERROR';
        icon = const Icon(Icons.error, size: 14, color: Colors.white);
        break;
      case ItemStatus.unknown:
        bg = Colors.grey.shade600;
        label = 'UNKNOWN';
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
