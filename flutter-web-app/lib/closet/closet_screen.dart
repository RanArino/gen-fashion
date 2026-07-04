import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../api/api_client.dart';
import '../auth/auth_service.dart';
import '../l10n/app_localizations.dart';
import '../shared/help_dialog.dart';
import '../theme/app_theme.dart';
import 'closet_item.dart';
import 'thumbnail.dart';
import 'upload_service.dart';

const int _kMaxItems = 20;

/// Applies the ownership/category filters to [items]. Pure function so it
/// can be unit-tested without a widget tree.
List<ClosetItem> applyClosetFilters(
  List<ClosetItem> items, {
  ItemOwnership? ownership,
  String? category,
}) {
  return items.where((item) {
    if (ownership != null && item.ownership != ownership) return false;
    if (category != null && item.category != category) return false;
    return true;
  }).toList();
}

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
  ItemOwnership? _ownershipFilter;
  String? _categoryFilter;

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
    var ownership =
        item.ownership == ItemOwnership.interesting ? 'INTERESTING' : 'OWNED';
    final saved = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: Text(l10n.editMetadata),
          content: SizedBox(
            width: 360,
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextField(
                      controller: category,
                      decoration: InputDecoration(labelText: l10n.category)),
                  const SizedBox(height: 12),
                  TextField(
                      controller: colors,
                      decoration:
                          InputDecoration(labelText: l10n.colorsComma)),
                  const SizedBox(height: 12),
                  TextField(
                      controller: season,
                      decoration: InputDecoration(labelText: l10n.season)),
                  const SizedBox(height: 12),
                  TextField(
                      controller: tags,
                      decoration: InputDecoration(labelText: l10n.tagsComma)),
                  const SizedBox(height: 12),
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
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    initialValue: ownership,
                    decoration: InputDecoration(labelText: l10n.ownership),
                    items: [
                      DropdownMenuItem(
                        value: 'OWNED',
                        child: Text(l10n.ownershipOwned),
                      ),
                      DropdownMenuItem(
                        value: 'INTERESTING',
                        child: Text(l10n.ownershipInteresting),
                      ),
                    ],
                    onChanged: (value) {
                      if (value != null) {
                        setDialogState(() => ownership = value);
                      }
                    },
                  ),
                  const SizedBox(height: 4),
                  Text(
                    ownership == 'INTERESTING'
                        ? l10n.ownershipInterestingHint
                        : l10n.ownershipOwnedHint,
                    style: Theme.of(context).textTheme.labelSmall?.copyWith(
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                  ),
                ],
              ),
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
        'ownershipStatus': ownership,
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
    if (widget.embedded) {
      return Stack(
        children: [
          _buildBody(),
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
            tooltip: l10n.appHelpTooltip,
            onPressed: () => showAppHelpDialog(
              context,
              initialSection: helpSectionCloset,
            ),
            icon: const Icon(Icons.info_outline),
          ),
          IconButton(
            tooltip: l10n.signOut,
            onPressed: () => _auth.signOut(),
            icon: const Icon(Icons.logout),
          ),
        ],
      ),
      body: _buildBody(),
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
        final ownershipFiltered =
            applyClosetFilters(items, ownership: _ownershipFilter);
        final categories = _distinctCategories(ownershipFiltered);
        if (_categoryFilter != null && !categories.contains(_categoryFilter)) {
          _categoryFilter = null;
        }
        final filtered =
            applyClosetFilters(ownershipFiltered, category: _categoryFilter);
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            ClosetFilterBar(
              categories: categories,
              ownershipFilter: _ownershipFilter,
              categoryFilter: _categoryFilter,
              onOwnershipChanged: (value) => setState(() {
                _ownershipFilter = value;
                _categoryFilter = null;
              }),
              onCategoryChanged: (value) =>
                  setState(() => _categoryFilter = value),
            ),
            Expanded(
              child: filtered.isEmpty
                  ? const _NoFilterMatchState()
                  : ClosetGrid(
                      items: filtered,
                      cache: _cache,
                      onDelete: _onDelete,
                      onEdit: _onEdit,
                    ),
            ),
          ],
        );
      },
    );
  }
}

List<String> _distinctCategories(List<ClosetItem> items) {
  final seen = <String>{};
  for (final item in items) {
    final category = item.category;
    if (category != null && category.trim().isNotEmpty) {
      seen.add(category);
    }
  }
  final sorted = seen.toList()..sort();
  return sorted;
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
          const SizedBox(height: 8),
          Text(
            AppLocalizations.of(context)!.emptyClosetHelpHint,
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
          ),
        ],
      ),
    );
  }
}

