# config_cp.py
# Configuration for CircuitPython ESP32 Sound Simulator

# --- Audio File Paths (Must be on SD card in a 'sounds' folder) ---
SOUND_DIR = "/sd/sounds" 
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
CROSSFADE_DURATION_S = 0.450 

# --- CircuitPython Audio Settings ---
AUDIO_SAMPLE_RATE = 22050 
NUM_MIXER_VOICES = 6      
ENGINE_LOOP_VOICE_1 = 0   
ENGINE_LOOP_VOICE_2 = 1   
SFX_STARTSHUT_VOICE = 2   
SFX_ACCEL_VOICE = 3       
SFX_DECEL_VOICE = 4       

# --- Optional Features ---
ENABLE_ACCEL_BURST = True
# New Accel Burst Config (Gesture Based)
ACCEL_BURST_HISTORY_DURATION_S = 0.3  # How long to keep throttle history for flick detection
ACCEL_BURST_FLICK_WINDOW_S = 0.2    # Max duration of a "flick" gesture (e.g., 0 to 100% in < 0.2s)
ACCEL_BURST_MIN_END_THROTTLE = 0.90   # Throttle must end at/above this for flick burst (e.g., 90%)
ACCEL_BURST_MAX_START_THROTTLE = 0.60 # Throttle must have started at/below this in the flick window (e.g., 60% or less)
ACCEL_BURST_MIN_JUMP_VALUE = 0.35     # Minimum throttle increase during the flick (e.g., 0.60 to 0.95 is a 0.35 jump)
ACCEL_BURST_COOLDOWN_S = 0.500 # Cooldown in seconds (was ACCEL_BURST_COOLDOWN_MS)
ACCEL_BURST_EFFECT_DURATION_MULTIPLIER = 0.9 # How much of the SFX sound duration the effect lasts
ACCEL_BURST_SFX_VOLUME_MULTIPLIER = 1.2 

ENABLE_DECEL_POPS = True
# New Decel Pop Config (Gesture Based)
DECEL_POP_HIGH_THROTTLE_THRESHOLD = 0.85 # Throttle must have been at/above this before drop
DECEL_POP_LOW_THROTTLE_THRESHOLD = 0.20  # Throttle must drop to/below this
DECEL_POP_MAX_FLICK_DURATION_S = 0.25  # Max duration of the throttle drop gesture
DECEL_POP_MIN_DROP_VALUE = 0.60        # Minimum throttle decrease during the flick (e.g. 0.85 to 0.20 is 0.65 drop)
DECEL_POP_RPM_THRESHOLD = 1500         # RPM must be above this for pop to occur after gesture
DECEL_POP_RPM_CHECK_WINDOW_S = 0.20    # How long after gesture to wait for RPM to be correct
DECEL_POP_CHANCE = 0.9                 # Chance to play if conditions are met
DECEL_POP_COOLDOWN_S = 0.500 # Cooldown in seconds (was DECEL_POP_COOLDOWN_MS)
DECEL_POP_LINGER_DURATION_S = 4.0 # How long the *effect* (background sound override) lasts
DECEL_POP_RPM_FALL_RATE_MODIFIER = 0.35 # Slows RPM fall during linger
DECEL_POP_SFX_VOLUME_MULTIPLIER = 0.95

# --- Cruise Feature ---
ENABLE_CRUISE_SOUND = True
CRUISE_THROTTLE_ENTER_THRESHOLD = 0.98
CRUISE_THROTTLE_MAINTAIN_THRESHOLD = 0.95
CRUISE_RPM_THRESHOLD = MAX_RPM - 150
CRUISE_HIGH_RPM_SUSTAIN_S = SOUND_DURATIONS["high_rpm"] * 0.8

# --- General Throttle Jitter Tolerance ---
THROTTLE_EFFECTIVELY_ZERO = 0.05
THROTTLE_SIGNIFICANTLY_OPEN = 0.10 # Used to cancel decel pop linger effect