# config.py
import os

# --- Audio File Paths ---
SOUND_DIR = "sounds"
SOUND_FILES = {
    "starter": os.path.join(SOUND_DIR, "engine_starter.wav"),
    "shutdown": os.path.join(SOUND_DIR, "engine_shutdown.wav"),
    "idle": os.path.join(SOUND_DIR, "engine_idle_loop.wav"),
    "low_rpm": os.path.join(SOUND_DIR, "engine_low_rpm_loop.wav"),
    "mid_rpm": os.path.join(SOUND_DIR, "engine_mid_rpm_loop.wav"),
    "high_rpm": os.path.join(SOUND_DIR, "engine_high_rpm_loop.wav"),
    "cruise": os.path.join(SOUND_DIR, "cruise.wav"),
    "accel_burst": os.path.join(SOUND_DIR, "quick_accel_burst.wav"),
    "decel_pop": os.path.join(SOUND_DIR, "decel_pop1.wav"),
}

# --- Audio File Durations (Approximate, in seconds) ---
SOUND_DURATIONS = {
    "starter": 5.37,
    "shutdown": 5.37,
    "idle": 9.91,
    "low_rpm": 5.14,
    "mid_rpm": 10.38,
    "high_rpm": 10.64,
    "cruise": 21.0, 
    "accel_burst": 3.57,
    "decel_pop": 6.74,
}

# --- Engine Simulation ---
MIN_RPM = 800
MAX_RPM = 7000
IDLE_RPM = 900
STARTER_SOUND_DURATION_TARGET_S = SOUND_DURATIONS["starter"]
STARTER_TIMEOUT_S = SOUND_DURATIONS["starter"] + 0.5

RPM_RANGES = {
    "idle": (MIN_RPM, 1200),
    "low_rpm": (1000, 2800),
    "mid_rpm": (2500, 4800),
    "high_rpm": (4500, MAX_RPM),
}

RPM_ACCEL_RATE = 7000
RPM_DECEL_RATE = 6000
RPM_IDLE_RETURN_RATE = 1500

# --- Audio Playback ---
MAIN_ENGINE_VOLUME = 0.7
SFX_VOLUME = 0.8
CROSSFADE_DURATION_MS = 450

# --- Optional Features ---
ENABLE_ACCEL_BURST = True
ACCEL_BURST_HISTORY_DURATION_S = 0.3
ACCEL_BURST_FLICK_WINDOW_S = 0.2
ACCEL_BURST_MIN_END_THROTTLE = 0.90
ACCEL_BURST_MAX_START_THROTTLE = 0.60
ACCEL_BURST_MIN_JUMP_VALUE = 0.35
ACCEL_BURST_COOLDOWN_MS = 500
ACCEL_BURST_EFFECT_DURATION_MULTIPLIER = 0.9 
ACCEL_BURST_SFX_VOLUME_MULTIPLIER = 1.2 

ENABLE_DECEL_POPS = True
DECEL_POP_HIGH_THROTTLE_THRESHOLD = 0.85
DECEL_POP_LOW_THROTTLE_THRESHOLD = 0.20
DECEL_POP_MAX_FLICK_DURATION_S = 0.25
DECEL_POP_MIN_DROP_VALUE = 0.60
DECEL_POP_RPM_THRESHOLD = 1500
DECEL_POP_RPM_CHECK_WINDOW_S = 0.20
DECEL_POP_CHANCE = 0.9
DECEL_POP_COOLDOWN_MS = 500
DECEL_POP_LINGER_DURATION_S = 4.0
DECEL_POP_RPM_FALL_RATE_MODIFIER = 0.35
DECEL_POP_SFX_VOLUME_MULTIPLIER = 0.95

# --- Cruise Feature ---
ENABLE_CRUISE_SOUND = True
CRUISE_THROTTLE_ENTER_THRESHOLD = 0.98
CRUISE_THROTTLE_MAINTAIN_THRESHOLD = 0.95
CRUISE_RPM_THRESHOLD = MAX_RPM - 150
CRUISE_HIGH_RPM_SUSTAIN_S = SOUND_DURATIONS["high_rpm"] * 0.8 

# --- General Throttle Jitter Tolerance ---
THROTTLE_EFFECTIVELY_ZERO = 0.05 
THROTTLE_SIGNIFICANTLY_OPEN = 0.10 # Restored: Used to cancel decel pop linger effect

# --- Pygame Mixer Settings ---
MIXER_FREQUENCY = 44100
MIXER_SIZE = -16
MIXER_CHANNELS = 2
MIXER_BUFFER_SIZE = 1024
NUM_AUDIO_CHANNELS = 8