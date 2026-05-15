# Flutter Voice Integration Guide

## Overview

This document explains how to integrate the backend voice feature into the Flutter application.

Supported backend voice flows:

- Speech to Text: `STT`
- Text to Speech: `TTS`
- Voice Chat with RAG answer

Base route:

```text
/api/v1/voice
```

## Endpoints

### 1. Speech to Text

```http
POST /api/v1/voice/stt
```

Request type:

- `multipart/form-data`

Fields:

- `audio`: required file
- `language`: optional string such as `en` or `ar`

Success response:

```json
{
  "signal": "stt_success",
  "text": "hello world",
  "language": "en",
  "duration_ms": 2140
}
```

Timeout response:

```json
{
  "signal": "stt_timeout",
  "message": "Speech-to-text exceeded 300 seconds"
}
```

Failure response:

```json
{
  "signal": "stt_failed",
  "message": "error details"
}
```

### 2. Text to Speech

```http
POST /api/v1/voice/tts
```

Request type:

- `application/json`

Body:

```json
{
  "text": "Hello from Flutter",
  "format": "wav"
}
```

Important notes:

- only `wav` is currently supported
- success response is binary audio, not JSON
- response content type is:

```text
audio/wav
```

Failure response:

```json
{
  "signal": "tts_failed",
  "message": "error details"
}
```

### 3. Voice Chat

```http
POST /api/v1/voice/chat/{project_id}
```

Request type:

- `multipart/form-data`

Path params:

- `project_id`: required integer

Fields:

- `audio`: required file
- `limit`: optional integer, default `30`
- `return_audio_base64`: optional boolean, default `true`
- `language`: optional string

Success response when `return_audio_base64=true`:

```json
{
  "signal": "voice_chat_success",
  "transcript": "what is the project about",
  "answer": "project answer here",
  "audio_base64": "UklGRi...",
  "audio_mime_type": "audio/wav",
  "full_prompt": "...",
  "chat_history": []
}
```

Success response when `return_audio_base64=false`:

- binary `audio/wav`
- response header includes:

```text
X-Transcript: recognized speech text
```

Timeout response:

```json
{
  "signal": "voice_chat_timeout",
  "message": "Speech-to-text exceeded 300 seconds"
}
```

Failure response:

```json
{
  "signal": "voice_chat_failed",
  "message": "error details"
}
```

Possible additional backend responses:

- `project not found`
- `rag_answer_failed`
- `stt_failed`

## Backend Signals Used by Flutter

The Flutter app should handle these signals:

- `stt_success`
- `stt_failed`
- `stt_timeout`
- `tts_failed`
- `voice_chat_success`
- `voice_chat_failed`
- `voice_chat_timeout`
- `rag_answer_failed`
- `project not found`

## Recommended Flutter Packages

- `dio`: HTTP client
- `record`: audio recording
- `path_provider`: temp file storage
- `audioplayers` or `just_audio`: audio playback
- `permission_handler`: microphone permission

## Suggested Dart Models

```dart
class SttResponse {
  final String signal;
  final String text;
  final String? language;
  final int? durationMs;

  SttResponse({
    required this.signal,
    required this.text,
    required this.language,
    required this.durationMs,
  });

  factory SttResponse.fromJson(Map<String, dynamic> json) {
    return SttResponse(
      signal: json['signal'] as String,
      text: json['text'] as String? ?? '',
      language: json['language'] as String?,
      durationMs: json['duration_ms'] as int?,
    );
  }
}

class VoiceChatResponse {
  final String signal;
  final String transcript;
  final String answer;
  final String? audioBase64;
  final String? audioMimeType;
  final dynamic fullPrompt;
  final dynamic chatHistory;

  VoiceChatResponse({
    required this.signal,
    required this.transcript,
    required this.answer,
    this.audioBase64,
    this.audioMimeType,
    this.fullPrompt,
    this.chatHistory,
  });

  factory VoiceChatResponse.fromJson(Map<String, dynamic> json) {
    return VoiceChatResponse(
      signal: json['signal'] as String,
      transcript: json['transcript'] as String? ?? '',
      answer: json['answer'] as String? ?? '',
      audioBase64: json['audio_base64'] as String?,
      audioMimeType: json['audio_mime_type'] as String?,
      fullPrompt: json['full_prompt'],
      chatHistory: json['chat_history'],
    );
  }
}
```

