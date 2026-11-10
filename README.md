# Serum Bridge for KeyLab Essential mk3 (FL Studio)

Browse **Serum 2** presets from an **Arturia KeyLab Essential mk3** in FL Studio, with a short
sound preview after every change. Arturia's normal FL Studio integration (transport, mixer,
channel rack, browser, pads, knobs) keeps working as before.

| While Serum 2's window is focused | Action |
|---|---|
| Main encoder turn | Previous / next preset |
| Context button 3 | Previous preset |
| Context button 4 | Next preset |

After each preset change, a short note (C4) plays so you can hear the new sound. It's skipped
while you're holding keys. Focus any other window and every control does what Arturia's script
normally does.

## Requirements

- Windows, FL Studio 21 or newer (tested on FL Studio 2025 / 25.2.3)
- Arturia KeyLab Essential mk3 (49/61/88) in DAW mode
- Serum 2 (VST3, tested with 2.1.5)

## Install

1. **Close FL Studio.** Serum rewrites its preferences file when it closes.
2. Download or clone this repository and double-click **`install.bat`**. If you prefer the
   command line, run `powershell -ExecutionPolicy Bypass -File install.ps1`.

   The installer:
   - copies `Serum Bridge KeyLab Essential mk3` into
     `Documents\Image-Line\FL Studio\Settings\Hardware`
   - sets Serum 2's preset-stepping CCs in `%APPDATA%\Xfer\Serum 2\Serum2Prefs.json`, after
     making a timestamped backup

3. In FL Studio, open **Options > MIDI settings**. Select the KeyLab's **DAW** port, set
   **Controller type** to **KeyLab Essential mk3 + Serum 2 Bridge**, and give it a port number
   (for example 236). Set the matching output port to the same number.
4. Open Serum 2 and click the **gear icon** at the top left of the plugin window (FL's wrapper
   settings). Under **MIDI**, set **Input port** to the same port number. Do this for each Serum
   instance. Saving it in a template or default project saves repeating it.

Installer options: `-HardwareDir <path>` if your FL user data folder is somewhere else,
`-SkipSerumPrefs` to leave Serum's prefs alone, and `-Force` to edit the prefs while FL is open
(only safe if no Serum instance is loaded).

To set the CCs by hand instead, open Serum 2's preferences, enable *CC for rockers*, and set
*Preset +* to CC 14 and *Preset -* to CC 15.

## How it works

FL Studio can't change Serum 2 presets directly. Serum 2 is VST3-only, FL doesn't pass Program
Change through to it, and Serum exposes no preset parameter to the host. What does work is
Serum's own **"CC for rockers"** preference: Serum steps to the next or previous preset when a
chosen CC rises from below 64 to above it.

The bridge:

- loads Arturia's own FL script from its installed folder, without copying or modifying it, and
  passes every MIDI event and callback to it
- intercepts only the main encoder and context buttons 3/4, and only while Serum 2's window is
  focused
- sends CC 14 (next) or CC 15 (previous) to Serum as a 0 → 127 pair, spacing steps out so Serum
  can finish loading each preset
- plays a short preview note on the Serum channel once a preset has loaded

FL only delivers raw MIDI CCs to a VST3 plugin when the plugin wrapper's MIDI input port matches
the controller's port. That's why step 4 is needed.

### Limitations

- Serum doesn't tell the host which preset is loaded, so the KeyLab screen shows "Next preset /
  Prev preset" rather than the preset name. The name is visible in Serum's window.
- Stepping follows Serum's own browser list and order, including any filter you set in Serum's
  browser.

## Settings

Edit `serum_bridge_config.py` in the installed folder, then restart FL (or reload the script).
The installer never overwrites this file.

| Setting | Default | Meaning |
|---|---|---|
| `PREVIEW_ENABLED` | `True` | Play a preview after a preset change |
| `PREVIEW_NOTES` | `[60]` | Notes to play, e.g. `[60, 63, 67]` for a chord |
| `PREVIEW_VELOCITY` | `100` | Preview velocity |
| `PREVIEW_DELAY_MS` | `250` | Wait for the preset to load before the preview plays |
| `PREVIEW_LENGTH_MS` | `800` | Preview note length |
| `PRESET_NEXT_CC` / `PRESET_PREV_CC` | `14` / `15` | Must match Serum's prefs. Run the installer again after changing them |
| `STEP_INTERVAL_MS` | `150` | Pause between preset steps |
| `MAX_QUEUED_STEPS` | `8` | Most steps queued when the encoder is turned fast |
| `ARTURIA_DIR` | auto | Folder holding Arturia's `device_KLEss3.py` |

## Troubleshooting

- **Nothing happens in Serum.** Check that Serum's wrapper MIDI input port equals the KeyLab DAW
  port number (step 4), and that Serum's *CC for rockers* is enabled with CC 14/15. Serum's MIDI
  Learn is a quick test: if it can learn a KeyLab knob, CCs are getting through.
- **The DAW integration stops working.** Look in **View > Script output**. The bridge prints
  where it loaded Arturia's script from. If it couldn't find it, set `ARTURIA_DIR` in
  `serum_bridge_config.py`.
- **The preset jumps by more than one.** Raise `STEP_INTERVAL_MS`.

## Uninstall

Run `powershell -ExecutionPolicy Bypass -File uninstall.ps1`, then set the KeyLab's controller
type back to Arturia's script. Backups of Serum's prefs (`Serum2Prefs.json.bak-*`) stay next to
the prefs file.

## License

MIT. Arturia's KeyLab script isn't included. It ships with FL Studio and stays under its own
terms.
