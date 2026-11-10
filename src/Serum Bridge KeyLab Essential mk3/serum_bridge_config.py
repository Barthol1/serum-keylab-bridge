# Serum Bridge settings. Edit and reload the script (FL: Options > MIDI settings,
# or restart FL) to apply. The installer never overwrites an existing copy of this file.

# Folder that holds Arturia's FL Studio script (device_KLEss3.py).
# None = auto-detect: the "Arturia KeyLab Essential mk3" folder next to this one.
ARTURIA_DIR = None

# Serum 2 "CCForRocker Preset +/-" CCs. Must match Serum2Prefs.json
# (the installer sets them). Pick CCs the KeyLab never sends in DAW mode.
PRESET_NEXT_CC = 14
PRESET_PREV_CC = 15

# Pause after each preset step so Serum can finish loading before the next one.
STEP_INTERVAL_MS = 150
# Most steps queued at once when the encoder is turned fast.
MAX_QUEUED_STEPS = 8

# Sound preview after a preset has loaded.
PREVIEW_ENABLED = True
PREVIEW_NOTES = [60]        # MIDI notes; 60 = C4. e.g. [60, 63, 67] for a C minor chord
PREVIEW_VELOCITY = 100
PREVIEW_DELAY_MS = 250      # wait for the preset to load before playing
PREVIEW_LENGTH_MS = 800     # how long the preview note is held
