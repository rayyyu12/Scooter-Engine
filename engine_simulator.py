import time
import random
import config

class EngineState:
    OFF = 0
    STARTING = 1
    IDLE = 2
    RUNNING = 3
    SHUTTING_DOWN = 4

class EngineSimulator:
    def __init__(self, audio_manager):
        self.audio_manager = audio_manager
        self.state = EngineState.OFF
        self.current_rpm = 0
        self.throttle_position = 0.0
        self.last_update_time = time.time()

        self.previous_rpm = 0
        self.rpm_change_rate = 0 
        self.previous_throttle_position = 0.0 # For comparing throttle changes for SFX
        
        self.update_call_count = 0
        self.start_time_for_state = time.time()

        self.previous_state_for_log = self.state
        self.previous_rpm_for_log = self.current_rpm
        self.log_interval_updates = 60 
        self.log_rpm_change_threshold = 70

        self.starter_sound_played_once = False


    def start_engine(self):
        if self.state == EngineState.OFF:
            self.state = EngineState.STARTING
            self.start_time_for_state = time.time()
            self.audio_manager.play_sfx("starter", on_channel=self.audio_manager.sfx_channel)
            # print("ENGINE_SIM: Engine starting process initiated...") # Logged by SFX play
            self.current_rpm = 0 
            self.last_update_time = time.time()
            self.update_call_count = 0
            self.starter_sound_played_once = True 

    def stop_engine(self):
        if self.state != EngineState.OFF and self.state != EngineState.SHUTTING_DOWN:
            # print(f"ENGINE_SIM: Stop engine called. Current state: {self.state}") # Logged by SFX play
            self.state = EngineState.SHUTTING_DOWN
            self.start_time_for_state = time.time()
            self.throttle_position = 0.0
            
            self.audio_manager.stop_engine_sounds_for_shutdown() 
            self.audio_manager.play_sfx("shutdown", on_channel=self.audio_manager.sfx_channel)
            # print("ENGINE_SIM: Engine shutting down process initiated...")

    def set_throttle(self, throttle_value):
        new_throttle_position = max(0.0, min(1.0, throttle_value))
        self.previous_throttle_position = self.throttle_position # Store before update

        # Accel Burst Logic: Trigger on a significant positive change in throttle
        if config.ENABLE_ACCEL_BURST and self.state in [EngineState.IDLE, EngineState.RUNNING]:
            throttle_diff = new_throttle_position - self.previous_throttle_position
            # Burst if increasing significantly from a non-max throttle
            if throttle_diff > config.ACCEL_BURST_THROTTLE_THRESHOLD : # Simpler: just a large enough increase
                print(f"ENGINE_SIM (SetThrottle): Accel Burst Check Triggered: new_thr={new_throttle_position:.2f}, prev_thr={self.previous_throttle_position:.2f}, diff={throttle_diff:.2f}")
                self.audio_manager.play_accel_burst()
        
        self.throttle_position = new_throttle_position


    def update(self):
        self.update_call_count += 1
        current_time = time.time()
        dt = current_time - self.last_update_time
        
        if dt <= 0.0001: dt = 0.001 
        self.last_update_time = current_time

        if self.audio_manager: self.audio_manager.update() 
        else: return # Cannot proceed without audio manager

        self.previous_rpm = self.current_rpm # Store before RPM update

        # --- State Machine & RPM Calculation ---
        if self.state == EngineState.STARTING:
            target_idle_rpm = config.IDLE_RPM
            time_in_starting_state = current_time - self.start_time_for_state

            if self.current_rpm < target_idle_rpm:
                rpm_to_gain = target_idle_rpm 
                duration = max(0.1, config.STARTER_SOUND_DURATION_TARGET_S - 0.3) # Aim to reach idle just before sound ends
                rate = rpm_to_gain / duration if duration > 0 else rpm_to_gain * 10 # Fast if no duration
                self.current_rpm += rate * dt
            self.current_rpm = min(self.current_rpm, target_idle_rpm)

            sfx_busy = self.audio_manager.is_sfx_channel_busy() if self.audio_manager else False
            starter_done = (not sfx_busy and self.starter_sound_played_once and time_in_starting_state > 0.5)
            
            if (starter_done and self.current_rpm >= target_idle_rpm) or \
               time_in_starting_state > config.STARTER_TIMEOUT_S:
                reason = "Starter sound & RPM" if starter_done else f"Timeout ({config.STARTER_TIMEOUT_S:.1f}s)"
                self.current_rpm = target_idle_rpm 
                self.state = EngineState.IDLE
                self.starter_sound_played_once = False 
                print(f"ENGINE_SIM: State -> IDLE. RPM: {self.current_rpm:.0f}. Reason: {reason}.")

        elif self.state == EngineState.IDLE or self.state == EngineState.RUNNING:
            target_rpm = config.IDLE_RPM
            if self.throttle_position > 0.005: 
                if self.state == EngineState.IDLE: self.state = EngineState.RUNNING
                throttle_effect = pow(self.throttle_position, 0.7) # More responsive curve
                target_rpm = config.IDLE_RPM + (config.MAX_RPM - config.IDLE_RPM) * throttle_effect
            
            rpm_diff = target_rpm - self.current_rpm
            rate_factor = config.RPM_ACCEL_RATE if rpm_diff > 0 else config.RPM_DECEL_RATE
            if self.throttle_position < 0.01 and rpm_diff < 0 : rate_factor = config.RPM_IDLE_RETURN_RATE

            # Inertia: approach target RPM smoothly
            # Change is proportional to diff, scaled by rate and inertia
            # RPM change = (target_rpm - current_rpm) * (1 - inertia_factor_scaled_by_dt) - not quite right
            # More like: current_rpm += (target_rpm - current_rpm) * some_factor * dt
            # Or: current_rpm += sign(rpm_diff) * rate_factor * dt (simpler, then apply inertia or smoothing)
            
            # Let's use a direct approach towards target_rpm with inertia affecting how quickly it gets there
            # The "inertia" can be thought of as a resistance to change.
            # A simple low-pass filter like approach:
            # self.current_rpm += (target_rpm - self.current_rpm) * config.RPM_INERTIA_FACTOR * dt # RPM_INERTIA_FACTOR would be response speed here
            # For now, stick to the rate-based approach and ensure clamping

            change = rate_factor * dt
            if rpm_diff > 0: # Accelerate
                self.current_rpm += change
                if self.current_rpm > target_rpm: self.current_rpm = target_rpm 
            elif rpm_diff < 0: # Decelerate
                self.current_rpm -= change
                if self.current_rpm < target_rpm: self.current_rpm = target_rpm

            if self.throttle_position < 0.01 and self.current_rpm <= config.IDLE_RPM and self.state == EngineState.RUNNING:
                self.state = EngineState.IDLE
                self.current_rpm = config.IDLE_RPM 
            
            min_for_state = config.IDLE_RPM if self.state == EngineState.IDLE else config.MIN_RPM
            self.current_rpm = max(min_for_state, min(self.current_rpm, config.MAX_RPM))

        elif self.state == EngineState.SHUTTING_DOWN:
            self.current_rpm -= config.RPM_DECEL_RATE * 2.0 * dt # Faster shutdown
            
            time_in_state = current_time - self.start_time_for_state
            sfx_busy = self.audio_manager.is_sfx_channel_busy() if self.audio_manager else False
            shutdown_done = not sfx_busy and time_in_state > 0.5
            max_time = config.SOUND_DURATIONS.get("shutdown", 5.0) + 2.0

            if self.current_rpm <= 5 or (shutdown_done and self.current_rpm < config.MIN_RPM / 4) or time_in_state > max_time:
                self.current_rpm = 0
                self.state = EngineState.OFF
                print(f"ENGINE_SIM: State -> OFF. Shutdown complete (RPM={self.current_rpm:.0f}, time={time_in_state:.2f}s).")

        # --- Calculate RPM Change Rate ---
        self.rpm_change_rate = (self.current_rpm - self.previous_rpm) / dt if dt > 0.00001 else 0 

        # --- Logging (after RPM calculation) ---
        if self.update_call_count % self.log_interval_updates == 0 or \
           self.state != self.previous_state_for_log or \
           abs(self.current_rpm - self.previous_rpm_for_log) > self.log_rpm_change_threshold or \
           (self.update_call_count < 15 and self.update_call_count % 5 == 0) : 
            # print(f"ENGINE_SIM (Upd {self.update_call_count}): St: {self.state}, RPM: {self.current_rpm:.0f} (Prev:{self.previous_rpm:.0f}), Thr: {self.throttle_position:.2f} (Prev:{self.previous_throttle_position:.2f}), dt: {dt:.4f}, RPMChgRt: {self.rpm_change_rate:.0f}")
            self.previous_state_for_log = self.state
            self.previous_rpm_for_log = self.current_rpm
            # self.previous_throttle_for_log = self.throttle_position # If needed

        # --- Update Audio System ---
        if self.audio_manager: self._update_engine_sound() 

        # --- Decel Pops Logic ---
        if config.ENABLE_DECEL_POPS and self.state in [EngineState.RUNNING, EngineState.IDLE]:
            # Condition: Rapid decel (high -ve rpm_change_rate), throttle just closed or very low, RPM above threshold.
            throttle_closed_recently = self.throttle_position < 0.05 and self.previous_throttle_position > 0.1
            is_decelerating_sharply = self.rpm_change_rate < config.LOAD_THRESHOLD_DECEL
            
            if is_decelerating_sharply and throttle_closed_recently and self.current_rpm > config.DECEL_POP_RPM_THRESHOLD:
                print(f"ENGINE_SIM (DecelPop Check Triggered): RPMChg={self.rpm_change_rate:.0f}, ThrNow={self.throttle_position:.2f}, ThrPrev={self.previous_throttle_position:.2f}, RPM={self.current_rpm:.0f}")
                if random.random() < config.DECEL_POP_CHANCE:
                    if self.audio_manager: self.audio_manager.play_decel_pop()
        
        if self.state == EngineState.OFF and self.audio_manager and self.audio_manager.is_any_engine_sound_playing():
            self.audio_manager.stop_all_engine_sounds()


    def _update_engine_sound(self):
        if not self.audio_manager: return
        target_sound_key = None
        
        if self.state == EngineState.STARTING or self.state == EngineState.SHUTTING_DOWN:
            pass # SFX handled elsewhere
        elif self.state == EngineState.IDLE:
            target_sound_key = "idle"
        elif self.state == EngineState.RUNNING:
            # RPM ranges define the sound. Ensure RPM_RANGES in config.py have overlaps.
            # This logic tries to find the most appropriate band.
            if self.current_rpm < config.RPM_RANGES["low_rpm"][0] + 50 : # Give slight preference to idle if very close to low_rpm start
                 target_sound_key = "idle"
            elif self.current_rpm < config.RPM_RANGES["low_rpm"][1] - 100: # Well within low_rpm
                 target_sound_key = "low_rpm"
            elif self.current_rpm < config.RPM_RANGES["mid_rpm"][1] - 150: # Well within mid_rpm
                 target_sound_key = "mid_rpm"
            else: # Default to high_rpm if above mid_rpm's upper part
                 target_sound_key = "high_rpm"

            # Hysteresis: If current sound is still valid for current RPM, prefer it to avoid flapping
            # Example: if playing 'low_rpm' and RPM is in overlap between 'low' and 'mid', stick to 'low'
            # unless RPM moves decisively into 'mid'.
            current_am_loop = self.audio_manager.current_loop_sound_key
            is_fading_to = self.audio_manager.crossfade_to_sound_key if self.audio_manager.is_crossfading else None
            effective_current_sound = is_fading_to if is_fading_to else current_am_loop

            if effective_current_sound:
                if effective_current_sound == "idle" and self.current_rpm < config.RPM_RANGES["low_rpm"][1] * 0.95: # Stay idle longer
                    target_sound_key = "idle"
                elif effective_current_sound == "low_rpm" and \
                     config.RPM_RANGES["low_rpm"][0] * 0.9 < self.current_rpm < config.RPM_RANGES["mid_rpm"][0] * 1.05:
                    target_sound_key = "low_rpm"
                elif effective_current_sound == "mid_rpm" and \
                     config.RPM_RANGES["mid_rpm"][0] * 0.95 < self.current_rpm < config.RPM_RANGES["high_rpm"][0] * 1.05:
                    target_sound_key = "mid_rpm"
                # No specific hysteresis for high_rpm, if RPM high enough, it should be high_rpm.
            
        elif self.state == EngineState.OFF:
            if self.audio_manager.is_any_engine_sound_playing():
                 self.audio_manager.stop_all_engine_sounds()
            return 

        if target_sound_key:
            is_new_decision = (target_sound_key != self.audio_manager.current_loop_sound_key and \
                               not (self.audio_manager.is_crossfading and self.audio_manager.crossfade_to_sound_key == target_sound_key))
            
            # If engine is supposed to be making sound but isn't (and not because it's starting/stopping)
            should_be_playing = self.state in [EngineState.IDLE, EngineState.RUNNING]
            is_silent = not self.audio_manager.is_any_engine_sound_playing() and not self.audio_manager.is_crossfading

            if is_new_decision or (should_be_playing and is_silent):
                print(f"ENGINE_SIM: Sound Decision - St: {self.state}, RPM: {self.current_rpm:.0f} => Target: '{target_sound_key}' (AM.Cur: '{self.audio_manager.current_loop_sound_key}', AM.XFto: '{self.audio_manager.crossfade_to_sound_key if self.audio_manager.is_crossfading else 'N/A'}')")
            
            self.audio_manager.update_engine_sound(target_sound_key)

        elif self.state not in [EngineState.STARTING, EngineState.SHUTTING_DOWN, EngineState.OFF]:
            if self.audio_manager.is_any_engine_sound_playing():
                print(f"ENGINE_SIM: WARNING - No target sound for St {self.state}, RPM {self.current_rpm:.0f} but sounds playing. Stopping.")
                self.audio_manager.stop_all_engine_sounds()

    def get_rpm(self): return self.current_rpm
    def get_state(self): return self.state