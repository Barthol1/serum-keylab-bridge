# Serum Bridge settings. Edit, then reload the script (or restart FL) to apply.
# The installer never overwrites an existing copy of this file.

# Folder that holds Arturia's FL Studio script (device_KLEss3.py).
# None = auto-detect: the "Arturia KeyLab Essential mk3" folder next to this one.
ARTURIA_DIR = None

# Serum 2 "CCForRocker Preset +/-" CCs. Must match Serum2Prefs.json (the installer
# sets them). Use CCs the KeyLab never sends in DAW mode.
PRESET_NEXT_CC = 14
PRESET_PREV_CC = 15

# MIDI port the bridge sends to (0-127). Set the wrapper MIDI input port of each
# Serum you browse to this number (Serum's gear icon > MIDI > Input port).
# Don't use the KeyLab's own port.
SERUM_PORT = 100

# While Serum 2 is focused, KeyLab knobs 1-8 control Serum's macros 1-8.
KNOBS_TO_MACROS = True
# Serum inside Patcher can't be controlled directly: knobs 1-8 then send these CCs
# on SERUM_PORT instead. MIDI-learn each macro in Serum once (right-click > MIDI Learn).
# 56-63 are never sent by the KeyLab itself (20-27 would clash with its transport).
MACRO_CCS = [56, 57, 58, 59, 60, 61, 62, 63]

# FL reports a plugin window inside Patcher as Patcher itself, so a focused Patcher
# window counts as "Serum inside Patcher"; only the Serums on SERUM_PORT react.
PATCHER_IS_SERUM_HOST = True
# Only Patcher channels whose name contains this text (e.g. "BAND"). "" = every Patcher.
PATCHER_CHANNEL_FILTER = ""

# Sound preview after a preset change.
PREVIEW_ENABLED = True
PREVIEW_NOTES = [60]        # MIDI notes; 60 = C4. e.g. [60, 63, 67] for a C minor chord
PREVIEW_VELOCITY = 100
PREVIEW_DELAY_MS = 250      # wait for the preset to load before playing
PREVIEW_LENGTH_MS = 800     # how long the preview note is held

# Pause after each preset step so Serum can finish loading before the next one.
STEP_INTERVAL_MS = 150
# Most steps queued at once when the encoder is turned fast.
MAX_QUEUED_STEPS = 8

# Print each preset step to View > Script output.
DEBUG = False
