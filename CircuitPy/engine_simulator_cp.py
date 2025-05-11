# engine_simulator_cp.py
import time
import random
import config_cp as config # Use the CircuitPython config

class EngineState:
    OFF = 0
    STARTING = 1
    IDLE = 2
    RUNNING = 3
    SHUTTING_DOWN = 4

class EngineSimulatorCP:
    def __init__(self, audio_manager):
        self.audio_manager = audio_manager
        self.state = EngineState.OFF
        self.current_rpm = 0
        self.throttle_position = 0.0
        # self.previous_throttle_position = 0.0 # No longer primary for new gesture logic
                                               # but can be useful for other simple checks if needed.
                                               # For now, relying on new gesture logic.

        self.last_update_time = time.monotonic()
        self.previous_rpm = 0 # Still useful for rpm_change_rate
        self.rpm_change_rate = 0 
        
        self.update_call_count = 0
        self.start_time_for_state = time.monotonic()

        self.log_interval_updates = 60 

        self.starter_sound_played_once = False
        
        # Accel Burst related (New logic)
        self.throttle_history_for_accel = [] # List of (timestamp, throttle_value)
        self.accel_burst_effect_active_until = 0

        # Decel Pop related (New logic)
        self.last_known_high_throttle_value = 0.0
        self.last_known_high_throttle_time = 0.0
        self.decel_pop_gesture_detected_at = 0.0 # Timestamp when gesture was detected by set_throttle
        self.decel_pop_linger_active_until = 0
        self.decel_pop_background_override_key = None
        
        self.time_at_cruise_throttle_start = 0
        self.is_eligible_for_cruise_sound = False
        self.is_currently_cruising = False

        print("ENGINE_SIM_CP: EngineSimulatorCP initialized with new gesture logic.")

    def _reset_special_effects_state(self):
        self.throttle_history_for_accel = []
        self.accel_burst_effect_active_until = 0
        self.last_known_high_throttle_value = 0.0
        self.last_known_high_throttle_time = 0.0
        self.decel_pop_gesture_detected_at = 0.0
        self.decel_pop_linger_active_until = 0
        self.decel_pop_background_override_key = None


    def start_engine(self):
        if self.state == EngineState.OFF:
            print("ENGINE_SIM_CP: Event - Start Engine")
            self.state = EngineState.STARTING
            self.start_time_for_state = time.monotonic()
            self.audio_manager.play_sfx("starter", voice_idx=self.audio_manager.sfx_startshut_voice_idx)
            self.current_rpm = 0 
            self.throttle_position = 0.0
            self.last_update_time = time.monotonic()
            self.starter_sound_played_once = True 
            self._reset_cruise_state()
            self._reset_special_effects_state() # Reset gesture states

    def stop_engine(self):
        if self.state != EngineState.OFF and self.state != EngineState.SHUTTING_DOWN:
            print("ENGINE_SIM_CP: Event - Stop Engine")
            self.state = EngineState.SHUTTING_DOWN
            self.start_time_for_state = time.monotonic()
            self.throttle_position = 0.0
            self.audio_manager.stop_engine_sounds_for_shutdown() 
            self.audio_manager.play_sfx("shutdown", voice_idx=self.audio_manager.sfx_startshut_voice_idx)
            self._reset_cruise_state()
            self._reset_special_effects_state() # Reset gesture states

    def _reset_cruise_state(self):
        self.time_at_cruise_throttle_start = 0
        self.is_eligible_for_cruise_sound = False
        self.is_currently_cruising = False

    def set_throttle(self, throttle_value):
        current_time = time.monotonic()
        # Keep track of the throttle before this specific call for delta checks if needed
        # For the new gesture logic, self.throttle_position is the "previous" from the last set_throttle call.
        _previous_throttle_this_call = self.throttle_position 
        
        new_throttle_clamped = max(0.0, min(1.0, throttle_value))
        
        # --- Cruise State Management ---
        if self.is_currently_cruising and new_throttle_clamped < config.CRUISE_THROTTLE_MAINTAIN_THRESHOLD:
            self._reset_cruise_state()
        elif not self.is_currently_cruising and \
             new_throttle_clamped >= config.CRUISE_THROTTLE_ENTER_THRESHOLD and \
             _previous_throttle_this_call < config.CRUISE_THROTTLE_ENTER_THRESHOLD: 
            if self.state == EngineState.RUNNING : 
                self.time_at_cruise_throttle_start = current_time
                self.is_eligible_for_cruise_sound = False 
        elif not self.is_currently_cruising and new_throttle_clamped < config.CRUISE_THROTTLE_ENTER_THRESHOLD:
            if self.time_at_cruise_throttle_start != 0 : 
                 self.time_at_cruise_throttle_start = 0 
                 self.is_eligible_for_cruise_sound = False

        # --- Accel Burst Gesture Detection (New Logic) ---
        if config.ENABLE_ACCEL_BURST and self.state in [EngineState.IDLE, EngineState.RUNNING]:
            self.throttle_history_for_accel.append((current_time, new_throttle_clamped))
            # Prune old history
            self.throttle_history_for_accel = [
                (t, thr) for t, thr in self.throttle_history_for_accel 
                if current_time - t <= config.ACCEL_BURST_HISTORY_DURATION_S
            ]

            if new_throttle_clamped >= config.ACCEL_BURST_MIN_END_THROTTLE:
                if not (current_time < self.accel_burst_effect_active_until): # Check if effect not already active
                    for t_old, thr_old in self.throttle_history_for_accel:
                        if current_time - t_old <= config.ACCEL_BURST_FLICK_WINDOW_S: # Within flick time
                            if thr_old <= config.ACCEL_BURST_MAX_START_THROTTLE: # Started low enough
                                throttle_jump = new_throttle_clamped - thr_old
                                if throttle_jump >= config.ACCEL_BURST_MIN_JUMP_VALUE: # Jumped enough
                                    if self.audio_manager.play_accel_burst():
                                        self.accel_burst_effect_active_until = current_time + \
                                            (config.SOUND_DURATIONS["accel_burst"] * config.ACCEL_BURST_EFFECT_DURATION_MULTIPLIER)
                                        self.throttle_history_for_accel = [] # Clear history
                                        if self.is_currently_cruising: 
                                            self._reset_cruise_state()
                                        # print(f"ESIM_CP: ---> ACCEL BURST by flick from {thr_old:.2f} to {new_throttle_clamped:.2f}")
                                        break 
        
        # --- Decel Pop Gesture Detection (New Logic) ---
        if config.ENABLE_DECEL_POPS and self.state in [EngineState.IDLE, EngineState.RUNNING]:
            if new_throttle_clamped >= config.DECEL_POP_HIGH_THROTTLE_THRESHOLD:
                self.last_known_high_throttle_value = max(self.last_known_high_throttle_value, new_throttle_clamped)
                self.last_known_high_throttle_time = current_time
            
            # Check for drop if we were high and now low, and no gesture is pending RPM check
            # _previous_throttle_this_call helps detect just crossing the threshold
            if self.decel_pop_gesture_detected_at == 0.0 and \
               self.last_known_high_throttle_value >= config.DECEL_POP_HIGH_THROTTLE_THRESHOLD and \
               new_throttle_clamped <= config.DECEL_POP_LOW_THROTTLE_THRESHOLD and \
               _previous_throttle_this_call > config.DECEL_POP_LOW_THROTTLE_THRESHOLD: 

                time_since_high = current_time - self.last_known_high_throttle_time
                throttle_drop = self.last_known_high_throttle_value - new_throttle_clamped

                if time_since_high <= config.DECEL_POP_MAX_FLICK_DURATION_S and \
                   throttle_drop >= config.DECEL_POP_MIN_DROP_VALUE:
                    self.decel_pop_gesture_detected_at = current_time
                    # print(f"ESIM_CP: DECEL POP GESTURE (from {self.last_known_high_throttle_value:.2f} to {new_throttle_clamped:.2f}). Wait RPM.")
                    self.last_known_high_throttle_value = 0.0 # Require going high again
            
            if self.decel_pop_gesture_detected_at != 0.0 and new_throttle_clamped > (config.DECEL_POP_LOW_THROTTLE_THRESHOLD + 0.05):
                # print(f"ESIM_CP: Decel pop gesture cancelled (throttle up to {new_throttle_clamped:.2f})")
                self.decel_pop_gesture_detected_at = 0.0
        
        self.throttle_position = new_throttle_clamped


    def update(self):
        current_time = time.monotonic()
        dt = current_time - self.last_update_time
        if dt <= 0.0001: dt = 0.001 
        self.last_update_time = current_time

        if self.audio_manager: self.audio_manager.update() 
        else: return

        self.previous_rpm = self.current_rpm

        # --- State Machine (largely similar to desktop, ensure time.monotonic() usage) ---
        if self.state == EngineState.STARTING:
            target_idle_rpm = config.IDLE_RPM
            time_in_starting_state = current_time - self.start_time_for_state
            if self.current_rpm < target_idle_rpm:
                rpm_to_gain = target_idle_rpm 
                duration = max(0.1, config.STARTER_SOUND_DURATION_TARGET_S - 0.3)
                rate = rpm_to_gain / duration if duration > 0 else rpm_to_gain * 10
                self.current_rpm += rate * dt
            self.current_rpm = min(self.current_rpm, target_idle_rpm)
            sfx_busy = self.audio_manager.is_sfx_starter_shutdown_busy() # Use CP specific check
            starter_done = (not sfx_busy and self.starter_sound_played_once and time_in_starting_state > 0.5)
            if (starter_done and self.current_rpm >= target_idle_rpm) or \
               time_in_starting_state > config.STARTER_TIMEOUT_S:
                self.current_rpm = config.IDLE_RPM 
                self.state = EngineState.IDLE
                self.starter_sound_played_once = False 
                self._reset_cruise_state()
                # print(f"ENGINE_SIM_CP: State -> IDLE. RPM: {self.current_rpm:.0f}.")


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
                if current_time >= self.decel_pop_linger_active_until and current_time >= self.accel_burst_effect_active_until:
                    self.state = EngineState.IDLE
                    self.current_rpm = config.IDLE_RPM 
                    self.decel_pop_background_override_key = None 
                    if self.is_currently_cruising: self._reset_cruise_state()
                    # print(f"ENGINE_SIM_CP: State -> IDLE (throttle off, RPM near idle)")
            
            min_for_state = config.IDLE_RPM if self.state == EngineState.IDLE else config.MIN_RPM
            self.current_rpm = max(min_for_state, min(self.current_rpm, config.MAX_RPM))


        elif self.state == EngineState.SHUTTING_DOWN:
            time_in_state = current_time - self.start_time_for_state
            sfx_busy = self.audio_manager.is_sfx_starter_shutdown_busy()
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
                # print(f"ENGINE_SIM_CP: State -> OFF. Shutdown complete.")

        self.rpm_change_rate = (self.current_rpm - self.previous_rpm) / dt if dt > 0.00001 else 0 

        # --- SFX Logic (Decel Pop - RPM Check and Play - New Logic) ---
        if self.decel_pop_gesture_detected_at != 0.0 and \
           config.ENABLE_DECEL_POPS and self.state in [EngineState.RUNNING, EngineState.IDLE]:
            
            if current_time - self.decel_pop_gesture_detected_at <= config.DECEL_POP_RPM_CHECK_WINDOW_S:
                if self.current_rpm > config.DECEL_POP_RPM_THRESHOLD:
                    if random.random() < config.DECEL_POP_CHANCE:
                        if self.audio_manager.play_decel_pop(): # AudioManager handles cooldown
                            self.decel_pop_linger_active_until = current_time + config.DECEL_POP_LINGER_DURATION_S
                            current_loop = self.audio_manager.current_loop_sound_key
                            fading_to = self.audio_manager.crossfade_to_sound_key if self.audio_manager.is_crossfading else None
                            self.decel_pop_background_override_key = fading_to if fading_to else current_loop
                            if self.decel_pop_background_override_key in ["high_rpm", "mid_rpm", "cruise", "idle"] : 
                                self.decel_pop_background_override_key = "low_rpm"
                            
                            # print(f"ESIM_CP: ---> DECEL POP SFX PLAYED (RPM: {self.current_rpm:.0f})")
                            if self.is_currently_cruising: 
                                self._reset_cruise_state() 
                            self.decel_pop_gesture_detected_at = 0.0 # Consume gesture
            else: # Timeout for RPM check
                # print(f"ESIM_CP: Decel pop gesture timed out for RPM.")
                self.decel_pop_gesture_detected_at = 0.0 
        
        if self.throttle_position > config.THROTTLE_SIGNIFICANTLY_OPEN and current_time > self.decel_pop_linger_active_until : 
            self.decel_pop_linger_active_until = 0 
            self.decel_pop_background_override_key = None
        
        if self.update_call_count % (self.log_interval_updates) == 0: 
            # print(f"ESIM_CP St:{self.state} RPM:{self.current_rpm:.0f} Thr:{self.throttle_position:.2f} AccAct:{current_time < self.accel_burst_effect_active_until} DecPopAct:{current_time < self.decel_pop_linger_active_until}")
            pass
        self.update_call_count +=1
        
        if self.audio_manager: self._update_engine_sound(current_time) 

        if self.state == EngineState.OFF and self.audio_manager and \
           self.audio_manager.is_any_engine_sound_playing(ignore_sfx=True):
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

            # --- SFX Overrides (New Logic) ---
            active_sfx_override_for_sound_choice = False
            if current_sim_time < self.accel_burst_effect_active_until:
                if target_sound_key == "high_rpm" or target_sound_key == "cruise":
                    target_sound_key = "mid_rpm" 
                # Cruise state is reset by set_throttle when burst actually plays
                active_sfx_override_for_sound_choice = True
            
            if not active_sfx_override_for_sound_choice and \
               current_sim_time < self.decel_pop_linger_active_until and \
               self.throttle_position < config.THROTTLE_EFFECTIVELY_ZERO:
                if self.decel_pop_background_override_key:
                    if target_sound_key != self.decel_pop_background_override_key:
                         target_sound_key = self.decel_pop_background_override_key
                elif target_sound_key == "idle" or target_sound_key == "cruise": 
                    target_sound_key = "low_rpm" 
                # Cruise state is reset by update when pop actually plays

        elif self.state == EngineState.OFF:
            if self.audio_manager.is_any_engine_sound_playing(ignore_sfx=True):
                 self.audio_manager.stop_all_engine_sounds()
            self._reset_cruise_state()
            return 

        if target_sound_key:
            is_new_decision = (target_sound_key != effective_current_sound)
            should_be_playing = self.state in [EngineState.IDLE, EngineState.RUNNING]
            
            # Check if any engine loop is playing on the dedicated voices
            e1_playing = self.audio_manager.mixer.voice[self.audio_manager.engine_voice_idx1].playing
            e2_playing = self.audio_manager.mixer.voice[self.audio_manager.engine_voice_idx2].playing
            no_engine_loop_is_active = not (e1_playing or e2_playing or self.audio_manager.is_crossfading)

            if is_new_decision or (should_be_playing and no_engine_loop_is_active):
                # if target_sound_key != effective_current_sound or no_engine_loop_is_active : 
                #     print(f"ESIM_CP: Sound Out => Target: '{target_sound_key}' (Eff: '{effective_current_sound}', Cruise:{self.is_currently_cruising})")
                pass
            self.audio_manager.update_engine_sound(target_sound_key)

    def get_rpm(self): return self.current_rpm
    def get_state(self): return self.state