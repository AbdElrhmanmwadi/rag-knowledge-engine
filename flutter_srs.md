# Software Requirements Specification (SRS)

## Flutter Mobile App for RAG Knowledge Engine

## 1. Introduction

### 1.1 Purpose
This document defines the software requirements for a Flutter mobile application that consumes the existing `RAG Knowledge Engine` backend.

The mobile application shall allow users to:

- open or create a project by project identifier
- upload supported files to a project
- process uploaded files into chunks
- index processed chunks into the vector database
- search indexed knowledge
- ask RAG questions and receive generated answers
- record audio and transcribe speech to text
- convert text responses into playable speech
- use voice chat with project knowledge
- submit file translation jobs
- track translation job status
- download completed translated files

### 1.2 Scope
The Flutter application is a client application for Android and iOS, with optional future support for desktop and web.

The application is responsible for:

- presenting a user-friendly interface for project-based knowledge workflows
- invoking backend REST APIs
- validating basic client-side user input
- showing request state, job state, and backend responses
- managing lightweight local UI state such as recent project identifiers

The application is not responsible for:

- document parsing logic
- chunk generation
- vector indexing logic
- embedding generation
- translation engine execution
- file storage implementation on the server

### 1.3 Intended Audience
This document is intended for:

- Flutter developers
- backend integrators
- UI/UX designers
- QA engineers
- technical stakeholders

### 1.4 Definitions

- `Project`: a logical knowledge workspace identified by `project_id`
- `Asset`: an uploaded or generated file associated with a project
- `Chunk`: processed text segment derived from an asset
- `Indexing`: pushing chunks into the vector database
- `RAG`: retrieval-augmented generation
- `Translation Job`: asynchronous request to translate a file

## 2. Product Overview

### 2.1 Product Perspective
The mobile application is a thin client over the existing backend APIs.

The backend currently exposes workflows for:

- file upload and file processing
- vector indexing and vector search
- RAG answer generation
- voice STT, TTS, and voice chat
- file translation, translation status retrieval, and translated file download

The mobile application shall organize these backend capabilities into a guided user flow.

### 2.2 Product Goals
The application should:

- make the backend usable by non-technical users
- reduce manual API interaction
- provide a clear project-based workflow
- present status and failure states in understandable language
- support future expansion such as richer file listing and translation history

### 2.3 User Types

#### 2.3.1 Standard User
Uses the app to upload documents, index them, ask questions, and request translations.

#### 2.3.2 Power User
Uses project identifiers repeatedly, uploads many files, and may trigger reprocessing or reindexing flows.

#### 2.3.3 QA or Demo User
Uses the app to validate integration with the backend and observe system behavior.

## 3. Assumptions and Dependencies

### 3.1 Assumptions

- the backend service is reachable over HTTP
- the backend creates a project automatically when a valid `project_id` is used
- the backend returns JSON responses in the current documented shape
- the mobile device has network access to the backend
- supported file picking is available on the client platform

### 3.2 External Dependencies

- Flutter SDK
- Dart SDK
- `dio` for HTTP networking
- `file_picker` for file selection
- `record` for audio recording
- `just_audio` or `audioplayers` for playback
- optional state management package such as `flutter_riverpod`
- the existing FastAPI backend

### 3.3 Backend Dependencies
The app depends on the following backend endpoints:

- `POST /api/v1/data/upload/{project_id}`
- `POST /api/v1/data/process/{project_id}`
- `POST /api/v1/nlp/index/push/{project_id}`
- `GET /api/v1/nlp/index/info/{project_id}`
- `POST /api/v1/nlp/index/search/{project_id}`
- `POST /api/v1/nlp/index/answer/{project_id}`
- `POST /api/v1/voice/stt`
- `POST /api/v1/voice/tts`
- `POST /api/v1/voice/chat/{project_id}`
- `POST /translate/file`
- `GET /translate/status/{job_id}`
- `GET /translate/download/{job_id}`

## 4. High-Level User Workflow

### 4.1 Primary Workflow
The primary application flow shall be:

1. user opens a project using `project_id`
2. user uploads a file
3. user processes the file
4. user indexes project chunks
5. user searches or asks a question
6. user optionally uses speech-to-text or voice chat
7. user optionally starts a translation job for a file
8. user downloads the translated file after the job is completed

### 4.2 Secondary Workflow
The application may support:

- reprocessing a specific file
- reindexing with reset
- checking translation job status repeatedly
- replaying generated audio responses
- switching between text chat and voice chat
- downloading translated files from completed jobs
- reopening recently used projects

