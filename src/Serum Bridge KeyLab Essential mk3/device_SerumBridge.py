# name=KeyLab Essential mk3 + Serum 2 Bridge
# url=https://github.com/Barthol1/serum-keylab-bridge
"""
Serum Bridge for the Arturia KeyLab Essential mk3 in FL Studio.

Wraps Arturia's own FL Studio script (loaded from its installed folder, not
copied) so the normal DAW integration keeps working, and adds Serum 2 preset
browsing:

  While Serum 2's plugin window is focused
    Main encoder turn ...... previous / next preset
    Context button 3 ....... previous preset
    Context button 4 ....... next preset
  After each preset change a short preview note plays (unless you hold keys).

Everything else, and everything while another window is focused, goes to
Arturia's script unchanged.

How it reaches Serum: Serum 2's "CCForRocker Preset +/-" preference steps
presets on a MIDI CC rising edge. FL only delivers raw CCs to a VST3 when the
plugin wrapper's MIDI input port matches the controller's port, so set Serum's
wrapper input port to the KeyLab's port. See README.md.
"""

import os
import sys
import time

import channels
import device
import plugins
import ui

# ------------------------------------------------------------- settings ----

try:
    import serum_bridge_config as cfg
except ImportError:
    cfg = None


def _setting(name, default):
    return getattr(cfg, name, default) if cfg is not None else default


PRESET_NEXT_CC = _setting("PRESET_NEXT_CC", 14)
PRESET_PREV_CC = _setting("PRESET_PREV_CC", 15)
STEP_INTERVAL_MS = _setting("STEP_INTERVAL_MS", 150)
MAX_QUEUED_STEPS = _setting("MAX_QUEUED_STEPS", 8)
PREVIEW_ENABLED = _setting("PREVIEW_ENABLED", True)
PREVIEW_NOTES = list(_setting("PREVIEW_NOTES", [60]))
PREVIEW_VELOCITY = _setting("PREVIEW_VELOCITY", 100)
PREVIEW_DELAY_MS = _setting("PREVIEW_DELAY_MS", 250)
PREVIEW_LENGTH_MS = _setting("PREVIEW_LENGTH_MS", 800)

EDGE_GAP_MS = 20            # between the CC=0 and CC=127 halves of one step
FORWARD_MODE = 1            # device.forwardMIDICC: 1 = focused plugin

# KeyLab Essential mk3, DAW mode
CC_CONTEXT3 = 46
CC_CONTEXT4 = 47
CC_MAIN_ENCODER = 116       # relative: >64 clockwise, <64 counter-clockwise

WID_PLUGIN = 5
WID_PLUGIN_GENERATOR = 7

SYSEX_HEADER = [0xF0, 0x00, 0x20, 0x6B, 0x7F, 0x42]

# -------------------------------------------------- load Arturia's script ----


def _find_arturia_dir():
    configured = _setting("ARTURIA_DIR", None)
    if configured:
        return configured
    candidates = []
    here = globals().get("__file__")
    if here:
        candidates.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(here))),
                                       "Arturia KeyLab Essential mk3"))
    candidates.append(os.path.join(os.path.expanduser("~"), "Documents", "Image-Line", "FL Studio",
                                   "Settings", "Hardware", "Arturia KeyLab Essential mk3"))
    for path in candidates:
        if os.path.isfile(os.path.join(path, "device_KLEss3.py")):
            return path
    return candidates[0]


ARTURIA_DIR = _find_arturia_dir()
try:
    if ARTURIA_DIR not in sys.path:
        sys.path.insert(0, ARTURIA_DIR)
    import device_KLEss3 as arturia
except Exception as e:  # keep the bridge usable even if Arturia's script is missing
    arturia = None
    print("Serum Bridge: could not load Arturia's script from %s (%s)." % (ARTURIA_DIR, e))
    print("Serum Bridge: set ARTURIA_DIR in serum_bridge_config.py. Running Serum browsing only.")


def _arturia(callback, *args):
    fn = getattr(arturia, callback, None) if arturia is not None else None
    if fn is not None:
        return fn(*args)
    return None


# ---------------------------------------------------------------- state ----

pending_steps = 0       # signed: queued preset steps
step_high = False       # True between the 0 and the 127 half of a step
next_step_ms = 0.0
preview_at_ms = None    # when to start the preview note(s)
preview_off_ms = None   # when to release the sounding preview
preview_channel = None  # global channel index the preview is sounding on
serum_channel = None    # global channel index of the focused Serum
held_notes = set()      # keys/pads currently held on the KeyLab


def now_ms():
    return time.monotonic() * 1000.0


# --------------------------------------------------------------- helpers ----

def _send_sysex(data):
    try:
        device.midiOutSysex(bytes(SYSEX_HEADER + data + [0xF7]))
    except Exception:
        pass


def _ascii(text, maxlen=16):
    text = "".join(c if 32 <= ord(c) <= 126 else "?" for c in str(text))
    return [ord(c) for c in text[:maxlen]]


def show(line1, line2):
    """Two-line transient popup; the KeyLab returns to Arturia's screen afterwards."""
    _send_sysex([0x04, 0x01, 0x60, 0x12, 0x01] + _ascii(line1) + [0x00, 0x02]
                + _ascii(line2) + [0x00, 0x01])


