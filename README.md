# Codex ASR

> [!NOTE]
> I built this for my own use, and an AI coding agent wrote all of the code and
> documentation. I've only tested it on my own machine. It's shared as-is, with
> no support or maintenance planned.

Dictation for Ubuntu GNOME that uses your existing Codex CLI login instead of an
OpenAI API key. It runs as an IBus input method, so it types into the focused
application and works on Wayland.

Each utterance is recorded locally with PipeWire and uploaded to the endpoint
Codex Desktop uses for dictation:

```text
https://chatgpt.com/backend-api/transcribe
```

This endpoint is undocumented and was reverse-engineered from Codex Desktop. A
future Codex release could change or remove it.

## Requirements

- Ubuntu with GNOME and IBus
- The Codex CLI, logged in with ChatGPT (`codex login status` should report
  `Logged in using ChatGPT`)
- System packages: `python3-gi`, `gir1.2-ibus-1.0`, `pipewire-bin` (for
  `pw-record`) and `libnotify-bin` (for `notify-send`)

## Install

```bash
bash ./setup.sh
```

`setup.sh` does the following:

1. Installs the engine to `~/.local/lib/codex-asr` and the `codex-asr` command to
   `~/.local/bin`.
2. Runs `codex-asr doctor`.
3. Uses sudo to copy the IBus component into `/usr/share/ibus/component`, since
   Ubuntu's IBus does not scan the user component directory.
4. Adds **Codex Dictation** to your GNOME input sources and leaves your
   existing sources in place.

Log out and back in, then select **Codex Dictation** from the input menu in
the top bar. To skip the sudo and GNOME steps, run `./install.sh`, which only
does step 1.

## Usage

Press **Ctrl+Shift+Space** to dictate:

- **Tap** once to start recording and again to stop.
- **Hold** for at least 0.4 seconds while speaking, then release to stop.

Recording starts as soon as you press the shortcut. The transcript is inserted
at the cursor. If focus changes while you are recording, the recording is
cancelled. If focus changes while a transcript is pending, the transcript is
discarded so it cannot end up in the wrong window.

## Troubleshooting

```bash
codex-asr doctor                  # check dependencies and the Codex login
codex-asr diagnose                # record 5 seconds and transcribe them end to end
codex-asr transcribe audio.wav    # transcribe an existing file
```

## Configuration

Configuration is optional and goes in `~/.config/codex-asr/config.ini`:

```ini
[codex]
# Language hint; omit to auto-detect.
language = en
# Add a space after each transcript.
append_space = true
# auth_file = ~/.codex/auth.json
```

The auth file is chosen in this order: the `CODEX_ASR_AUTH_FILE` environment
variable, `auth_file` in the config, `$CODEX_HOME/auth.json`, and then
`~/.codex/auth.json`.

## Privacy

On every request, the engine reads `tokens.access_token` and the account ID
from the Codex auth file. It never writes, copies, logs or refreshes the token.
If the login is expired or rejected, it tells you to run `codex login`.

Audio is saved to a temporary WAV file, uploaded to ChatGPT and deleted once
the request finishes. Transcripts are never stored. Audio is transcribed in the
cloud, so do not dictate secrets or use this anywhere cloud transcription is not
allowed.

## Development

The tests have no dependencies and do not need a network, microphone or IBus:

```bash
/usr/bin/python3 -m unittest discover -v
```
