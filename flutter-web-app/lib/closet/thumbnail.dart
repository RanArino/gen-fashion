import 'package:flutter/material.dart';

import '../api/api_client.dart';

/// Per-session cache of signed download URLs so the closet grid does not refetch
/// a URL on every rebuild. Presigned GET URLs outlive a typical browsing
/// session (1h TTL), so a single fetch per item is enough.
class DownloadUrlCache {
  DownloadUrlCache(this._api);
  final ApiClient _api;
  final Map<String, Future<String>> _cache = {};

  Future<String> urlFor(String itemId) =>
      _cache.putIfAbsent(itemId, () => _api.getDownloadUrl(itemId));

  void invalidate(String itemId) => _cache.remove(itemId);
}

class Thumbnail extends StatelessWidget {
  const Thumbnail({super.key, required this.itemId, required this.cache});

  final String itemId;
  final DownloadUrlCache cache;

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<String>(
      future: cache.urlFor(itemId),
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError || !snapshot.hasData) {
          return const ColoredBox(
            color: Color(0xFFEEEEEE),
            child: Center(child: Icon(Icons.broken_image)),
          );
        }
        return Image.network(
          snapshot.data!,
          fit: BoxFit.cover,
          errorBuilder: (_, __, ___) => const ColoredBox(
            color: Color(0xFFEEEEEE),
            child: Center(child: Icon(Icons.broken_image)),
          ),
        );
      },
    );
  }
}