## Example Dio Service

```dart
import 'dart:convert';
import 'dart:io';

import 'package:dio/dio.dart';

class VoiceApiService {
  final Dio dio;
  final String baseUrl;

  VoiceApiService({
    required this.dio,
    required this.baseUrl,
  });

  Future<SttResponse> speechToText({
    required File audioFile,
    String? language,
  }) async {
    final formData = FormData.fromMap({
      'audio': await MultipartFile.fromFile(
        audioFile.path,
        filename: audioFile.uri.pathSegments.last,
      ),
      if (language != null && language.isNotEmpty) 'language': language,
    });

    final response = await dio.post(
      '$baseUrl/api/v1/voice/stt',
      data: formData,
    );

    return SttResponse.fromJson(response.data as Map<String, dynamic>);
  }

  Future<List<int>> textToSpeech({
    required String text,
  }) async {
    final response = await dio.post<List<int>>(
      '$baseUrl/api/v1/voice/tts',
      data: {
        'text': text,
        'format': 'wav',
      },
      options: Options(
        responseType: ResponseType.bytes,
        headers: {
          HttpHeaders.contentTypeHeader: 'application/json',
        },
      ),
    );

    return response.data ?? <int>[];
  }

  Future<VoiceChatResponse> voiceChat({
    required int projectId,
    required File audioFile,
    int limit = 30,
    bool returnAudioBase64 = true,
    String? language,
  }) async {
    final formData = FormData.fromMap({
      'audio': await MultipartFile.fromFile(
        audioFile.path,
        filename: audioFile.uri.pathSegments.last,
      ),
      'limit': limit.toString(),
      'return_audio_base64': returnAudioBase64.toString(),
      if (language != null && language.isNotEmpty) 'language': language,
    });

    final response = await dio.post(
      '$baseUrl/api/v1/voice/chat/$projectId',
      data: formData,
    );

    return VoiceChatResponse.fromJson(response.data as Map<String, dynamic>);
  }

  List<int> decodeBase64Audio(String base64Audio) {
    return base64Decode(base64Audio);
  }
}
```

## Recording Flow in Flutter

Suggested mobile flow:

1. Request microphone permission.
2. Start recording to a local file.
3. Stop recording.
4. Upload the file using `speechToText` or `voiceChat`.
5. If needed, save returned TTS/voice-chat audio to a temp `.wav` file and play it.

## Save and Play Returned WAV

Example helper:

```dart
import 'dart:io';

import 'package:path_provider/path_provider.dart';

Future<File> saveWavBytes(List<int> bytes, String fileName) async {
  final dir = await getTemporaryDirectory();
  final file = File('${dir.path}/$fileName');
  await file.writeAsBytes(bytes, flush: true);
  return file;
}
```

For `voice_chat_success` with `audio_base64`:

1. decode base64
2. write bytes to temp file
3. play the file

## UI Recommendations

Suggested screens or widgets:

- `VoiceRecorderWidget`
- `SpeechToTextPage`
- `TextToSpeechPage`
- `VoiceChatPage`

Recommended states for each screen:

- idle
- recording
- uploading
- success
- timeout
- failed

## Important Integration Notes

- For Android emulator, local backend URL is usually:

```text
http://10.0.2.2:8000
```

- For physical device, use the local machine IP instead of `localhost`.
- If you upload `mp3` or `m4a`, the backend requires `ffmpeg`.
- `tts` returns binary audio directly, so do not parse it as JSON on success.
- `voice chat` is easier in Flutter when `return_audio_base64=true`.

## Example Error Handling Strategy

Flutter should:

- show backend `message` when available
- map `stt_timeout` to a user-friendly timeout message
- map `voice_chat_timeout` to "recording was uploaded but transcription took too long"
- retry only when the user explicitly requests retry

## Minimal Acceptance Checklist

- Record voice from Flutter
- Send recorded file to `/voice/stt`
- Display transcript
- Send text to `/voice/tts`
- Save and play returned wav
- Send audio to `/voice/chat/{project_id}`
- Display transcript and answer
- Decode returned `audio_base64` and play it
