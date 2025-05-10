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
    "accel_burst": 3.57, # Used for accel burst effect timing
    "decel_pop": 6.74,   # Full duration of the decel pop sound
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
RPM_IDLE_RETURN_RATE = 1500 # Rate when throttle is 0 and returning to idle (not during pop linger)
RPM_INERTIA_FACTOR = 0.05 # Not heavily used with current direct rate approach

# --- Audio Playback ---
MAIN_ENGINE_VOLUME = 0.7
SFX_VOLUME = 0.8 # Base volume for SFX
CROSSFADE_DURATION_MS = 450

# --- Load Simulation (Basic) ---
LOAD_THRESHOLD_DECEL = -2000

# --- Optional Features ---
ENABLE_ACCEL_BURST = True
ACCEL_BURST_THROTTLE_THRESHOLD = 0.5 # Make it a more significant jump: new_throttle > old_throttle + this
ACCEL_BURST_MIN_NEW_THROTTLE = 0.7  # New throttle must be at least this high
ACCEL_BURST_MAX_OLD_THROTTLE = 0.3  # Old throttle must have been below this
ACCEL_BURST_COOLDOWN_MS = 300      # Cooldown for the SFX itself
ACCEL_BURST_EFFECT_DURATION_MULTIPLIER = 0.85 # Multiplier for SOUND_DURATIONS["accel_burst"] for engine sound suppression
ACCEL_BURST_SFX_VOLUME_MULTIPLIER = 1.15 # Multiplier for SFX_VOLUME for this specific sound

ENABLE_DECEL_POPS = True
DECEL_POP_RPM_THRESHOLD = 1500
DECEL_POP_CHANCE = 0.75 # Chance to play if conditions met
DECEL_POP_COOLDOWN_MS = 200 # Cooldown for the SFX itself
DECEL_POP_LINGER_DURATION_S = 4.8  # <<< INCREASED: How long RPM fall rate & sound loop are modified
DECEL_POP_RPM_FALL_RATE_MODIFIER = 0.45 # <<< ADJUSTED: Makes RPM fall slower (0.1 very slow, 1.0 no change)
DECEL_POP_SFX_VOLUME_MULTIPLIER = 0.9 # Multiplier for SFX_VOLUME for this specific sound

# --- Pygame Mixer Settings ---
MIXER_FREQUENCY = 44100
MIXER_SIZE = -16
MIXER_CHANNELS = 2
MIXER_BUFFER_SIZE = 1024
NUM_AUDIO_CHANNELS = 8