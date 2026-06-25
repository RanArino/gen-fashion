import 'package:fetch_client/fetch_client.dart';
import 'package:http/http.dart' as http;

/// On Flutter Web, `package:http`'s default `BrowserClient` is XHR-backed and
/// only completes the response stream once the connection closes — which never
/// happens incrementally for SSE. `FetchClient` reads the Fetch API response
/// body as a `ReadableStream`, delivering `text/event-stream` chunks as they
/// arrive, while still allowing the `Authorization` header (which native
/// `EventSource` cannot set).
http.Client createStreamingClient() => FetchClient(mode: RequestMode.cors);
