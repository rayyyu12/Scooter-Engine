# config_cp.py
# Configuration for CircuitPython ESP32 Sound Simulator

# --- Audio File Paths (Must be on SD card in a 'sounds' folder) ---
# Ensure these are 16-bit WAV files, preferably mono, and at a consistent sample rate (e.g., 22050Hz or 44100Hz)
# Shorter sample rates and mono will save memory and CPU on the ESP32.
SOUND_DIR = "/sd/sounds" # Path on the ESP32's SD card
SOUND_FILES = {
    "starter": f"{SOUND_DIR}/engine_starter.wav",
    "shutdown": f"{SOUND_DIR}/engine_shutdown.wav",
    "idle": f"{SOUND_DIR}/engine_idle_loop.wav",
    "low_rpm": f"{SOUND_DIR}/engine_low_rpm_loop.wav",
    "mid_rpm": f"{SOUND_DIR}/engine_mid_rpm_loop.wav",
    "high_rpm": f"{SOUND_DIR}/engine_high_rpm_loop.wav",
    "cruise": f"{SOUND_DIR}/cruise.wav",
    "accel_burst": f"{SOUND_DIR}/quick_accel_burst.wav",
    "decel_pop": f"{SOUND_DIR}/decel_pop1.wav",
}

# --- Audio File Durations (Approximate, in seconds) ---
# These are used by the engine simulator for timing certain state transitions
# and effects. Ensure they are reasonably accurate.
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
MAX_RPM = 7000 # Adjust if your sounds are designed for a different max
IDLE_RPM = 900
STARTER_SOUND_DURATION_TARGET_S = SOUND_DURATIONS["starter"]
STARTER_TIMEOUT_S = SOUND_DURATIONS["starter"] + 0.5

RPM_RANGES = { # RPM ranges for selecting sound loops
    "idle": (MIN_RPM, 1200),
    "low_rpm": (1000, 2800),
    "mid_rpm": (2500, 4800),
    "high_rpm": (4500, MAX_RPM),
}

RPM_ACCEL_RATE = 7000 # RPM increase per second
RPM_DECEL_RATE = 6000 # RPM decrease per second
RPM_IDLE_RETURN_RATE = 1500 # RPM decrease per second when returning to idle

# --- Audio Playback ---
# For CircuitPython audiomixer, levels are 0.0 to 1.0
MAIN_ENGINE_VOLUME = 0.7  # Default volume for engine loops
SFX_VOLUME = 0.8          # Default volume for SFX
CROSSFADE_DURATION_S = 0.450 # Crossfade duration in seconds (was MS)

# --- CircuitPython Audio Settings ---
AUDIO_SAMPLE_RATE = 22050 # IMPORTANT: All your WAV files should ideally be this sample rate.
                          # 44100Hz is CD quality but more demanding. 22050Hz is often good enough.
                          # MONO WAV files are strongly recommended to save memory/CPU.
NUM_MIXER_VOICES = 6      # Number of voices for the audiomixer.
                          # 2 for engine loops (crossfading)
                          # 1 for starter/shutdown
                          # 1 for accel_burst
                          # 1 for decel_pop
                          # +1 spare or for more complex SFX layering
ENGINE_LOOP_VOICE_1 = 0   # Mixer voice index for first engine loop
ENGINE_LOOP_VOICE_2 = 1   # Mixer voice index for second engine loop (for crossfading)
SFX_STARTSHUT_VOICE = 2   # Mixer voice index for starter/shutdown
SFX_ACCEL_VOICE = 3       # Mixer voice index for accel bursts
SFX_DECEL_VOICE = 4       # Mixer voice index for decel pops

# --- Load Simulation (Basic) ---
LOAD_THRESHOLD_DECEL = -2000 # RPM change rate to trigger decel effects

# --- Optional Features ---
ENABLE_ACCEL_BURST = True
ACCEL_BURST_THROTTLE_THRESHOLD = 0.45
ACCEL_BURST_MIN_NEW_THROTTLE = 0.6
ACCEL_BURST_MAX_OLD_THROTTLE = 0.25
ACCEL_BURST_COOLDOWN_S = 0.250 # Cooldown in seconds (was MS)
ACCEL_BURST_EFFECT_DURATION_MULTIPLIER = 0.9
ACCEL_BURST_SFX_VOLUME_MULTIPLIER = 1.2
ACCEL_BURST_BASELINE_CREEP_THRESHOLD = 0.05

ENABLE_DECEL_POPS = True
DECEL_POP_RPM_THRESHOLD = 1500
DECEL_POP_CHANCE = 0.8
DECEL_POP_COOLDOWN_S = 0.150 # Cooldown in seconds (was MS)
DECEL_POP_LINGER_DURATION_S = 5.8
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
THROTTLE_SIGNIFICANTLY_OPEN = 0.10