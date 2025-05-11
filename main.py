# main.py
import tkinter as tk
from tkinter import ttk
import time
import config
from audio_manager import AudioManager
from engine_simulator import EngineSimulator, EngineState
import threading
import pygame # Keep pygame import here

# --- Pygame Initialization ---
pygame.init()
print("MAIN_APP: Pygame initialized (pygame.init()).")

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Electric Scooter Sound Simulator")
        self.root.geometry("400x350")

        self.running = True
        self.audio_manager = None
        self.engine_simulator = None

        self._init_ui()

        print("MAIN_APP: Initializing and starting simulation thread...")
        self.simulation_thread = threading.Thread(target=self._simulation_init_and_loop, daemon=True)
        self.simulation_thread.start()
        print("MAIN_APP: Simulation thread has been started.")

        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _init_ui(self):
        self.rpm_label = ttk.Label(self.root, text="RPM: 0", font=("Arial", 16))
        self.rpm_label.pack(pady=10)

        self.state_label = ttk.Label(self.root, text="State: OFF", font=("Arial", 12))
        self.state_label.pack(pady=5)

        self.throttle_label = ttk.Label(self.root, text="Throttle:")
        self.throttle_label.pack(pady=5)

        self.throttle_value_label = ttk.Label(self.root, text="0%")
        self.throttle_value_label.pack()

        self.throttle_slider = ttk.Scale(self.root, from_=0, to=100, orient=tk.HORIZONTAL, length=300,
                                         command=self._on_throttle_change)
        self.throttle_slider.set(0)
        self.throttle_slider.pack(pady=5)
        self.throttle_slider.config(state=tk.DISABLED) 

        self.button_frame = ttk.Frame(self.root)
        self.button_frame.pack(pady=20)

        self.start_button = ttk.Button(self.button_frame, text="Start Engine", command=self._start_engine)
        self.start_button.pack(side=tk.LEFT, padx=10)
        self.start_button.config(state=tk.DISABLED)

        self.stop_button = ttk.Button(self.button_frame, text="Stop Engine", command=self._stop_engine, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=10)

        self.status_label = ttk.Label(self.root, text="Initializing...", font=("Arial", 10))
        self.status_label.pack(pady=10)

    def _simulation_init_and_loop(self):
        print("SIM_THREAD: _simulation_init_and_loop started.")
        try:
            self.root.after(0, lambda: self.status_label.config(text="Initializing Audio..."))
            print("SIM_THREAD: Initializing AudioManager...")
            self.audio_manager = AudioManager(
                mixer_frequency=config.MIXER_FREQUENCY,
                mixer_size=config.MIXER_SIZE,
                mixer_channels=config.MIXER_CHANNELS,
                mixer_buffer=config.MIXER_BUFFER_SIZE,
                num_audio_channels=config.NUM_AUDIO_CHANNELS,
                sound_files=config.SOUND_FILES,
                sfx_volume=config.SFX_VOLUME,
                main_engine_volume=config.MAIN_ENGINE_VOLUME,
                crossfade_duration_ms=config.CROSSFADE_DURATION_MS,
                accel_burst_cooldown_ms=config.ACCEL_BURST_COOLDOWN_MS,
                decel_pop_cooldown_ms=config.DECEL_POP_COOLDOWN_MS,
                enable_accel_burst=config.ENABLE_ACCEL_BURST,
                enable_decel_pops=config.ENABLE_DECEL_POPS
            )
            print("SIM_THREAD: AudioManager initialized.")

            if not pygame.mixer.get_init():
                print("SIM_THREAD: Pygame Mixer not initialized after AudioManager init. Disabling controls.")
                self.root.after(0, lambda: self.status_label.config(text="ERROR: Pygame Mixer failed. No audio."))
                while self.running:
                    time.sleep(0.1)
                print("SIM_THREAD: Exiting due to mixer init failure and app closing.")
                return

            self.root.after(0, lambda: self.status_label.config(text="Initializing Engine Simulator..."))
            print("SIM_THREAD: Initializing EngineSimulator...")
            self.engine_simulator = EngineSimulator(self.audio_manager)
            print("SIM_THREAD: EngineSimulator initialized.")
            
            self.root.after(0, lambda: self.start_button.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.throttle_slider.config(state=tk.NORMAL)) # Enable slider after init
            self.root.after(0, lambda: self.status_label.config(text="Ready."))

            print("SIM_THREAD: Entering main simulation loop...")
            target_fps = 120 
            target_sleep_time = 1.0 / target_fps
            
            while self.running:
                loop_start_time = time.perf_counter()

                if self.engine_simulator:
                    self.engine_simulator.update() 
                
                self.root.after(0, self._update_gui_data)

                loop_end_time = time.perf_counter()
                processing_time = loop_end_time - loop_start_time
                sleep_time = target_sleep_time - processing_time
                if sleep_time > 0:
                    time.sleep(sleep_time)
            print("SIM_THREAD: Exited main simulation loop because self.running is False.")

        except Exception as e:
            print(f"SIM_THREAD: ***** EXCEPTION IN SIMULATION THREAD *****")
            import traceback
            traceback.print_exc()
            try:
                self.root.after(0, lambda: self.status_label.config(text=f"ERROR IN SIM THREAD! See console."))
            except tk.TclError: 
                pass

        print("SIM_THREAD: Starting cleanup...")
        if self.audio_manager:
            if 'pygame' in globals() and pygame.mixer and pygame.mixer.get_init():
                print("SIM_THREAD: Stopping all sounds and quitting mixer via AudioManager.")
                self.audio_manager.stop_all_sounds() 
                self.audio_manager.quit()
            else:
                print("SIM_THREAD: Mixer not initialized or pygame module gone at cleanup, skipping audio_manager quit.")
        else:
            print("SIM_THREAD: No audio_manager to clean up.")
        
        print("SIM_THREAD: _simulation_init_and_loop finished.")

    def _on_throttle_change(self, value_str):
        if not self.engine_simulator or not self.running:
            return
        value = float(value_str) / 100.0
        # Call set_throttle regardless of engine state, let simulator handle it
        self.engine_simulator.set_throttle(value)

        if hasattr(self, 'throttle_value_label'):
            try:
                self.throttle_value_label.config(text=f"{int(float(value_str))}%")
            except tk.TclError:
                 pass

    def _start_engine(self):
        print("MAIN_APP: Start Engine button clicked.")
        if self.engine_simulator and self.engine_simulator.get_state() == EngineState.OFF:
            self.engine_simulator.start_engine()
        # Update GUI immediately after trying to start
        self._update_gui_data()


    def _stop_engine(self):
        print("MAIN_APP: Stop Engine button clicked.")
        if self.engine_simulator and self.engine_simulator.get_state() not in [EngineState.OFF, EngineState.SHUTTING_DOWN]:
            self.engine_simulator.stop_engine()
        # Update GUI immediately
        self._update_gui_data()


    def _update_gui_data(self):
        if not self.running or not hasattr(self, 'rpm_label'): 
            return

        try:
            if self.engine_simulator:
                rpm = self.engine_simulator.get_rpm()
                state = self.engine_simulator.get_state()
                self.rpm_label.config(text=f"RPM: {int(rpm)}")

                state_map = {
                    EngineState.OFF: ("OFF", "Engine Off. Ready."),
                    EngineState.STARTING: ("STARTING", "Engine Starting..."),
                    EngineState.IDLE: ("IDLE", "Engine Idling."),
                    EngineState.RUNNING: ("RUNNING", "Engine Running."),
                    EngineState.SHUTTING_DOWN: ("SHUTTING DOWN", "Engine Shutting Down...")
                }
                state_text, current_status_text = state_map.get(state, ("UNKNOWN", "Unknown state."))
                
                if state == EngineState.RUNNING and \
                   hasattr(self.engine_simulator, 'is_currently_cruising') and \
                   self.engine_simulator.is_currently_cruising: 
                    state_text = "CRUISING"
                    current_status_text = "Engine Cruising."

                self.state_label.config(text=f"State: {state_text}")
                
                if hasattr(self, 'status_label') and self.status_label.winfo_exists() and \
                   self.status_label['text'] != current_status_text and \
                   not (self.status_label['text'].startswith("ERROR")): 
                    self.status_label.config(text=current_status_text)

                is_off = (state == EngineState.OFF)
                is_busy_transition = (state == EngineState.STARTING or state == EngineState.SHUTTING_DOWN)
                
                if hasattr(self, 'start_button') and self.start_button.winfo_exists():
                    self.start_button.config(state=tk.NORMAL if is_off and pygame.mixer.get_init() else tk.DISABLED)
                if hasattr(self, 'stop_button') and self.stop_button.winfo_exists():
                    self.stop_button.config(state=tk.DISABLED if (is_off or is_busy_transition) else tk.NORMAL)
                if hasattr(self, 'throttle_slider') and self.throttle_slider.winfo_exists():
                     # Throttle slider should be enabled if engine is IDLE or RUNNING, and not busy.
                     # And pygame mixer must be initialized.
                     slider_state = tk.NORMAL if state in [EngineState.IDLE, EngineState.RUNNING] and not is_busy_transition and pygame.mixer.get_init() else tk.DISABLED
                     self.throttle_slider.config(state=slider_state)
            else: 
                if hasattr(self, 'start_button') and self.start_button.winfo_exists(): self.start_button.config(state=tk.DISABLED)
                if hasattr(self, 'stop_button') and self.stop_button.winfo_exists(): self.stop_button.config(state=tk.DISABLED)
                if hasattr(self, 'throttle_slider') and self.throttle_slider.winfo_exists(): self.throttle_slider.config(state=tk.DISABLED)
                if hasattr(self, 'status_label') and self.status_label.winfo_exists() and not self.status_label['text'].startswith("ERROR"):
                    self.status_label.config(text="Simulator not ready.")


        except tk.TclError:
            pass 
        except Exception as e:
            print(f"MAIN_APP: Error in _update_gui_data: {e}")
            import traceback
            traceback.print_exc()


    def _on_closing(self):
        print("MAIN_APP: _on_closing called. Setting self.running to False.")
        self.running = False
        if hasattr(self, 'simulation_thread') and self.simulation_thread.is_alive():
            print("MAIN_APP: Waiting for simulation thread to join...")
            self.simulation_thread.join(timeout=5) 
            if self.simulation_thread.is_alive():
                print("MAIN_APP: WARNING! Simulation thread did not join in time.")
            else:
                print("MAIN_APP: Simulation thread joined successfully.")
        
        if hasattr(self, 'root') and self.root.winfo_exists():
            self.root.destroy()
        print("MAIN_APP: Root window destroyed or was already gone.")


if __name__ == "__main__":
    print("MAIN_APP: Application started.")
    main_root = tk.Tk()
    app = App(main_root)
    main_root.mainloop()

    if pygame.get_init():
        print("MAIN_APP: Quitting Pygame (pygame.quit()).")
        pygame.quit()
    print("MAIN_APP: mainloop finished.")