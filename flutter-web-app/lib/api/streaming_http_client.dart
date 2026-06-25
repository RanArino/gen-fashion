import 'package:http/http.dart' as http;

/// Returns an HTTP client used for the long-lived SSE request.
///
/// On non-web platforms the default client already streams response bodies
/// incrementally via `Client.send`, so the standard client is sufficient.
http.Client createStreamingClient() => http.Client();