## 5. Application Structure

### 5.1 Main Screens
The application shall contain at minimum the following screens:

- `ProjectsPage`
- `ProjectDashboardPage`
- `FilesPage`
- `AskPage`
- `VoicePage`
- `TranslatePage`

### 5.2 Navigation Model
The navigation model shall be:

1. `ProjectsPage` -> `ProjectDashboardPage`
2. `ProjectDashboardPage` -> `FilesPage`
3. `ProjectDashboardPage` -> `AskPage`
4. `ProjectDashboardPage` -> `VoicePage`
5. `ProjectDashboardPage` -> `TranslatePage`

## 6. Functional Requirements

### 6.1 Project Entry
The application shall:

- allow the user to enter a numeric `project_id`
- validate that `project_id` is a valid integer
- store recent project identifiers locally
- allow reopening a recently used project

### 6.2 Project Dashboard
The application shall display a project dashboard showing available actions:

- manage files
- ask AI questions
- use voice features
- request file translation
- optionally view index info in future versions

### 6.3 File Upload
The application shall:

- allow the user to pick a file from the device
- send the file as multipart form data to the backend
- display upload progress or loading state
- display the backend response signal
- store or display the returned `file_id`

The application should support the backend file types currently handled by the backend registry, including:

- `.txt`
- `.pdf`
- `.docx`
- `.csv`
- `.html`
- `.xlsx`

### 6.4 File Processing
The application shall:

- allow processing of a specific uploaded file by `file_id`
- allow setting `chunk_size`
- allow setting `overlap_size`
- allow toggling `do_reset`
- show `inserted_chunks`
- show `processed_files`

The first mobile release may keep `chunk_size`, `overlap_size`, and `do_reset` behind an advanced section while using defaults for standard users.

### 6.5 Vector Index Push
The application shall:

- allow the user to push project chunks into the vector database
- allow `do_reset` for full reindexing
- show request loading state
- show success or error signal returned by the backend

### 6.6 Index Info
The application should provide an optional screen or panel that:

- calls `GET /api/v1/nlp/index/info/{project_id}`
- displays collection metadata if available

This requirement is recommended but not mandatory for the first release.

### 6.7 Semantic Search
The application shall:

- allow the user to enter a search query
- allow the user to set a result limit
- call the vector search endpoint
- display ranked search results
- display result text, score, and metadata

### 6.8 RAG Answer Generation
The application shall:

- allow the user to ask a question for the current project
- allow a configurable retrieval limit
- display the generated answer
- optionally display the full prompt and chat history in an expandable debug section

### 6.9 Speech to Text
The application shall:

- allow the user to record audio or pick an audio file
- send the audio file to `POST /api/v1/voice/stt`
- optionally send `language`
- display the returned transcript
- display timeout and failure states based on backend `signal`

### 6.10 Text to Speech
The application shall:

- allow the user to submit text to `POST /api/v1/voice/tts`
- send `format=wav`
- receive binary wav audio from the backend
- save or stream the returned audio
- play the generated speech in the app

### 6.11 Voice Chat
The application shall:

- allow the user to record audio for a given `project_id`
- send the audio file to `POST /api/v1/voice/chat/{project_id}`
- allow optional `limit`
- allow optional `language`
- allow optional `return_audio_base64`
- display the recognized transcript
- display the generated answer
- decode and play returned audio when `audio_base64` is present

### 6.12 File Translation
The application shall:

- allow the user to enter or select a `file_id`
- allow the user to specify `source_lang`
- allow the user to specify `target_lang`
- send a translation job creation request
- display `job_id`, job `status`, and related response fields

### 6.13 Translation Status Tracking
The application shall:

- allow the user to manually refresh job status
- optionally poll the translation status automatically
- display:
  - `job_id`
  - `status`
  - `result_file_id`
  - `download_url` when the job is completed
  - `error_message`

### 6.14 Translated File Download
The application shall:

- allow the user to download a translated file when the translation job status is `completed`
- use the backend `download_url` returned by the translation status response
- save or open the downloaded file using the filename provided by the backend attachment response
- display a friendly message if the backend returns `404` or `409` for missing or not-ready translated files

### 6.15 Error Handling
The application shall:

- handle network errors gracefully
- display backend error messages when available
- display validation messages for invalid user input
- disable repeated action buttons while requests are running
- request microphone permission before recording

## 7. Screen-Level Requirements

### 7.1 ProjectsPage
The `ProjectsPage` shall contain:

- app title
- text field for `project_id`
- button to open project
- list of recent project identifiers

