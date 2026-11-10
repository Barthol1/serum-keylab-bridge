# name=KeyLab Essential mk3 + Serum 2 Bridge
# url=https://github.com/Barthol1/serum-keylab-bridge
"""
Serum Bridge for the Arturia KeyLab Essential mk3 in FL Studio.

Wraps Arturia's own FL Studio script (loaded from its installed folder, not
copied) so the normal DAW integration keeps working, and adds Serum 2 control:

  While a Serum 2 window is focused (directly on a channel, or inside Patcher)
    Main encoder turn ...... previous / next preset
    Context button 3 ....... previous preset
    Context button 4 ....... next preset
    Knobs 1-8 .............. Serum macros 1-8
  After each preset change a short preview note plays (unless you hold keys).

Everything else, and everything while another window is focused, goes to
Arturia's script unchanged.

How it reaches Serum: Serum 2's "CCForRocker Preset +/-" preference steps
presets on a MIDI CC rising edge. The bridge sends those CCs with
device.forwardMIDICC, which delivers to plugins whose wrapper MIDI input port
equals the port in the message (SERUM_PORT, default 100). See README.md.
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
SERUM_PORT = _setting("SERUM_PORT", 100) & 0x7F   # top byte of a signed 32-bit message
FORWARD_MODE = _setting("FORWARD_MODE", 1)        # 0 all plugins, 1 focused, 2 selected channels
STEP_INTERVAL_MS = _setting("STEP_INTERVAL_MS", 150)
MAX_QUEUED_STEPS = _setting("MAX_QUEUED_STEPS", 8)

KNOBS_TO_MACROS = _setting("KNOBS_TO_MACROS", True)
MACRO_CCS = list(_setting("MACRO_CCS", [56, 57, 58, 59, 60, 61, 62, 63]))

PATCHER_IS_SERUM_HOST = _setting("PATCHER_IS_SERUM_HOST", True)
PATCHER_CHANNEL_FILTER = _setting("PATCHER_CHANNEL_FILTER", "")

PREVIEW_ENABLED = _setting("PREVIEW_ENABLED", True)
PREVIEW_NOTES = list(_setting("PREVIEW_NOTES", [60]))
PREVIEW_VELOCITY = _setting("PREVIEW_VELOCITY", 100)
PREVIEW_DELAY_MS = _setting("PREVIEW_DELAY_MS", 250)
PREVIEW_LENGTH_MS = _setting("PREVIEW_LENGTH_MS", 800)

DEBUG = _setting("DEBUG", False)

EDGE_GAP_MS = 20            # between the CC=0 and CC=127 halves of one step

# KeyLab Essential mk3, DAW mode
CC_CONTEXT3 = 46
CC_CONTEXT4 = 47
CC_MAIN_ENCODER = 116       # relative: >64 clockwise, <64 counter-clockwise
CC_KNOBS = (96, 97, 98, 99, 100, 101, 102, 103)   # knobs 1-8, absolute 0-127

# Serum 2 lists its 8 macros right after this parameter. Presets rename the
# macros (e.g. "DRIVE"), so they're found by position, not by name.
MACRO_ANCHOR_PARAM = "Mod 64 Out"

WID_PLUGIN = 5
SYSEX_HEADER = [0xF0, 0x00, 0x20, 0x6B, 0x7F, 0x42]


def _log(*parts):
    if DEBUG:
        print("Serum Bridge:", *parts)


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
    print("Serum Bridge: set ARTURIA_DIR in serum_bridge_config.py. Running Serum control only.")


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
preview_channel = None  # channel the preview is sounding on
serum_channel = None    # channel of the focused Serum (or of its Patcher)
held_notes = set()      # keys/pads currently held on the KeyLab
macro_first_param = None    # param index of Macro 1; same for every Serum 2 instance


def now_ms():
    return time.monotonic() * 1000.0


# --------------------------------------------------------------- helpers ----

def _safe(fn, *args):
    try:
        return fn(*args)
    except Exception:
        return None


def _send_sysex(data):
    _safe(device.midiOutSysex, bytes(SYSEX_HEADER + data + [0xF7]))


def _ascii(text, maxlen=16):
    text = "".join(c if 32 <= ord(c) <= 126 else "?" for c in str(text))
    return [ord(c) for c in text[:maxlen]]


def show(line1, line2):
    """Two-line transient popup; the KeyLab returns to Arturia's screen afterwards."""
    _send_sysex([0x04, 0x01, 0x60, 0x12, 0x01] + _ascii(line1) + [0x00, 0x02]
                + _ascii(line2) + [0x00, 0x01])


def _show_knob(name, value):
    """Arturia's knob popup (name, percentage, ring), or a plain popup as fallback."""
    percent = "%d%%" % round(value * 100 / 127)
    try:
        arturia._KLEss3.paged_display().SetCenterPage(
            14, line1=name, line2=percent, hw_value=value, transient=1)
    except Exception:
        show(name, percent)


def _selected_channel():
    try:
        return channels.selectedChannel(0, 0, 1)    # global index
    except TypeError:
        return channels.selectedChannel()