class _NoFilterMatchState extends StatelessWidget {
  const _NoFilterMatchState();

  @override
  Widget build(BuildContext context) {
    return Center(
      key: const ValueKey('no-filter-match-state'),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.filter_alt_off, size: 64, color: AppColors.muted),
          const SizedBox(height: 12),
          Text(AppLocalizations.of(context)!.noItemsMatchFilter),
        ],
      ),
    );
  }
}

/// Ownership + category filter bar shown above [ClosetGrid]. Stateless:
/// [ClosetScreen] owns the filter selection and passes down the distinct
/// category values already narrowed by the current ownership filter.
class ClosetFilterBar extends StatelessWidget {
  const ClosetFilterBar({
    super.key,
    required this.categories,
    required this.ownershipFilter,
    required this.categoryFilter,
    required this.onOwnershipChanged,
    required this.onCategoryChanged,
  });

  final List<String> categories;
  final ItemOwnership? ownershipFilter;
  final String? categoryFilter;
  final ValueChanged<ItemOwnership?> onOwnershipChanged;
  final ValueChanged<String?> onCategoryChanged;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(12, 12, 12, 12),
      decoration: const BoxDecoration(
        color: AppColors.panel,
        border: Border(bottom: BorderSide(color: AppColors.border)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Wrap(
            crossAxisAlignment: WrapCrossAlignment.center,
            spacing: 16,
            runSpacing: 8,
            children: [
              SegmentedButton<ItemOwnership?>(
                segments: [
                  ButtonSegment(value: null, label: Text(l10n.filterAll)),
                  ButtonSegment(
                    value: ItemOwnership.owned,
                    label: Text(l10n.ownershipOwned),
                    tooltip: l10n.ownershipOwnedHint,
                  ),
                  ButtonSegment(
                    value: ItemOwnership.interesting,
                    label: Text(l10n.ownershipInteresting),
                    tooltip: l10n.ownershipInterestingHint,
                  ),
                ],
                selected: {ownershipFilter},
                onSelectionChanged: (values) =>
                    onOwnershipChanged(values.first),
                style: const ButtonStyle(
                  visualDensity: VisualDensity.compact,
                ),
              ),
              if (categories.isNotEmpty)
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    FilterChip(
                      label: Text(l10n.filterAll),
                      selected: categoryFilter == null,
                      onSelected: (_) => onCategoryChanged(null),
                    ),
                    for (final category in categories)
                      FilterChip(
                        label: Text(category),
                        selected: categoryFilter == category,
                        onSelected: (selected) =>
                            onCategoryChanged(selected ? category : null),
                      ),
                  ],
                ),
            ],
          ),
          if (ownershipFilter != null) ...[
            const SizedBox(height: 4),
            Text(
              ownershipFilter == ItemOwnership.owned
                  ? l10n.ownershipOwnedHint
                  : l10n.ownershipInterestingHint,
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
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
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      StatusBadge(status: item.status),
                      const SizedBox(height: 4),
                      OwnershipChip(ownership: item.ownership),
                    ],
                  ),
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
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          item.category ?? l10n.unknown,
                          style: Theme.of(context).textTheme.titleSmall,
                        ),
                      ),
                      if (item.ownership == ItemOwnership.interesting &&
                          item.productUrl != null)
                        IconButton(
                          tooltip: l10n.openProductPage,
                          iconSize: 18,
                          visualDensity: VisualDensity.compact,
                          padding: EdgeInsets.zero,
                          constraints: const BoxConstraints(),
                          onPressed: () => launchUrl(
                            Uri.parse(item.productUrl!),
                            mode: LaunchMode.externalApplication,
                          ),
                          icon: const Icon(Icons.open_in_new),
                        ),
                    ],
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

/// Ownership classification chip (MK): distinct from the analysis
/// [StatusBadge], never shows a spinner.
class OwnershipChip extends StatelessWidget {
  const OwnershipChip({super.key, required this.ownership});
  final ItemOwnership ownership;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final interesting = ownership == ItemOwnership.interesting;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: interesting ? AppColors.accent : AppColors.tertiary,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            interesting ? Icons.bookmark : Icons.check,
            size: 14,
            color: Colors.white,
          ),
          const SizedBox(width: 6),
          Text(
            interesting ? l10n.ownershipInteresting : l10n.ownershipOwned,
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
