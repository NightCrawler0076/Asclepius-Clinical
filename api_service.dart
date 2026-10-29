// api_service.dart
//
// This app is just the FRONTEND. Whisper itself only runs in Python, so
// Flutter can't transcribe anything on its own — it uploads audio to a
// small FastAPI backend (see whisper_backend/main.py) and shows back
// whatever text comes out.
//
// Only one endpoint is used in the web build:
//   POST /transcribe/file  <- multipart audio file (mic recording OR a
//                              picked file — both modes upload the same way)
//
// (System/Device Audio mode is disabled in the web build — browsers can't
// do OS-level loopback capture, so there's nothing for this app to call.)
//
// Swap [baseUrl] for wherever that backend is running.

import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;

class ApiService {
  static const String baseUrl = 'http://localhost:8000';

  /// Uploads a recorded/picked audio file and returns the transcript text.
  /// Used by both the Mic mode and the Prerecorded-file mode.
  static Future<String> transcribeAudioFile(File audioFile) async {
    final uri = Uri.parse('$baseUrl/transcribe/file');
    final request = http.MultipartRequest('POST', uri)
      ..files.add(await http.MultipartFile.fromPath('audio', audioFile.path));

    final streamed = await request.send();
    final response = await http.Response.fromStream(streamed);

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return data['text'] as String? ?? '';
    }
    throw Exception('Transcription failed: ${response.statusCode}');
  }
}
