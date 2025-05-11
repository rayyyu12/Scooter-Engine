# code.py
import board
import time
import analogio
import busio
import sdcardio
import storage
import audiobusio 

import config_cp as config
from audio_manager_cp import AudioManagerCP
from engine_simulator_cp import EngineSimulatorCP, EngineState 

# --- Global Variables ---
audio_manager = None
engine_simulator = None
potentiometer = None
i2s_audio = None 

# --- Hardware Setup ---
# 1. Potentiometer 
THROTTLE_PIN = board.IO36 
try:
    potentiometer = analogio.AnalogIn(THROTTLE_PIN)
    print(f"MAIN_APP: Potentiometer initialized on {THROTTLE_PIN}")
except Exception as e:
    print(f"MAIN_APP: FATAL - Failed to initialize potentiometer on {THROTTLE_PIN}: {e}")
    potentiometer = None 

# 2. SD Card
SD_CS_PIN = board.IO5    
SD_SPI_SCK = board.IO18
SD_SPI_MOSI = board.IO23
SD_SPI_MISO = board.IO19
sd_card = None
vfs = None
try:
    spi = busio.SPI(clock=SD_SPI_SCK, MOSI=SD_SPI_MOSI, MISO=SD_SPI_MISO)
    sd_card = sdcardio.SDCard(spi, SD_CS_PIN)
    vfs = storage.VfsFat(sd_card)
    storage.mount(vfs, "/sd")
    print("MAIN_APP: SD card mounted successfully at /sd")
except Exception as e:
    print(f"MAIN_APP: FATAL - Failed to initialize/mount SD card: {e}")
    while True: time.sleep(1) # Halt on SD error

# 3. Audio Output (I2S DAC)
I2S_BIT_CLOCK_PIN = board.IO25 
I2S_WORD_SELECT_PIN = board.IO26 
I2S_DATA_PIN = board.IO22        
try:
    i2s_audio = audiobusio.I2SOut(I2S_BIT_CLOCK_PIN, I2S_WORD_SELECT_PIN, I2S_DATA_PIN)
    print("MAIN_APP: I2S Audio Output initialized.")
except Exception as e:
    print(f"MAIN_APP: FATAL - Failed to initialize I2S audio: {e}")
    while True: time.sleep(1) # Halt on audio error


# --- Application Initialization ---
print("MAIN_APP: Initializing Application Logic...")
try:
    audio_output_device = i2s_audio
    if audio_output_device:
        audio_manager = AudioManagerCP(audio_output_device)
        engine_simulator = EngineSimulatorCP(audio_manager)
        print("MAIN_APP: Audio Manager and Engine Simulator initialized.")
    else:
        raise RuntimeError("Audio output device not initialized (I2S failed).")

except Exception as e:
    print(f"MAIN_APP: FATAL - Error initializing app components: {e}")
    # Basic error blink if NeoPixel is available
    try:
        import neopixel
        led = neopixel.NeoPixel(board.NEOPIXEL, 1, auto_write=False)
        led.brightness = 0.1
        while True:
            led[0] = (255,0,0); led.show()
            time.sleep(0.5)
            led[0] = (0,0,0); led.show()
            time.sleep(0.5)
    except ImportError: # No NeoPixel
        print("MAIN_APP: No NeoPixel for error indication.")
        while True: time.sleep(1) # Halt
    except Exception as e_led:
        print(f"MAIN_APP: Error with NeoPixel indication: {e_led}")
        while True: time.sleep(1) # Halt

# --- Main Loop ---
if engine_simulator and engine_simulator.get_state() == EngineState.OFF:
    print("MAIN_APP: Auto-starting engine for testing...")
    engine_simulator.start_engine()

TARGET_FPS = 60 
TARGET_SLEEP_TIME = 1.0 / TARGET_FPS
last_loop_print_time = time.monotonic()
loop_counter = 0

print("MAIN_APP: Entering main loop...")
while True:
    loop_start_time = time.monotonic()
    loop_counter += 1

    throttle_input = 0.0
    if potentiometer:
        raw_adc = potentiometer.value
        throttle_input = raw_adc / 65535.0
        throttle_input = max(0.0, min(1.0, throttle_input))
    
    if engine_simulator:
        engine_simulator.set_throttle(throttle_input)
        engine_simulator.update() 
    
    current_time_mono = time.monotonic()
    if current_time_mono - last_loop_print_time >= 5.0: # Print every 5 seconds
        if engine_simulator:
             print(f"Loop {loop_counter}: RPM={engine_simulator.get_rpm():.0f} Thr={throttle_input:.2f} State={engine_simulator.get_state()}")
        last_loop_print_time = current_time_mono

    processing_time = time.monotonic() - loop_start_time
    sleep_time = TARGET_SLEEP_TIME - processing_time
    if sleep_time > 0:
        time.sleep(sleep_time)
    # else:
    #     print(f"MAIN_APP: Loop {loop_counter} took too long: {processing_time*1000:.2f} ms")