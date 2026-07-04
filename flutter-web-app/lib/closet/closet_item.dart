import 'package:cloud_firestore/cloud_firestore.dart';

enum ItemStatus { processing, ready, error, unknown }

/// Ownership classification (MK): analysis status stays separate.
enum ItemOwnership { owned, interesting }

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

ItemOwnership _parseOwnership(Object? raw) {
  // Pre-MK documents have no ownershipStatus; they are user uploads.
  return raw == 'INTERESTING' ? ItemOwnership.interesting : ItemOwnership.owned;
}

/// In-memory model of `users/{uid}/closet/{itemId}` per §8.1.
class ClosetItem {
  ClosetItem({
    required this.id,
    required this.status,
    this.ownership = ItemOwnership.owned,
    this.origin,
    this.externalUrl,
    this.affiliateUrl,
    this.price,
    this.category,
    this.tags = const [],
    this.colors = const [],
    this.season,
    this.gender,
    this.createdAt,
  });

  final String id;
  final ItemStatus status;
  final ItemOwnership ownership;
  final String? origin;
  final String? externalUrl;
  final String? affiliateUrl;
  final num? price;
  final String? category;
  final List<String> tags;
  final List<String> colors;
  final String? season;
  final String? gender;
  final DateTime? createdAt;

  /// Product page link, preferring the affiliate link when present.
  String? get productUrl => affiliateUrl ?? externalUrl;

  static ClosetItem fromFirestore(String id, Map<String, dynamic> data) {
    final created = data['createdAt'];
    return ClosetItem(
      id: id,
      status: _parseStatus(data['status']),
      ownership: _parseOwnership(data['ownershipStatus']),
      origin: data['origin'] as String?,
      externalUrl: data['externalUrl'] as String?,
      affiliateUrl: data['affiliateUrl'] as String?,
      price: data['price'] as num?,
      category: data['category'] as String?,
      tags: (data['tags'] as List?)?.cast<String>() ?? const [],
      colors: (data['colors'] as List?)?.cast<String>() ?? const [],
      season: data['season'] as String?,
      gender: data['gender'] as String?,
      createdAt: created is Timestamp ? created.toDate() : null,
    );
  }
}
