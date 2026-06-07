import 'package:http/http.dart' as http;
import 'package:image_picker/image_picker.dart';
import 'package:uuid/uuid.dart';

import '../api/api_client.dart';

/// Orchestrates one upload: pick → signed PUT → complete.
class UploadService {
  UploadService({ApiClient? api, ImagePicker? picker, http.Client? httpClient})
      : _api = api ?? ApiClient(),
        _picker = picker ?? ImagePicker(),
        _http = httpClient ?? http.Client();

  final ApiClient _api;
  final ImagePicker _picker;
  final http.Client _http;
  final _uuid = const Uuid();

  /// Returns the new `itemId` on success, or `null` if the user cancelled the
  /// picker. Throws [ClosetFullException] when the user is at the cap and any
  /// other exception for network failures.
  Future<String?> upload() async {
    final picked = await _picker.pickImage(source: ImageSource.gallery);
    if (picked == null) return null;
    final bytes = await picked.readAsBytes();
    final itemId = _uuid.v4();

    final uploadUrl = await _api.getUploadUrl(itemId);
    final putRes = await _http.put(
      Uri.parse(uploadUrl),
      headers: {'Content-Type': 'image/jpeg'},
      body: bytes,
    );
    if (putRes.statusCode != 200) {
      throw ApiException(putRes.statusCode, putRes.body);
    }
    await _api.completeUpload(itemId);
    return itemId;
  }
}
