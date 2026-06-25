import 'package:cloud_firestore/cloud_firestore.dart';

enum ItemStatus { processing, ready, error, unknown }

ItemStatus _parseStatus(Object? raw) {
  switch (raw) {
    case 'PROCESSING':
      return ItemStatus.processing;
    case 'READY':
      return ItemStatus.ready;
    case 'ERROR':
      return ItemStatus.error;
    default:
      return ItemStatus.unknown;
  }
}

/// In-memory model of `users/{uid}/closet/{itemId}` per §8.1.
class ClosetItem {
  ClosetItem({
    required this.id,
    required this.status,
    this.category,
    this.tags = const [],
    this.colors = const [],
    this.season,
    this.gender,
    this.createdAt,
  });

  final String id;
  final ItemStatus status;
  final String? category;
  final List<String> tags;
  final List<String> colors;
  final String? season;
  final String? gender;
  final DateTime? createdAt;

  static ClosetItem fromFirestore(String id, Map<String, dynamic> data) {
    final created = data['createdAt'];
    return ClosetItem(
      id: id,
      status: _parseStatus(data['status']),
      category: data['category'] as String?,
      tags: (data['tags'] as List?)?.cast<String>() ?? const [],
      colors: (data['colors'] as List?)?.cast<String>() ?? const [],
      season: data['season'] as String?,
      gender: data['gender'] as String?,
      createdAt: created is Timestamp ? created.toDate() : null,
    );
  }
}