def _selected_channel_global():
    try:
        return channels.selectedChannel(0, 0, 1)
    except TypeError:
        return channels.selectedChannel()


def focused_serum_channel():
    """Global channel index of Serum 2 if its plugin window is focused, else None."""
    try:
        focused = ui.getFocused(WID_PLUGIN_GENERATOR)
    except Exception:
        focused = ui.getFocused(WID_PLUGIN)
    if not focused:
        return None
    try:
        index = _selected_channel_global()
        try:
            name = plugins.getPluginName(index, -1, False, True)
        except TypeError:
            name = plugins.getPluginName(channels.selectedChannel())
    except Exception:
        return None
    name = str(name)
    if "serum 2" in name.lower() and "fx" not in name.lower():
        return index
    return None


def _cc(cc, value):
    return 0xB0 | (cc << 8) | (value << 16)


def _note(channel, note, velocity):
    try:
        channels.midiNoteOn(channel, note, velocity)
    except Exception as e:
        print("Serum Bridge: preview note failed:", e)


def stop_preview():
    global preview_off_ms, preview_channel
    if preview_channel is not None:
        for n in PREVIEW_NOTES:
            _note(preview_channel, n, 0)
    preview_channel = None
    preview_off_ms = None


# --------------------------------------------------------------- actions ----

def queue_steps(delta):
    global pending_steps, preview_at_ms
    pending_steps = max(-MAX_QUEUED_STEPS, min(MAX_QUEUED_STEPS, pending_steps + delta))
    preview_at_ms = None
    stop_preview()
    if pending_steps > 0:
        show("Serum 2", "Next preset  >")
    elif pending_steps < 0:
        show("Serum 2", "<  Prev preset")


def _run_steps(t):
    global pending_steps, step_high, next_step_ms, preview_at_ms
    if not pending_steps or t < next_step_ms:
        return
    cc = PRESET_NEXT_CC if pending_steps > 0 else PRESET_PREV_CC
    try:
        if not step_high:
            device.forwardMIDICC(_cc(cc, 0), FORWARD_MODE)    # arm the rising edge
            step_high = True
            next_step_ms = t + EDGE_GAP_MS
            return
        device.forwardMIDICC(_cc(cc, 127), FORWARD_MODE)      # Serum steps here
    except Exception as e:
        print("Serum Bridge: forwardMIDICC failed:", e)
        pending_steps = 0
        step_high = False
        return
    step_high = False
    pending_steps += -1 if pending_steps > 0 else 1
    next_step_ms = t + STEP_INTERVAL_MS
    if not pending_steps and PREVIEW_ENABLED:
        preview_at_ms = t + PREVIEW_DELAY_MS


def _run_preview(t):
    global preview_at_ms, preview_off_ms, preview_channel
    if preview_off_ms is not None and t >= preview_off_ms:
        stop_preview()
    if preview_at_ms is None or t < preview_at_ms:
        return
    preview_at_ms = None
    if held_notes or serum_channel is None:
        return  # you're already playing: don't add a preview on top
    preview_channel = serum_channel
    for n in PREVIEW_NOTES:
        _note(preview_channel, n, PREVIEW_VELOCITY)
    preview_off_ms = t + PREVIEW_LENGTH_MS


def _track_held_notes(event):
    kind = event.status & 0xF0
    if kind == 0x90 and event.data2 > 0:
        held_notes.add((event.status & 0x0F, event.data1))
    elif kind == 0x80 or (kind == 0x90 and event.data2 == 0):
        held_notes.discard((event.status & 0x0F, event.data1))


def _handle_serum_event(event):
    """Return True if the event was a Serum browsing control and has been used."""
    global serum_channel
    if (event.status & 0xF0) != 0xB0:
        return False
    cc, value = event.data1, event.data2
    if cc not in (CC_CONTEXT3, CC_CONTEXT4, CC_MAIN_ENCODER):
        return False
    channel = focused_serum_channel()
    if channel is None:
        return False
    serum_channel = channel
    if cc == CC_MAIN_ENCODER:
        if value != 64:
            queue_steps(1 if value > 64 else -1)
    elif value > 0:  # button press; releases are swallowed too
        queue_steps(1 if cc == CC_CONTEXT4 else -1)
    return True


# ------------------------------------------------------------ FL callbacks ----

def OnInit():
    print("Serum Bridge: Arturia script from", ARTURIA_DIR if arturia else "<not loaded>")
    _arturia("OnInit")


def OnDeInit():
    stop_preview()
    _arturia("OnDeInit")


def OnMidiMsg(event):
    _track_held_notes(event)
    if _handle_serum_event(event):
        event.handled = True
        return
    _arturia("OnMidiMsg", event)


def OnIdle():
    t = now_ms()
    _run_steps(t)
    _run_preview(t)
    _arturia("OnIdle")


def OnRefresh(flags):
    _arturia("OnRefresh", flags)


def OnUpdateBeatIndicator(value):
    _arturia("OnUpdateBeatIndicator", value)


def OnSysEx(event):
    _arturia("OnSysEx", event)


def OnProjectLoad(status):
    _arturia("OnProjectLoad", status)
