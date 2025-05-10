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
# Useful for specific state timings, like starter.
SOUND_DURATIONS = {
    "starter": 4.8,  # Adjusted: engine_starter.wav is 5 seconds, allow slight early cut for blending
    "shutdown": 4.8, # engine_shutdown.wav is 5 seconds
    # Loops don't strictly need duration here for playback logic, but can be informative
    "idle": 9.0,
    "low_rpm": 5.0,
    "mid_rpm": 10.0,
    "high_rpm": 10.0,
    "accel_burst": 3.0,
    "decel_pop": 6.0,
}


# --- Engine Simulation ---
MIN_RPM = 800
MAX_RPM = 7000
IDLE_RPM = 900
# Adjusted to better match the starter sound length
STARTER_SOUND_DURATION_TARGET_S = SOUND_DURATIONS["starter"]
# Max time for start, slightly longer than target, or a fixed reasonable time
STARTER_TIMEOUT_S = SOUND_DURATIONS["starter"] + 0.5 # Give a little buffer


RPM_RANGES = {
    "idle": (MIN_RPM, 1200),
    "low_rpm": (1000, 2800), # Overlap for smoother transitions
    "mid_rpm": (2500, 4800), # Overlap
    "high_rpm": (4500, MAX_RPM), # Overlap
}

RPM_ACCEL_RATE = 7000  # RPM increase per second with full throttle (adjust for feel)
RPM_DECEL_RATE = 6000  # RPM decrease per second with zero throttle (adjust for feel)
RPM_IDLE_RETURN_RATE = 1500 # RPM decrease rate when returning to idle without throttle
RPM_INERTIA_FACTOR = 0.05 # Lower value means RPM changes faster, higher means more sluggish

# --- Audio Playback ---
MAIN_ENGINE_VOLUME = 0.7 # Slightly reduced to avoid clipping with SFX
SFX_VOLUME = 0.8
CROSSFADE_DURATION_MS = 450 # Increased for potentially smoother transitions
# LOOP_CHECK_INTERVAL_MS = 50 # Not currently used, can be removed

# --- Throttle Simulation ---
# VIRTUAL_THROTTLE_UPDATE_INTERVAL_MS = 20 # Not directly used, simulation loop runs at its own pace

# --- Load Simulation (Basic) ---
LOAD_THRESHOLD_DECEL = -2000

# --- Optional Features ---
ENABLE_ACCEL_BURST = True
ACCEL_BURST_THROTTLE_THRESHOLD = 0.3
ACCEL_BURST_COOLDOWN_MS = 300 # Reduced cooldown

ENABLE_DECEL_POPS = True
DECEL_POP_RPM_THRESHOLD = 1500
DECEL_POP_CHANCE = 0.35
DECEL_POP_COOLDOWN_MS = 150 # Reduced cooldown

# --- Pygame Mixer Settings ---
MIXER_FREQUENCY = 44100
MIXER_SIZE = -16
MIXER_CHANNELS = 2 # Stereo
MIXER_BUFFER_SIZE = 1024 # Can try reducing for lower latency, but 2048 is often safer
NUM_AUDIO_CHANNELS = 8