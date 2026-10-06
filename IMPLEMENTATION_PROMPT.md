# Prompt: system-wide dictation on macOS using my Codex/ChatGPT login

I want a small macOS tool that works as a **system-wide dictation key**. I press
a global shortcut in any app, speak, and the transcript is inserted at the
cursor. It must use the **ChatGPT login my Codex CLI already has**, not an
OpenAI API key and not separate billing.

## Core idea

Codex Desktop transcribes its own dictation by uploading recorded audio to a
private ChatGPT backend endpoint. That request is authenticated with the
ChatGPT OAuth token the Codex CLI stores after `codex login`. We reuse that
token and endpoint, then insert the returned text wherever the cursor is.

```text
global shortcut → record mic → POST audio to Codex transcription endpoint → insert text at cursor
```

## The backend contract (the only Codex-specific part)

- **Auth:** read the Codex auth file. Look at `$CODEX_HOME/auth.json` first,
  then `~/.codex/auth.json`. Take the token from `tokens.access_token` and the
  account ID from `tokens.account_id`. If the account ID is missing, read the
  `chatgpt_account_id` claim from the token's JWT payload.
  - Refuse to run if the file shows an API-key login instead of a ChatGPT
    login, and tell the user to run `codex login`. Check with
    `codex login status`, which should report "Logged in using ChatGPT".
  - The Codex CLI may be configured to store credentials in the macOS
    Keychain instead of the file. If `auth.json` is missing, check how this
    machine's Codex stores credentials.
  - Re-read the auth for every request, and never copy, log or refresh the
    token.
- **Request:** `POST https://chatgpt.com/backend-api/transcribe`, sent as
  multipart form data.
  - Form fields: `file` (the audio, e.g. WAV, with its correct MIME type) and
    an optional `language`.
  - Headers: `Authorization: Bearer <token>`, `ChatGPT-Account-Id: <id>`,
    `Originator: Codex Desktop`, and a `User-Agent` of the form
    `Codex Desktop/<version> (<os>; <arch>)`.
- **Response:** JSON `{"text": "..."}`. On HTTP 401, tell the user to run
  `codex login`.
- This endpoint is **reverse-engineered and undocumented** and may change.
  Keep all knowledge of it in one isolated module and test it on its own with
  a "transcribe this audio file" command before building anything else.

## Required behaviour

- **Shortcut:** support both tap-to-toggle (tap to start, tap again to stop)
  and hold-to-talk (hold for longer than about 0.4 s, release to stop).
  Recording starts immediately on press. Ignore key autorepeat.
- **Never block the UI.** Run the network call in the background and show
  simple status ("Listening…", "Transcribing…", errors) through notifications
  or a menu-bar indicator.
- **Focus safety:** if the user switches app or window while recording or
  waiting for the transcript, cancel or discard the result. Text must never
  land in the wrong place.
- Optionally append a trailing space after each transcript.
- **Privacy:** delete temporary audio after every request, including failed
  ones, and never persist transcripts.
- Provide two diagnostic commands:
  - `doctor`: check permissions, the auth token and the audio tools.
  - `diagnose`: record a few seconds and transcribe them end to end.

## macOS-specific decisions for you to make

Investigate the options and pick the most robust one for current macOS:

- **Text insertion:** options include a proper Input Method (InputMethodKit),
  the Accessibility API, or a clipboard-paste fallback. Prefer a method that
  works in terminals, browsers and editors without clobbering the clipboard,
  or restore the clipboard if you must use it.
- **Global shortcut:** pick a key combination that does not clash with
  Spotlight or the input-source switcher.
- **Audio capture:** use a native framework or a CLI tool, and produce mono
  16-bit WAV.
- **Permissions:** the tool needs Microphone and Accessibility (and possibly
  Input Monitoring) permissions. Detect when they are missing and explain how
  to grant them.

Keep it small, with few dependencies and an install script, and include unit
tests that need no network, microphone or real OS integration.

## Reference
The original version of this tool was built for Ubuntu as an IBus input
method with PipeWire recording. Only the backend contract and the behaviour
above carry over to macOS; the platform mechanics do not.
