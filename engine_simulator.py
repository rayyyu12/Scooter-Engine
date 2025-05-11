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
        # self.previous_throttle_position = 0.0 # Replaced by more robust gesture detection

        self.last_update_time = time.time()
        self.previous_rpm = 0
        self.rpm_change_rate = 0 
        
        self.update_call_count = 0
        self.start_time_for_state = time.time()

        self.log_interval_updates = 60 
        self.log_rpm_change_threshold = 70

        self.starter_sound_played_once = False
        
        # Accel Burst related
        self.throttle_history_for_accel = [] # List of (timestamp, throttle_value)
        self.accel_burst_effect_active_until = 0

        # Decel Pop related
        self.last_known_high_throttle_value = 0.0
        self.last_known_high_throttle_time = 0.0
        self.decel_pop_gesture_detected_at = 0.0 # Timestamp when gesture was detected by set_throttle
        self.decel_pop_linger_active_until = 0
        self.decel_pop_background_override_key = None
        
        self.time_at_cruise_throttle_start = 0
        self.is_eligible_for_cruise_sound = False
        self.is_currently_cruising = False

    def start_engine(self):
        if self.state == EngineState.OFF:
            self.state = EngineState.STARTING
            self.start_time_for_state = time.time()
            self.audio_manager.play_sfx("starter", on_channel=self.audio_manager.sfx_channel)
            self.current_rpm = 0 
            self.throttle_position = 0.0
            self.last_update_time = time.time()
            self.starter_sound_played_once = True 
            self._reset_cruise_state()
            # Reset gesture detection states
            self.throttle_history_for_accel = []
            self.last_known_high_throttle_value = 0.0
            self.last_known_high_throttle_time = 0.0
            self.decel_pop_gesture_detected_at = 0.0
            self.accel_burst_effect_active_until = 0
            self.decel_pop_linger_active_until = 0


    def stop_engine(self):
        if self.state != EngineState.OFF and self.state != EngineState.SHUTTING_DOWN:
            self.state = EngineState.SHUTTING_DOWN
            self.start_time_for_state = time.time()
            self.throttle_position = 0.0
            self.audio_manager.stop_engine_sounds_for_shutdown() 
            self.audio_manager.play_sfx("shutdown", on_channel=self.audio_manager.sfx_channel)
            self._reset_cruise_state()
            # Reset gesture detection states
            self.throttle_history_for_accel = []
            self.last_known_high_throttle_value = 0.0
            self.last_known_high_throttle_time = 0.0
            self.decel_pop_gesture_detected_at = 0.0
            self.accel_burst_effect_active_until = 0
            self.decel_pop_linger_active_until = 0

    def _reset_cruise_state(self):
        self.time_at_cruise_throttle_start = 0
        self.is_eligible_for_cruise_sound = False
        self.is_currently_cruising = False

    def set_throttle(self, throttle_value):
        current_time = time.time()
        new_throttle_clamped = max(0.0, min(1.0, throttle_value))
        
        # --- Cruise State Management based on Throttle Input ---
        if self.is_currently_cruising and new_throttle_clamped < config.CRUISE_THROTTLE_MAINTAIN_THRESHOLD:
            self._reset_cruise_state()
        elif not self.is_currently_cruising and \
             new_throttle_clamped >= config.CRUISE_THROTTLE_ENTER_THRESHOLD and \
             self.throttle_position < config.CRUISE_THROTTLE_ENTER_THRESHOLD: 
            if self.state == EngineState.RUNNING : 
                self.time_at_cruise_throttle_start = time.time()
                self.is_eligible_for_cruise_sound = False 
        elif not self.is_currently_cruising and new_throttle_clamped < config.CRUISE_THROTTLE_ENTER_THRESHOLD:
            if self.time_at_cruise_throttle_start != 0 : 
                 self.time_at_cruise_throttle_start = 0 
                 self.is_eligible_for_cruise_sound = False

        # --- Accel Burst Gesture Detection ---
        if config.ENABLE_ACCEL_BURST and self.state in [EngineState.IDLE, EngineState.RUNNING]:
            self.throttle_history_for_accel.append((current_time, new_throttle_clamped))
            self.throttle_history_for_accel = [
                (t, thr) for t, thr in self.throttle_history_for_accel 
                if current_time - t <= config.ACCEL_BURST_HISTORY_DURATION_S
            ]

            if new_throttle_clamped >= config.ACCEL_BURST_MIN_END_THROTTLE:
                # Check if an accel burst effect is NOT already active
                if not (current_time < self.accel_burst_effect_active_until):
                    for t_old, thr_old in self.throttle_history_for_accel:
                        if current_time - t_old <= config.ACCEL_BURST_FLICK_WINDOW_S:
                            if thr_old <= config.ACCEL_BURST_MAX_START_THROTTLE:
                                throttle_jump = new_throttle_clamped - thr_old
                                if throttle_jump >= config.ACCEL_BURST_MIN_JUMP_VALUE:
                                    if self.audio_manager.play_accel_burst():
                                        self.accel_burst_effect_active_until = current_time + \
                                            (config.SOUND_DURATIONS["accel_burst"] * config.ACCEL_BURST_EFFECT_DURATION_MULTIPLIER)
                                        self.throttle_history_for_accel = [] # Clear history after successful burst
                                        if self.is_currently_cruising: 
                                            # print("ENGINE_SIM: Accel burst occurred, exiting cruise mode.")
                                            self._reset_cruise_state()
                                        # print(f"ESIM: ---> ACCEL BURST SFX PLAYED by flick from {thr_old:.2f} to {new_throttle_clamped:.2f}")
                                        break # Burst triggered and SFX played

        # --- Decel Pop Gesture Detection ---
        if config.ENABLE_DECEL_POPS and self.state in [EngineState.IDLE, EngineState.RUNNING]:
            # Update last known high throttle state
            if new_throttle_clamped >= config.DECEL_POP_HIGH_THROTTLE_THRESHOLD:
                self.last_known_high_throttle_value = max(self.last_known_high_throttle_value, new_throttle_clamped)
                self.last_known_high_throttle_time = current_time
            
            # Check for drop if we were high and now low, and no gesture is pending RPM check
            if self.decel_pop_gesture_detected_at == 0.0 and \
               self.last_known_high_throttle_value >= config.DECEL_POP_HIGH_THROTTLE_THRESHOLD and \
               new_throttle_clamped <= config.DECEL_POP_LOW_THROTTLE_THRESHOLD and \
               self.throttle_position > config.DECEL_POP_LOW_THROTTLE_THRESHOLD: # Ensure we just crossed the low threshold

                time_since_high = current_time - self.last_known_high_throttle_time
                throttle_drop = self.last_known_high_throttle_value - new_throttle_clamped

                if time_since_high <= config.DECEL_POP_MAX_FLICK_DURATION_S and \
                   throttle_drop >= config.DECEL_POP_MIN_DROP_VALUE:
                    self.decel_pop_gesture_detected_at = current_time
                    # print(f"ESIM: DECEL POP GESTURE detected (from {self.last_known_high_throttle_value:.2f} to {new_throttle_clamped:.2f}). Waiting for RPM.")
                    self.last_known_high_throttle_value = 0.0 # Reset to require going high again for next pop
            
            # If throttle goes up again significantly, cancel pending decel pop gesture
            if self.decel_pop_gesture_detected_at != 0.0 and new_throttle_clamped > (config.DECEL_POP_LOW_THROTTLE_THRESHOLD + 0.05): # Hysteresis
                # print(f"ESIM: Decel pop gesture cancelled due to throttle increase to {new_throttle_clamped:.2f}")
                self.decel_pop_gesture_detected_at = 0.0
        
        self.throttle_position = new_throttle_clamped


    def update(self):
        current_time = time.time()
        dt = current_time - self.last_update_time
        if dt <= 0.0001: dt = 0.001 
        self.last_update_time = current_time

        if self.audio_manager: self.audio_manager.update() 
        else: return

        self.previous_rpm = self.current_rpm

        # --- State Machine ---
        if self.state == EngineState.STARTING:
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
                self.current_rpm = config.IDLE_RPM 
                self.state = EngineState.IDLE
                self.starter_sound_played_once = False 
                self._reset_cruise_state()

        elif self.state == EngineState.IDLE or self.state == EngineState.RUNNING:
            target_rpm = config.IDLE_RPM
            if self.throttle_position > config.THROTTLE_EFFECTIVELY_ZERO:
                if self.state == EngineState.IDLE: self.state = EngineState.RUNNING
                
                if self.is_currently_cruising and self.throttle_position >= config.CRUISE_THROTTLE_MAINTAIN_THRESHOLD:
                    target_rpm = config.MAX_RPM
                elif self.throttle_position >= config.CRUISE_THROTTLE_ENTER_THRESHOLD: 
                     target_rpm = config.MAX_RPM 
                else: 
                     throttle_effect = pow(self.throttle_position, 0.7)
                     target_rpm = config.IDLE_RPM + (config.MAX_RPM - config.IDLE_RPM) * throttle_effect
            
            rpm_diff = target_rpm - self.current_rpm
            current_decel_rate = config.RPM_DECEL_RATE
            current_idle_return_rate = config.RPM_IDLE_RETURN_RATE

            if current_time < self.decel_pop_linger_active_until and self.throttle_position < config.THROTTLE_EFFECTIVELY_ZERO and rpm_diff < 0:
                current_decel_rate *= config.DECEL_POP_RPM_FALL_RATE_MODIFIER
                if self.throttle_position < 0.01: 
                     current_idle_return_rate *= config.DECEL_POP_RPM_FALL_RATE_MODIFIER

            rate_factor = config.RPM_ACCEL_RATE if rpm_diff > 0 else current_decel_rate
            if self.throttle_position < config.THROTTLE_EFFECTIVELY_ZERO and rpm_diff < 0 :
                rate_factor = current_idle_return_rate
                if self.is_currently_cruising: 
                    self._reset_cruise_state()
            
            change = rate_factor * dt
            if rpm_diff > 0:
                self.current_rpm += change
                if self.current_rpm > target_rpm: self.current_rpm = target_rpm 
            elif rpm_diff < 0:
                self.current_rpm -= change
                if self.current_rpm < target_rpm: self.current_rpm = target_rpm

            if self.throttle_position < config.THROTTLE_EFFECTIVELY_ZERO and \
               self.current_rpm <= config.IDLE_RPM + 50 and self.state == EngineState.RUNNING: 
                if current_time >= self.decel_pop_linger_active_until and current_time >= self.accel_burst_effect_active_until: # Ensure SFX effects are done
                    self.state = EngineState.IDLE
                    self.current_rpm = config.IDLE_RPM 
                    self.decel_pop_background_override_key = None 
                    if self.is_currently_cruising: self._reset_cruise_state()
            
            min_for_state = config.IDLE_RPM if self.state == EngineState.IDLE else config.MIN_RPM
            self.current_rpm = max(min_for_state, min(self.current_rpm, config.MAX_RPM))

        elif self.state == EngineState.SHUTTING_DOWN:
            time_in_state = current_time - self.start_time_for_state
            sfx_busy = self.audio_manager.is_sfx_channel_busy()
            shutdown_done = not sfx_busy and time_in_state > 0.5
            shutdown_sound_duration = config.SOUND_DURATIONS.get("shutdown", 5.0) 
            max_time = shutdown_sound_duration + 2.0
            self.current_rpm -= config.RPM_DECEL_RATE * 2.0 * dt 
            if self.current_rpm <= 5 or \
               (shutdown_done and self.current_rpm < config.MIN_RPM / 4) or \
               time_in_state > max_time:
                self.current_rpm = 0
                self.state = EngineState.OFF
                self._reset_cruise_state()

        self.rpm_change_rate = (self.current_rpm - self.previous_rpm) / dt if dt > 0.00001 else 0 

        # --- SFX Logic (Decel Pop - RPM Check and Play) ---
        if self.decel_pop_gesture_detected_at != 0.0 and \
           config.ENABLE_DECEL_POPS and self.state in [EngineState.RUNNING, EngineState.IDLE]:
            
            if current_time - self.decel_pop_gesture_detected_at <= config.DECEL_POP_RPM_CHECK_WINDOW_S:
                if self.current_rpm > config.DECEL_POP_RPM_THRESHOLD:
                    if random.random() < config.DECEL_POP_CHANCE: # Keep random chance if desired
                        if self.audio_manager.play_decel_pop():
                            self.decel_pop_linger_active_until = current_time + config.DECEL_POP_LINGER_DURATION_S
                            current_loop = self.audio_manager.current_loop_sound_key
                            fading_to = self.audio_manager.crossfade_to_sound_key if self.audio_manager.is_crossfading else None
                            self.decel_pop_background_override_key = fading_to if fading_to else current_loop
                            if self.decel_pop_background_override_key in ["high_rpm", "mid_rpm", "cruise"] : 
                                self.decel_pop_background_override_key = "low_rpm"
                            elif self.decel_pop_background_override_key == "idle" : 
                                self.decel_pop_background_override_key = "low_rpm" # Or keep idle if preferred
                            # print(f"ENGINE_SIM: ---> DECEL POP SFX PLAYED (RPM: {self.current_rpm:.0f})")
                            if self.is_currently_cruising: 
                                # print("ENGINE_SIM: Decel pop occurred, exiting cruise mode.")
                                self._reset_cruise_state() 
                            self.decel_pop_gesture_detected_at = 0.0 # Consume gesture
            else: # Timeout for RPM check
                # print(f"ESIM: Decel pop gesture ({self.decel_pop_gesture_detected_at}) timed out waiting for RPM. Current time: {current_time}")
                self.decel_pop_gesture_detected_at = 0.0 
        
        # Reset linger effect if throttle is opened again significantly
        if self.throttle_position > config.THROTTLE_SIGNIFICANTLY_OPEN and current_time > self.decel_pop_linger_active_until : 
            self.decel_pop_linger_active_until = 0 
            self.decel_pop_background_override_key = None
        
        if self.update_call_count % (self.log_interval_updates) == 0: 
            pass
        self.update_call_count +=1
        
        if self.audio_manager: self._update_engine_sound(current_time) 

        if self.state == EngineState.OFF and self.audio_manager and self.audio_manager.is_any_engine_sound_playing():
            self.audio_manager.stop_all_engine_sounds()

    def _update_engine_sound(self, current_sim_time):
        if not self.audio_manager: return
        target_sound_key = None
        
        current_am_loop = self.audio_manager.current_loop_sound_key
        is_fading_to = self.audio_manager.crossfade_to_sound_key if self.audio_manager.is_crossfading else None
        effective_current_sound = is_fading_to if is_fading_to else current_am_loop

        if self.state == EngineState.STARTING or self.state == EngineState.SHUTTING_DOWN:
            pass 
        elif self.state == EngineState.IDLE:
            target_sound_key = "idle"
        elif self.state == EngineState.RUNNING:
            if self.current_rpm < config.RPM_RANGES["low_rpm"][0] + 50 : target_sound_key = "idle"
            elif self.current_rpm < config.RPM_RANGES["low_rpm"][1] - 100: target_sound_key = "low_rpm"
            elif self.current_rpm < config.RPM_RANGES["mid_rpm"][1] - 150: target_sound_key = "mid_rpm"
            else: target_sound_key = "high_rpm"

            if effective_current_sound and not self.is_currently_cruising : 
                if effective_current_sound == "idle" and self.current_rpm < config.RPM_RANGES["low_rpm"][1] * 0.95: target_sound_key = "idle"
                elif effective_current_sound == "low_rpm" and \
                     config.RPM_RANGES["low_rpm"][0] * 0.9 < self.current_rpm < config.RPM_RANGES["mid_rpm"][0] * 1.05: target_sound_key = "low_rpm"
                elif effective_current_sound == "mid_rpm" and \
                     config.RPM_RANGES["mid_rpm"][0] * 0.95 < self.current_rpm < config.RPM_RANGES["high_rpm"][0] * 1.05: target_sound_key = "mid_rpm"
            
            if config.ENABLE_CRUISE_SOUND:
                can_enter_cruise = self.throttle_position >= config.CRUISE_THROTTLE_ENTER_THRESHOLD
                can_maintain_cruise = self.throttle_position >= config.CRUISE_THROTTLE_MAINTAIN_THRESHOLD
                is_at_cruise_rpm = self.current_rpm >= config.CRUISE_RPM_THRESHOLD

                if self.is_currently_cruising:
                    if can_maintain_cruise and is_at_cruise_rpm:
                        target_sound_key = "cruise" 
                    else: # Conditions to maintain cruise lost (likely throttle drop handled by set_throttle)
                          # Let default RPM logic take over if is_currently_cruising was reset
                        pass 
                elif can_enter_cruise and is_at_cruise_rpm: 
                    if effective_current_sound == "high_rpm" and not self.audio_manager.is_crossfading:
                        if self.time_at_cruise_throttle_start > 0: 
                            time_spent_on_high_rpm_at_cruise_thr = current_sim_time - self.time_at_cruise_throttle_start
                            if time_spent_on_high_rpm_at_cruise_thr >= config.CRUISE_HIGH_RPM_SUSTAIN_S:
                                self.is_eligible_for_cruise_sound = True
                        
                    if self.is_eligible_for_cruise_sound:
                        target_sound_key = "cruise"
                        self.is_currently_cruising = True 
                elif not can_enter_cruise and self.time_at_cruise_throttle_start > 0:
                     self.time_at_cruise_throttle_start = 0
                     self.is_eligible_for_cruise_sound = False

            # --- SFX Overrides ---
            active_sfx_override_for_sound_choice = False # Differentiates from SFX actually playing

            # Accel Burst Sound Override (makes main sound mid_rpm during burst)
            if current_sim_time < self.accel_burst_effect_active_until:
                if target_sound_key == "high_rpm" or target_sound_key == "cruise":
                    target_sound_key = "mid_rpm" 
                if self.is_currently_cruising: # Accel burst should take us out of cruise sound
                     # print("ENGINE_SIM: Accel burst effect active, temporarily exiting cruise sound if applicable.")
                     # is_currently_cruising flag itself is reset in set_throttle if burst plays
                     pass # Cruise state is reset by set_throttle when burst plays
                active_sfx_override_for_sound_choice = True
            
            # Decel Pop Sound Override (makes main sound low_rpm during pop linger)
            if not active_sfx_override_for_sound_choice and current_sim_time < self.decel_pop_linger_active_until and self.throttle_position < config.THROTTLE_EFFECTIVELY_ZERO:
                if self.decel_pop_background_override_key:
                    if target_sound_key != self.decel_pop_background_override_key: # Avoids self-xfade
                         target_sound_key = self.decel_pop_background_override_key
                elif target_sound_key == "idle" or target_sound_key == "cruise": 
                    target_sound_key = "low_rpm"
                if self.is_currently_cruising: # Decel pop should take us out of cruise sound
                     # print("ENGINE_SIM: Decel pop effect active, temporarily exiting cruise sound if applicable.")
                     # is_currently_cruising flag itself is reset in update if pop plays
                     pass # Cruise state is reset by update when pop plays
                active_sfx_override_for_sound_choice = True


        elif self.state == EngineState.OFF:
            if self.audio_manager.is_any_engine_sound_playing():
                 self.audio_manager.stop_all_engine_sounds()
            self._reset_cruise_state()
            return 

        if target_sound_key:
            is_new_decision = (target_sound_key != effective_current_sound)
            should_be_playing = self.state in [EngineState.IDLE, EngineState.RUNNING]
            is_silent_check = (not self.audio_manager.is_any_engine_sound_playing(ignore_sfx=True) and \
                              not self.audio_manager.is_crossfading)

            if is_new_decision or (should_be_playing and is_silent_check):
                if target_sound_key != effective_current_sound or is_silent_check: 
                    pass
            self.audio_manager.update_engine_sound(target_sound_key)

    def get_rpm(self): return self.current_rpm
    def get_state(self): return self.state