The page should:

- reject empty input
- reject non-numeric project identifiers

### 7.2 ProjectDashboardPage
The `ProjectDashboardPage` shall contain:

- current project identifier
- navigation cards or buttons for:
  - files
  - ask AI
  - voice
  - translation
  - optional project info

The page should use large clear actions suitable for mobile usage.

### 7.3 FilesPage
The `FilesPage` shall contain:

- file picker button
- selected file name
- upload button
- displayed `file_id`
- process button
- index button
- status or log panel

The page may later support:

- list of project files
- file deletion
- processing all project files

### 7.4 AskPage
The `AskPage` shall contain:

- text input for user question
- optional input for result limit
- search button
- ask button
- answer display area

The page may also include:

- retrieved chunks section
- debug section for prompt data

### 7.5 VoicePage
The `VoicePage` shall contain:

- record button
- stop button
- optional audio file picker
- speech-to-text action
- text-to-speech action
- voice chat action
- transcript display area
- answer display area
- audio playback action
- timeout and failure UI states

The page should support:

- microphone permission handling
- retry after failed upload or timeout
- switching between `STT`, `TTS`, and `Voice Chat`

### 7.6 TranslatePage
The `TranslatePage` shall contain:

- input for `file_id`
- input or selector for `source_lang`
- input or selector for `target_lang`
- button to start translation
- button to check job status
- button to download translated file when available
- status card

The page should display the backend-provided `download_url` or an equivalent download action only when the translation job is completed.

## 8. Data Model Requirements

### 8.1 Client-Side Models
The app shall define models for at minimum:

- `UploadResponse`
- `ProcessResponse`
- `IndexPushResponse`
- `SearchResultItem`
- `SearchResponse`
- `RagAnswerResponse`
- `SttResponse`
- `TtsAudioResponse` or equivalent binary wrapper
- `VoiceChatResponse`
- `TranslationJobCreateResponse`
- `TranslationJobStatusResponse`
- `TranslationDownloadState`

### 8.2 Suggested Local Data
The app should store locally:

- recent project identifiers
- last used backend base URL if configurable
- last used target language

The app should not store:

- backend secrets
- provider API keys

## 9. API Integration Requirements

### 9.1 Base URL Configuration
The application shall support a configurable backend base URL.

The app should:

- use `10.0.2.2` for Android emulator development when the backend runs locally
- support custom server IP or domain in future settings

### 9.2 Upload API
The app shall send:

- multipart field `file`

The app shall consume:

- `signal`
- `file_id`

### 9.3 Process API
The app shall send a JSON body with:

- `file_id`
- `chunk_size`
- `overlap_size`
- `do_reset`

The app shall consume:

- `signal`
- `inserted_chunks`
- `processed_files`

### 9.4 Index Push API
The app shall send:

- `do_reset`

The app shall consume:

- `signal`

### 9.5 Search API
The app shall send:

- `text`
- `limit`

The app shall consume:

- `signal`
- `search_result[]`

Each search result should be mapped as:

- `text`
- `score`
- `meta_data`

### 9.6 Answer API
The app shall send:

- `text`
- `limit`

The app shall consume:

- `signal`
- `answer`
- `full_prompt`
- `chat_history`

### 9.7 STT API
The app shall send:

- multipart field `audio`
- optional `language`

The app shall consume:

- `signal`
- `text`
- `language`
- `duration_ms`

### 9.8 TTS API
The app shall send:

- `text`
- `format`

The app shall consume:

- binary `audio/wav` on success
- JSON with `signal` and `message` on failure

### 9.9 Voice Chat API
The app shall send:

- multipart field `audio`
- `limit`
- `return_audio_base64`
- optional `language`

The app shall consume:

- `signal`
- `transcript`
- `answer`
- `audio_base64`
- `audio_mime_type`
- `full_prompt`
- `chat_history`

When `return_audio_base64=false`, the app shall handle binary audio and read `X-Transcript` from response headers.

### 9.10 Translation Create API
The app shall send:

- `project_id`
- `file_id`
- `source_lang`
- `target_lang`

The app shall consume:

- `signal`
- `job_id`
- `status`
- `asset_id`
- `source_lang`
- `target_lang`

### 9.11 Translation Status API
The app shall consume:

- `signal`
- `job.job_id`
- `job.status`
- `job.result_file_id`
- `job.download_url`
- `job.error_message`

The app should treat `job.download_url` as nullable and only enable download behavior when it is present.

### 9.12 Translation Download API
The app shall call:

