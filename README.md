# Serum Bridge for KeyLab Essential mk3 (FL Studio)

Browse **Serum 2** presets from an **Arturia KeyLab Essential mk3** in FL Studio, with a short
sound preview after every change. Arturia's normal FL Studio integration (transport, mixer,
channel rack, browser, pads, knobs) keeps working as before.

| While Serum 2's window is focused | Action |
|---|---|
| Main encoder turn | Previous / next preset |
| Context button 3 | Previous preset |
| Context button 4 | Next preset |
| Knobs 1–8 | Serum macros 1–8. The screen shows the preset's macro name and value |

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

3. In FL Studio, open **Options > MIDI settings**. Select the KeyLab's **DAW** port and set
   **Controller type** to **KeyLab Essential mk3 + Serum 2 Bridge**. Give the input and the
   matching output the same port number.
4. Open Serum 2 and click the **gear icon** at the top left of the plugin window (FL's wrapper
   settings). Under **MIDI**, set **Input port** to **100**, the bridge's Serum port. Don't use
   the KeyLab's own port here: Serum would then also receive every raw KeyLab CC, and buttons
   or knobs could step presets by accident. Do this for each Serum instance. Saving it in a
   template or default project saves repeating it.

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

The CCs go out through FL's `device.forwardMIDICC`, which delivers to plugins whose wrapper MIDI
input port matches the port number in the message. That's why step 4 is needed. Arturia's own
script uses the same mechanism for Analog Lab on port 10.

### Serum inside Patcher (e.g. a keyboard split with VFX Keyboard Splitter)

The bridge also works when Serum 2 sits inside Patcher. Open the inner Serum's window, so that
the window is focused rather than Patcher, and browse as usual. Two differences:

- **Each inner Serum needs its own wrapper MIDI input port set to 100.** If only the instances
  you browse (e.g. the lead) listen on port 100, the others never change preset.
- **Macros can't be set directly**, because FL's scripting API can't reach plugins inside
  Patcher. Instead, knobs 1–8 send CC 20–27 on port 100. In Serum, right-click each macro,
  choose *MIDI Learn*, and turn the matching knob once. Serum keeps the mapping when you change
  presets, as long as *Load MIDI Map from Presets* is off.

The preview note plays on the Patcher channel, so it passes through your split. Keep
`PREVIEW_NOTES` on the side of the split you browse.

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
| `KNOBS_TO_MACROS` | `True` | Knobs 1–8 control Serum's macros while Serum is focused |
| `MACRO_CCS` | `[20 … 27]` | CCs the knobs send for Serum inside Patcher (MIDI-learn them in Serum) |
| `PREVIEW_ENABLED` | `True` | Play a preview after a preset change |
| `PREVIEW_NOTES` | `[60]` | Notes to play, e.g. `[60, 63, 67]` for a chord |
| `PREVIEW_VELOCITY` | `100` | Preview velocity |
| `PREVIEW_DELAY_MS` | `250` | Wait for the preset to load before the preview plays |
| `PREVIEW_LENGTH_MS` | `800` | Preview note length |
| `PRESET_NEXT_CC` / `PRESET_PREV_CC` | `14` / `15` | Must match Serum's prefs. Run the installer again after changing them |
| `SERUM_PORT` | `100` | Port the bridge sends to (0–127). Must match Serum's wrapper MIDI input port |
| `FORWARD_MODE` | `1` | `forwardMIDICC` target: 0 all plugins, 1 focused plugin, 2 selected channels |
| `DEBUG` | `False` | Print every step to View > Script output |
| `STEP_INTERVAL_MS` | `150` | Pause between preset steps |
| `MAX_QUEUED_STEPS` | `8` | Most steps queued when the encoder is turned fast |
| `ARTURIA_DIR` | auto | Folder holding Arturia's `device_KLEss3.py` |

## Troubleshooting

- **Nothing happens in Serum.** Check that Serum's wrapper MIDI input port is 100 (step 4), and
  that Serum's *CC for rockers* is enabled with CC 14/15. Close FL before running the installer,
  or the prefs aren't updated. Set `DEBUG = True` to see each step in View > Script output.
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