def _plugin_name(index):
    try:
        return str(plugins.getPluginName(index, -1, False, True))
    except TypeError:
        return str(plugins.getPluginName(channels.selectedChannel()))


def _channel_name(index):
    try:
        return str(channels.getChannelName(index, True))
    except TypeError:
        return str(channels.getChannelName(index))


def focused_serum():
    """(channel, direct) when a Serum 2 window is focused, else (None, False).

    direct=True: Serum is the channel's plugin, so its parameters can be set.
    direct=False: Serum sits inside Patcher. FL reports every window inside
    Patcher as Patcher itself, so a focused Patcher channel counts; Serum is
    then reached via MIDI only, and 'channel' is the Patcher's (for the preview).
    """
    if not _safe(ui.getFocused, WID_PLUGIN):
        return None, False
    index = _safe(_selected_channel)
    if index is None:
        return None, False
    name = _safe(_plugin_name, index) or ""
    if "serum 2" in name.lower() and "fx" not in name.lower():
        return index, True
    if PATCHER_IS_SERUM_HOST and name == "Patcher":
        channel_name = _safe(_channel_name, index) or ""
        if not PATCHER_CHANNEL_FILTER or PATCHER_CHANNEL_FILTER.lower() in channel_name.lower():
            return index, False
    return None, False


def _forward_cc(cc, value):
    """Send a CC to the plugins listening on SERUM_PORT (port in the message's top byte)."""
    device.forwardMIDICC(0xB0 | (cc << 8) | (value << 16) | (SERUM_PORT << 24), FORWARD_MODE)


def _note(channel, note, velocity):
    try:
        channels.midiNoteOn(channel, note, velocity)
    except Exception as e:
        print("Serum Bridge: preview note failed:", e)


# ---------------------------------------------------------------- presets ----

def stop_preview():
    global preview_off_ms, preview_channel
    if preview_channel is not None:
        for n in PREVIEW_NOTES:
            _note(preview_channel, n, 0)
    preview_channel = None
    preview_off_ms = None


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
            _forward_cc(cc, 0)          # arm the rising edge
            step_high = True
            next_step_ms = t + EDGE_GAP_MS
            return
        _forward_cc(cc, 127)            # Serum steps here
        _log("sent CC%d 0/127 to port %d" % (cc, SERUM_PORT))
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


# ---------------------------------------------------------------- macros ----

def _param_name(param, channel):
    try:
        return str(plugins.getParamName(param, channel, -1, True))
    except TypeError:
        return str(plugins.getParamName(param, channel))


def _find_macros(channel):
    """Locate Macro 1's parameter index once (it doesn't change between presets)."""
    global macro_first_param
    if macro_first_param is not None:
        return macro_first_param
    macro_first_param = -1
    try:
        try:
            count = plugins.getParamCount(channel, -1, True)
        except TypeError:
            count = plugins.getParamCount(channel)
        for i in range(count):
            name = _param_name(i, channel)
            if name == MACRO_ANCHOR_PARAM:
                macro_first_param = i + 1
                break
            if name == "Macro 1" and macro_first_param < 0:
                macro_first_param = i
    except Exception as e:
        print("Serum Bridge: macro lookup failed:", e)
    if macro_first_param < 0:
        print("Serum Bridge: Serum's macro parameters not found; knobs stay with Arturia's script.")
    return macro_first_param


def set_macro(channel, knob, value):
    """Serum directly on a channel: set the macro parameter."""
    first = _find_macros(channel)
    if first < 0:
        return False
    param = first + knob
    try:
        plugins.setParamValue(value / 127.0, param, channel, -1, 0, True)
    except TypeError:
        plugins.setParamValue(value / 127.0, param, channel)
    _show_knob(_param_name(param, channel), value)
    return True


def send_macro_cc(knob, value):
    """Serum inside Patcher: its parameters can't be reached, so send a CC that
    the macro has been MIDI-learned to (right-click macro > MIDI Learn)."""
    if not MACRO_CCS:
        return False
    try:
        _forward_cc(MACRO_CCS[knob], value)
    except Exception as e:
        print("Serum Bridge: forwardMIDICC failed:", e)
        return False
    _show_knob("Macro %d" % (knob + 1), value)
    return True


# ------------------------------------------------------------- dispatch ----

def _handle_serum_event(event):
    """Return True if the event was a Serum control (browse or macro) and has been used."""
    global serum_channel
    if (event.status & 0xF0) != 0xB0:
        return False
    cc, value = event.data1, event.data2
    is_knob = KNOBS_TO_MACROS and cc in CC_KNOBS
    if cc not in (CC_CONTEXT3, CC_CONTEXT4, CC_MAIN_ENCODER) and not is_knob:
        return False
    channel, direct = focused_serum()
    if channel is None:
        return False
    serum_channel = channel
    if is_knob:
        knob = CC_KNOBS.index(cc)
        return set_macro(channel, knob, value) if direct else send_macro_cc(knob, value)
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
