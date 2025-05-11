# code.py
import board
import time
import analogio
import busio
import sdcardio
import storage
import audiobusio # For I2S
# Alternatively, for PWM audio (simpler setup, lower quality):
# import audiopwmio

import config_cp as config
from audio_manager_cp import AudioManagerCP
from engine_simulator_cp import EngineSimulatorCP, EngineState # Make sure EngineState is imported

# --- Global Variables ---
audio_manager = None
engine_simulator = None
potentiometer = None
i2s_audio = None # Or pwm_audio = None

# --- Hardware Setup ---
# 1. Potentiometer (Throttle Simulator)
# Connect to an ADC pin. ESP32: IO32-IO39 are ADC1, IO0-IO19 for ADC2 (ADC2 used by WiFi)
# For ESP32-S3, check pinout. Example: board.A0 or a specific IOxx pin.
# Let's use a common ADC pin, e.g., IO36 (often labeled A0 or SVP on dev boards)
# If board.A0 isn't defined, use the specific IO pin.
THROTTLE_PIN = board.IO36 # Verify this pin is ADC capable on your ESP32 board
try:
    potentiometer = analogio.AnalogIn(THROTTLE_PIN)
    print(f"MAIN_APP: Potentiometer initialized on {THROTTLE_PIN}")
except Exception as e:
    print(f"MAIN_APP: FATAL - Failed to initialize potentiometer on {THROTTLE_PIN}: {e}")
    potentiometer = None # Ensure it's None if init fails

# 2. SD Card
# Standard SPI pins for ESP32: SCK=IO18, MOSI=IO23, MISO=IO19, CS=IO5
# These can vary by board, check your board's documentation.
SD_CS_PIN = board.IO5    # Example CS pin
SD_SPI_SCK = board.IO18
SD_SPI_MOSI = board.IO23
SD_SPI_MISO = board.IO19
sd_card = None
try:
    spi = busio.SPI(clock=SD_SPI_SCK, MOSI=SD_SPI_MOSI, MISO=SD_SPI_MISO)
    sd_card = sdcardio.SDCard(spi, SD_CS_PIN)
    vfs = storage.VfsFat(sd_card)
    storage.mount(vfs, "/sd")
    print("MAIN_APP: SD card mounted successfully at /sd")
except Exception as e:
    print(f"MAIN_APP: FATAL - Failed to initialize/mount SD card: {e}")
    # Application cannot proceed without SD card for sounds
    while True: time.sleep(1)


# 3. Audio Output (I2S DAC - e.g., MAX98357A)
# Common I2S pins for ESP32: BCLK=IO25, LRC/WS=IO26, DIN/DOUT=IO22
# These are just examples, ensure they match your DAC connections.
# If using adafruit_max98357a.py library, it might simplify this.
# For generic I2S:
I2S_BIT_CLOCK_PIN = board.IO25 # BCLK
I2S_WORD_SELECT_PIN = board.IO26 # LRC or WS
I2S_DATA_PIN = board.IO22        # DIN or DOUT (Data from ESP32 to DAC)
try:
    i2s_audio = audiobusio.I2SOut(I2S_BIT_CLOCK_PIN, I2S_WORD_SELECT_PIN, I2S_DATA_PIN)
    print("MAIN_APP: I2S Audio Output initialized.")
except Exception as e:
    print(f"MAIN_APP: FATAL - Failed to initialize I2S audio: {e}")
    # Application cannot proceed without audio output
    while True: time.sleep(1)

# --- Optional: PWM Audio (if no I2S DAC) ---
# Simpler, uses one pin, but lower quality. Comment out I2S if using PWM.
# PWM_AUDIO_PIN = board.IO25 # Example pin, must be PWM capable
# try:
#     # For ESP32, audiopwmio might require a board specific build or an audiomixer trick
#     # If audiopwmio not available directly, some use audiocore.RawSample and play on PWMOut
#     # However, I2S is preferred for quality. Let's assume I2S works.
#     # pwm_audio = audiopwmio.PWMAudioOut(PWM_AUDIO_PIN)
#     # print("MAIN_APP: PWM Audio Output initialized.")
#     pass # Placeholder
# except Exception as e:
#     print(f"MAIN_APP: FATAL - Failed to initialize PWM audio: {e}")
#     while True: time.sleep(1)


