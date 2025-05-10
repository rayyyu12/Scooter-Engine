# engine_simulator.py
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
        self.previous_throttle_position = 0.0 # Value of throttle at the end of the last set_throttle call
        
        self.update_call_count = 0
        self.start_time_for_state = time.time()

        self.log_interval_updates = 60 
        self.log_rpm_change_threshold = 70
        self.previous_state_for_log = self.state # For logging
        self.previous_rpm_for_log = self.current_rpm # For logging

        self.starter_sound_played_once = False
        
        self.accel_burst_effect_active_until = 0 # Timer for engine sound suppression during accel burst
        self.decel_pop_linger_active_until = 0   # Timer for modified RPM fall and sound loop during decel pop

    def start_engine(self):
        if self.state == EngineState.OFF:
            self.state = EngineState.STARTING
            self.start_time_for_state = time.time()
            self.audio_manager.play_sfx("starter", on_channel=self.audio_manager.sfx_channel)
            self.current_rpm = 0 
            self.last_update_time = time.time()
            self.starter_sound_played_once = True 

    def stop_engine(self):
        if self.state != EngineState.OFF and self.state != EngineState.SHUTTING_DOWN:
            self.state = EngineState.SHUTTING_DOWN
            self.start_time_for_state = time.time()
            self.throttle_position = 0.0
            self.audio_manager.stop_engine_sounds_for_shutdown() 
            self.audio_manager.play_sfx("shutdown", on_channel=self.audio_manager.sfx_channel)

    def set_throttle(self, throttle_value):
        new_throttle_position = max(0.0, min(1.0, throttle_value))
        
        # Accel Burst Logic (uses self.throttle_position which is from *before* this call)
        if config.ENABLE_ACCEL_BURST and self.state in [EngineState.IDLE, EngineState.RUNNING]:
            # Check for a rapid, significant increase from a low throttle state
            is_significant_increase = new_throttle_position > (self.throttle_position + config.ACCEL_BURST_THROTTLE_THRESHOLD)
            is_to_high_throttle = new_throttle_position >= config.ACCEL_BURST_MIN_NEW_THROTTLE
            was_at_low_throttle = self.throttle_position <= config.ACCEL_BURST_MAX_OLD_THROTTLE

            if is_significant_increase and is_to_high_throttle and was_at_low_throttle:
                print(f"ENGINE_SIM (SetThrottle): Accel Burst Condition MET! NewThr: {new_throttle_position:.2f}, PrevThr (val before this call): {self.throttle_position:.2f}")
                if self.audio_manager.play_accel_burst(): # AudioManager's play_accel_burst now takes a volume multiplier
                    # Set timer to suppress aggressive high_rpm sound loop
                    self.accel_burst_effect_active_until = time.time() + (config.SOUND_DURATIONS["accel_burst"] * config.ACCEL_BURST_EFFECT_DURATION_MULTIPLIER)
                    print(f"ENGINE_SIM: Accel burst SFX PLAYED by AM. Effect active until {self.accel_burst_effect_active_until:.2f}")
        
        self.previous_throttle_position = self.throttle_position # Store current value before updating
        self.throttle_position = new_throttle_position           # Update to new value

    def update(self):
        current_time = time.time()
        dt = current_time - self.last_update_time
        if dt <= 0.0001: dt = 0.001 
        self.last_update_time = current_time

        if self.audio_manager: self.audio_manager.update() 
        else: return

        self.previous_rpm = self.current_rpm

        # --- State Machine & RPM Calculation ---
        if self.state == EngineState.STARTING:
            # ... (no changes to STARTING state logic) ...
            target_idle_rpm = config.IDLE_RPM
            time_in_starting_state = current_time - self.start_time_for_state
            if self.current_rpm < target_idle_rpm:
                rpm_to_gain = target_idle_rpm 
                duration = max(0.1, config.STARTER_SOUND_DURATION_TARGET_S - 0.3)
                rate = rpm_to_gain / duration if duration > 0 else rpm_to_gain * 10
                self.current_rpm += rate * dt
            self.current_rpm = min(self.current_rpm, target_idle_rpm)
            sfx_busy = self.audio_manager.is_sfx_channel_busy()
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
                throttle_effect = pow(self.throttle_position, 0.7)
                target_rpm = config.IDLE_RPM + (config.MAX_RPM - config.IDLE_RPM) * throttle_effect
            
            rpm_diff = target_rpm - self.current_rpm
            
            current_decel_rate = config.RPM_DECEL_RATE
            current_idle_return_rate = config.RPM_IDLE_RETURN_RATE

            # Decel pop RPM fall rate modification
            if current_time < self.decel_pop_linger_active_until and self.throttle_position < 0.05 and rpm_diff < 0:
                print(f"ENGINE_SIM: Decel pop linger active. Modifying decel rate from {current_decel_rate} to {current_decel_rate * config.DECEL_POP_RPM_FALL_RATE_MODIFIER:.0f}")
                current_decel_rate *= config.DECEL_POP_RPM_FALL_RATE_MODIFIER
                # Also modify the specific idle return rate if it's the one being used
                if self.throttle_position < 0.01: # Condition for using idle_return_rate
                     print(f"ENGINE_SIM: Decel pop linger active. Modifying idle return rate from {current_idle_return_rate} to {current_idle_return_rate * config.DECEL_POP_RPM_FALL_RATE_MODIFIER:.0f}")
                     current_idle_return_rate *= config.DECEL_POP_RPM_FALL_RATE_MODIFIER


            rate_factor = config.RPM_ACCEL_RATE if rpm_diff > 0 else current_decel_rate
            if self.throttle_position < 0.01 and rpm_diff < 0 :
                rate_factor = current_idle_return_rate # Use potentially modified idle return rate
            
            change = rate_factor * dt
            if rpm_diff > 0: # Accelerate
                self.current_rpm += change
                if self.current_rpm > target_rpm: self.current_rpm = target_rpm 
            elif rpm_diff < 0: # Decelerate
                self.current_rpm -= change
                if self.current_rpm < target_rpm: self.current_rpm = target_rpm

            # State transition to IDLE
            if self.throttle_position < 0.01 and self.current_rpm <= config.IDLE_RPM and self.state == EngineState.RUNNING:
                if current_time >= self.decel_pop_linger_active_until: # Only switch to IDLE if decel pop effect is over
                    print(f"ENGINE_SIM: Decel pop linger OVER. Transitioning to IDLE state.")
                    self.state = EngineState.IDLE
                    self.current_rpm = config.IDLE_RPM # Ensure it snaps to idle RPM
                # else: print(f"ENGINE_SIM: Holding off IDLE state due to decel pop linger.")
            
            min_for_state = config.IDLE_RPM if self.state == EngineState.IDLE else config.MIN_RPM
            self.current_rpm = max(min_for_state, min(self.current_rpm, config.MAX_RPM))

        elif self.state == EngineState.SHUTTING_DOWN:
            # ... (no changes to SHUTTING_DOWN state logic) ...
            self.current_rpm -= config.RPM_DECEL_RATE * 2.0 * dt 
            time_in_state = current_time - self.start_time_for_state
            sfx_busy = self.audio_manager.is_sfx_channel_busy()
            shutdown_done = not sfx_busy and time_in_state > 0.5 # Assuming SFX was played for shutdown
            max_time = config.SOUND_DURATIONS.get("shutdown", 5.0) + 2.0
            if self.current_rpm <= 5 or (shutdown_done and self.current_rpm < config.MIN_RPM / 4) or time_in_state > max_time:
                self.current_rpm = 0
                self.state = EngineState.OFF
                print(f"ENGINE_SIM: State -> OFF. Shutdown complete (RPM={self.current_rpm:.0f}, time={time_in_state:.2f}s).")


        self.rpm_change_rate = (self.current_rpm - self.previous_rpm) / dt if dt > 0.00001 else 0 

        # --- Decel Pops Logic ---
        if config.ENABLE_DECEL_POPS and self.state in [EngineState.RUNNING, EngineState.IDLE]: # Allow pops even from idle if RPMs were high
            # Use self.throttle_position (current) and self.previous_throttle_position (from end of last set_throttle)
            throttle_just_closed_sharply = self.throttle_position < 0.05 and self.previous_throttle_position > 0.20 # Previous was notably open
            is_decelerating_sharply = self.rpm_change_rate < config.LOAD_THRESHOLD_DECEL
            
            if is_decelerating_sharply and throttle_just_closed_sharply and self.current_rpm > config.DECEL_POP_RPM_THRESHOLD:
                if random.random() < config.DECEL_POP_CHANCE:
                    if self.audio_manager.play_decel_pop():
                        self.decel_pop_linger_active_until = current_time + config.DECEL_POP_LINGER_DURATION_S
                        print(f"ENGINE_SIM: Decel pop SFX PLAYED by AM. Linger effect active until {self.decel_pop_linger_active_until:.2f}")
        
        # Reset decel pop linger if throttle is applied again OR if it naturally expires
        if self.throttle_position > 0.1:
            if current_time > self.decel_pop_linger_active_until + 0.1 : # Add small buffer to ensure it's truly over
                 self.decel_pop_linger_active_until = 0 
        
        # Logging (reduced frequency)
        if self.update_call_count % (self.log_interval_updates * 2) == 0 or \
           self.state != self.previous_state_for_log or \
           (abs(self.current_rpm - self.previous_rpm_for_log) > self.log_rpm_change_threshold and self.update_call_count % 10 == 0) : 
            # print(f"ESIM: St:{self.state} RPM:{self.current_rpm:.0f} Thr:{self.throttle_position:.2f} RPMChg:{self.rpm_change_rate:.0f} AccelUntil:{self.accel_burst_effect_active_until - current_time if self.accel_burst_effect_active_until > current_time else 0:.1f} PopUntil:{self.decel_pop_linger_active_until - current_time if self.decel_pop_linger_active_until > current_time else 0:.1f}")
            self.previous_state_for_log = self.state
            self.previous_rpm_for_log = self.current_rpm
        
        self.update_call_count +=1
        if self.audio_manager: self._update_engine_sound(current_time) 

        if self.state == EngineState.OFF and self.audio_manager and self.audio_manager.is_any_engine_sound_playing():
            self.audio_manager.stop_all_engine_sounds()

    def _update_engine_sound(self, current_sim_time):
        if not self.audio_manager: return
        target_sound_key = None
        
        if self.state == EngineState.STARTING or self.state == EngineState.SHUTTING_DOWN:
            pass 
        elif self.state == EngineState.IDLE:
            target_sound_key = "idle"
        elif self.state == EngineState.RUNNING:
            # Basic RPM to sound key mapping
            if self.current_rpm < config.RPM_RANGES["low_rpm"][0] + 50 :
                 target_sound_key = "idle"
            elif self.current_rpm < config.RPM_RANGES["low_rpm"][1] - 100:
                 target_sound_key = "low_rpm"
            elif self.current_rpm < config.RPM_RANGES["mid_rpm"][1] - 150:
                 target_sound_key = "mid_rpm"
            else: 
                 target_sound_key = "high_rpm"

            # Hysteresis (prefer current sound if still valid)
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
            
            # Accel Burst effect: Delay transition to high_rpm
            if current_sim_time < self.accel_burst_effect_active_until:
                if target_sound_key == "high_rpm" and \
                   effective_current_sound != "high_rpm": # Simpler: if we are about to go to high_rpm
                    original_target = target_sound_key
                    target_sound_key = "mid_rpm" # Force mid_rpm to give burst SFX prominence
                    # print(f"ENGINE_SIM (AccelBurstEffect): Burst effect active. RPMs want '{original_target}', current/fading is '{effective_current_sound}'. Forcing target to '{target_sound_key}' temporarily.")
            
            # Decel Pop Linger effect: Prevent premature switch to idle sound loop
            if current_sim_time < self.decel_pop_linger_active_until and self.throttle_position < 0.05:
                if target_sound_key == "idle":
                    # If we were on low_rpm or fading to it, prefer to stay there
                    if effective_current_sound == "low_rpm":
                        target_sound_key = "low_rpm"
                        print(f"ENGINE_SIM (DecelPopEffect): Pop lingering. Overriding target from 'idle' to 'low_rpm' (was on low_rpm).")
                    elif self.current_rpm > config.RPM_RANGES["idle"][0] : # If RPM still a bit above pure idle bottom
                        target_sound_key = "low_rpm" # Default to low_rpm during pop if would have gone to idle
                        print(f"ENGINE_SIM (DecelPopEffect): Pop lingering. Forcing target 'low_rpm' instead of 'idle'. RPM: {self.current_rpm:.0f}")


        elif self.state == EngineState.OFF:
            if self.audio_manager.is_any_engine_sound_playing():
                 self.audio_manager.stop_all_engine_sounds()
            return 

        if target_sound_key:
            is_new_decision = (target_sound_key != self.audio_manager.current_loop_sound_key and \
                               not (self.audio_manager.is_crossfading and self.audio_manager.crossfade_to_sound_key == target_sound_key))
            should_be_playing = self.state in [EngineState.IDLE, EngineState.RUNNING]
            is_silent = not self.audio_manager.is_any_engine_sound_playing() and not self.audio_manager.is_crossfading

            if is_new_decision or (should_be_playing and is_silent):
                print(f"ENGINE_SIM: Sound Decision - St: {self.state}, RPM: {self.current_rpm:.0f} => Target: '{target_sound_key}' (AM.Cur: '{self.audio_manager.current_loop_sound_key}', AM.XFto: '{self.audio_manager.crossfade_to_sound_key if self.audio_manager.is_crossfading else 'N/A'}')")
            self.audio_manager.update_engine_sound(target_sound_key)

    def get_rpm(self): return self.current_rpm
    def get_state(self): return self.state