class SessionHistoryItem {
  const SessionHistoryItem({
    required this.sessionId,
    required this.status,
    required this.selectedItems,
    this.createdAt,
    this.completedAt,
    this.source,
    this.sharedClosetId,
    this.coordinateImageUrl,
  });

  final String sessionId;
  final String status;
  final DateTime? createdAt;
  final DateTime? completedAt;
  final String? source;
  final String? sharedClosetId;
  final List<HistorySelectedItem> selectedItems;
  final String? coordinateImageUrl;

  factory SessionHistoryItem.fromJson(Map<String, dynamic> json) {
    final styleResult = json['style_result'] as Map<String, dynamic>?;
    return SessionHistoryItem(
      sessionId: json['session_id'] as String,
      status: json['status'] as String,
      createdAt: _parseDateTime(json['created_at']),
      completedAt: _parseDateTime(json['completed_at']),
      source: json['source'] as String?,
      sharedClosetId: json['shared_closet_id'] as String?,
      selectedItems: (json['selected_items'] as List<dynamic>? ?? const [])
          .map(
            (item) => HistorySelectedItem.fromJson(
              item as Map<String, dynamic>,
            ),
          )
          .toList(),
      coordinateImageUrl: styleResult?['coordinate_image_url'] as String?,
    );
  }

  static DateTime? _parseDateTime(Object? value) {
    return value is String ? DateTime.parse(value) : null;
  }
}

class HistorySelectedItem {
  const HistorySelectedItem({
    required this.itemId,
    required this.imageUrl,
    this.category,
    this.gender,
  });

  final String itemId;
  final String imageUrl;
  final String? category;
  final String? gender;

  factory HistorySelectedItem.fromJson(Map<String, dynamic> json) {
    return HistorySelectedItem(
      itemId: json['item_id'] as String,
      imageUrl: json['image_url'] as String,
      category: json['category'] as String?,
      gender: json['gender'] as String?,
    );
  }
}