- `GET /translate/download/{job_id}`

The endpoint returns:

- a file attachment response when the translation is ready
- JSON error content when the job is not ready or not found

The app shall:

- handle attachment download using the backend response headers and filename
- handle `409 Conflict` as "translated file is not ready yet"
- handle `404 Not Found` as "translation job or translated file was not found"

## 10. Non-Functional Requirements

### 10.1 Usability
The application should:

- be easy to use with one-handed mobile interaction
- keep primary actions visible and understandable
- use simple labels for technical operations such as processing and indexing

### 10.2 Performance
The application should:

- show loading feedback within 200 milliseconds of starting a request
- remain responsive during API calls
- avoid blocking the main UI thread

### 10.3 Reliability
The application shall:

- survive intermittent network failures
- allow retrying failed requests
- preserve recent project identifiers after app restart

### 10.4 Maintainability
The codebase should separate:

- presentation
- data access
- models
- configuration

The app should keep backend integration logic out of widgets.

### 10.5 Scalability
The application should support future additions such as:

- authentication
- project file list endpoint integration
- job history
- dark mode
- tablet layout

### 10.6 Security
The application shall:

- avoid storing secrets in source code
- validate visible user input on the client side
- avoid logging sensitive data in production builds

## 11. Recommended Technical Architecture

### 11.1 State Management
The recommended state management approach is:

- `flutter_riverpod`

Alternative acceptable approaches:

- `bloc`
- `provider`

### 11.2 Networking
The recommended HTTP client is:

- `dio`

### 11.3 File Picking
The recommended file selection package is:

- `file_picker`

### 11.4 Audio Recording
The recommended audio recording package is:

- `record`

### 11.5 Audio Playback
Recommended audio playback packages:

- `just_audio`
- `audioplayers`

### 11.6 Navigation
The recommended navigation package is:

- `go_router`

### 11.7 Suggested Folder Structure
```text
lib/
  main.dart
  app.dart
  core/
    config/
      app_config.dart
    network/
      dio_client.dart
      api_exception.dart
    theme/
      app_theme.dart
    widgets/
      app_card.dart
      app_button.dart
      status_badge.dart
  features/
    projects/
      data/
      presentation/
    dashboard/
      presentation/
    files/
      data/
      presentation/
    rag/
      data/
      presentation/
    voice/
      data/
      presentation/
    translation/
      data/
      presentation/
```

## 12. UI and UX Requirements

### 12.1 Visual Style
The application should:

- use a clean modern mobile-first layout
- prefer card-based action grouping
- use clear visual distinction for upload, processing, AI, voice, and translation flows

### 12.2 Recommended Visual Direction
Suggested visual mapping:

- files: blue or teal
- ask AI: green
- voice: amber or deep orange
- translation: orange
- project context: neutral gray

### 12.3 Feedback States
Every primary screen shall support:

- idle state
- loading state
- success state
- empty state
- error state
- permission state for microphone-based features

## 13. Known Backend Gaps Affecting the Flutter App

The current backend is sufficient for a first mobile release, but the following additions are recommended:

- endpoint to list files by project
- endpoint to delete files
- endpoint to list translation jobs by project
- improved endpoint for processing or indexing status
- optional streaming voice response endpoint in future versions

These gaps do not block version 1, but they limit usability and observability.

## 14. Release Scope

### 14.1 Minimum Viable Product (MVP)
The MVP shall include:

- project entry
- file upload
- file processing
- vector index push
- RAG answer flow
- speech to text
- text to speech
- voice chat
- translation job creation
- translation status check
- translated file download for completed jobs

### 14.2 Post-MVP
Post-MVP may include:

- file listing
- richer voice history and replay
- translated file access
- search result browsing
- saved history
- settings screen
- multi-environment backend switching

## 15. Acceptance Criteria

The Flutter app shall be considered acceptable for MVP when:

- a user can enter a valid `project_id`
- a user can upload a supported file successfully
- a user can process and index uploaded content
- a user can ask a question and receive a backend-generated answer
- a user can record or select audio and receive a transcript
- a user can request generated speech and play returned audio
- a user can use voice chat and receive transcript, answer, and playable audio
- a user can submit a translation job and observe job status changes
- a user can download a translated file after the job is completed
- the app handles expected error states without crashing

## 16. Future Enhancements

Future enhancements may include:

- authentication and user accounts
- user-friendly project naming
- multi-file management
- document preview
- waveform visualization for recording and playback
- streaming voice responses
- translated file preview
- push notifications for translation completion
- offline queueing for non-upload actions