# --- Application Initialization ---
print("MAIN_APP: Initializing Application Logic...")
try:
    # Pass the initialized I2S (or PWM) audio output to AudioManagerCP
    audio_output_device = i2s_audio # or pwm_audio if you set that up
    if audio_output_device:
        audio_manager = AudioManagerCP(audio_output_device)
        engine_simulator = EngineSimulatorCP(audio_manager)
        print("MAIN_APP: Audio Manager and Engine Simulator initialized.")
    else:
        raise RuntimeError("Audio output device not initialized.")

except Exception as e:
    print(f"MAIN_APP: FATAL - Error initializing app components: {e}")
    # Optionally, blink an LED or provide other visual error indication
    while True:
        # Simple error blink using onboard LED if available (e.g., NeoPixel)
        try:
            import neopixel
            led = neopixel.NeoPixel(board.NEOPIXEL, 1)
            led.brightness = 0.1
            while True:
                led[0] = (255,0,0)
                time.sleep(0.5)
                led[0] = (0,0,0)
                time.sleep(0.5)
        except:
            time.sleep(1) # Fallback if no neopixel

# --- Main Loop ---
# Simulating your Start/Stop buttons (optional, can be physical buttons later)
# For now, let's assume the engine starts automatically for testing, or use REPL.
# To start/stop via REPL:
# import code
# code.engine_simulator.start_engine()
# code.engine_simulator.stop_engine()

# Auto-start for testing:
if engine_simulator and engine_simulator.get_state() == EngineState.OFF:
    print("MAIN_APP: Auto-starting engine for testing...")
    engine_simulator.start_engine()

# Target FPS for the main logic loop
# The audio itself is mixed/played by DMA, so this loop rate is for control logic.
TARGET_FPS = 60 # Start with 60, can try higher/lower. 120 might be too fast for Python on ESP32.
TARGET_SLEEP_TIME = 1.0 / TARGET_FPS
last_loop_print_time = time.monotonic()

print("MAIN_APP: Entering main loop...")
while True:
    loop_start_time = time.monotonic()

    # 1. Read Throttle Input
    throttle_input = 0.0
    if potentiometer:
        # ADC range is 0-65535. Normalize to 0.0-1.0
        # Some pots might not use the full range, or might be reversed.
        # Add a small dead zone at the bottom if needed.
        raw_adc = potentiometer.value
        throttle_input = raw_adc / 65535.0
        # Optional: reverse if pot is wired backward for your preference
        # throttle_input = 1.0 - throttle_input
        throttle_input = max(0.0, min(1.0, throttle_input)) # Clamp
    
    # 2. Update Engine Simulator
    if engine_simulator:
        engine_simulator.set_throttle(throttle_input)
        engine_simulator.update() # This also calls audio_manager.update() internally for sound changes

    # 3. (Optional) Update Status (e.g., LEDs)
    # Example: if engine_simulator.get_state() == EngineState.RUNNING: onboard_led.value = True
    
    # 4. Print loop diagnostic periodically
    current_time = time.monotonic()
    if current_time - last_loop_print_time > 5.0: # Print every 5 seconds
        if engine_simulator:
             print(f"Loop: RPM={engine_simulator.get_rpm():.0f} Thr={throttle_input:.2f} State={engine_simulator.get_state()}")
        last_loop_print_time = current_time

    # 5. Maintain Loop Rate
    loop_end_time = time.monotonic()
    processing_time = loop_end_time - loop_start_time
    sleep_time = TARGET_SLEEP_TIME - processing_time
    if sleep_time > 0:
        time.sleep(sleep_time)
    # else:
    #     print(f"MAIN_APP: Loop took too long: {processing_time*1000:.2f} ms")