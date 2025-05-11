# engine_simulator_cp.py
import time
import random
import config_cp as config # Use the CircuitPython config

class EngineState: # No changes needed for this class
    OFF = 0
    STARTING = 1
    IDLE = 2
    RUNNING = 3
    SHUTTING_DOWN = 4

class EngineSimulatorCP:
    def __init__(self, audio_manager): # audio_manager will be an instance of AudioManagerCP
        self.audio_manager = audio_manager
        self.state = EngineState.OFF
        self.current_rpm = 0
        self.throttle_position = 0.0
        self.previous_throttle_position = 0.0 # For detecting throttle changes
        self.throttle_baseline_for_accel_burst = 0.0

        self.last_update_time = time.monotonic() # Use monotonic time
        self.previous_rpm = 0
        self.rpm_change_rate = 0 
        
        self.update_call_count = 0
        self.start_time_for_state = time.monotonic() # Use monotonic time

        self.log_interval_updates = 60 # Log every N updates (e.g., if 60fps, logs once per sec)
        self.log_rpm_change_threshold = 70

        self.starter_sound_played_once = False # Flag to ensure starter sound logic flows correctly
        
        self.accel_burst_effect_active_until = 0
        self.decel_pop_linger_active_until = 0
        self.decel_pop_background_override_key = None # Stores sound to revert to after decel pop

        # Cruise state variables
        self.time_at_cruise_throttle_start = 0
        self.is_eligible_for_cruise_sound = False
        self.is_currently_cruising = False

        print("ENGINE_SIM_CP: EngineSimulatorCP initialized.")

    def start_engine(self):
        if self.state == EngineState.OFF:
            print("ENGINE_SIM_CP: Event - Start Engine")
            self.state = EngineState.STARTING
            self.start_time_for_state = time.monotonic()
            # Use the correct voice index from config
            self.audio_manager.play_sfx("starter", voice_idx=self.audio_manager.sfx_startshut_voice_idx)
            self.current_rpm = 0 
            self.throttle_position = 0.0
            self.previous_throttle_position = 0.0
            self.throttle_baseline_for_accel_burst = 0.0
            self.last_update_time = time.monotonic()
            self.starter_sound_played_once = True 
            self._reset_cruise_state()

    def stop_engine(self):
        if self.state != EngineState.OFF and self.state != EngineState.SHUTTING_DOWN:
            print("ENGINE_SIM_CP: Event - Stop Engine")
            self.state = EngineState.SHUTTING_DOWN
            self.start_time_for_state = time.monotonic()
            self.throttle_position = 0.0 # Ensure throttle is zeroed
            self.throttle_baseline_for_accel_burst = 0.0
            self.audio_manager.stop_engine_sounds_for_shutdown() 
            # Use the correct voice index from config
            self.audio_manager.play_sfx("shutdown", voice_idx=self.audio_manager.sfx_startshut_voice_idx)
            self._reset_cruise_state()

    def _reset_cruise_state(self):
        self.time_at_cruise_throttle_start = 0
        self.is_eligible_for_cruise_sound = False
        self.is_currently_cruising = False

    def set_throttle(self, throttle_value):
        new_throttle_position = max(0.0, min(1.0, throttle_value))
        
        current_time = time.monotonic() # Get current time for cruise logic

        # --- Cruise State Management based on Throttle Input ---
        if self.is_currently_cruising and new_throttle_position < config.CRUISE_THROTTLE_MAINTAIN_THRESHOLD:
            # print(f"ENGINE_SIM_CP: Exiting cruise (throttle {new_throttle_position:.2f} < maintain {config.CRUISE_THROTTLE_MAINTAIN_THRESHOLD:.2f}).")
            self._reset_cruise_state()
        
        elif not self.is_currently_cruising and \
             new_throttle_position >= config.CRUISE_THROTTLE_ENTER_THRESHOLD and \
             self.throttle_position < config.CRUISE_THROTTLE_ENTER_THRESHOLD: # Just crossed enter threshold
            if self.state == EngineState.RUNNING: 
                # print(f"ENGINE_SIM_CP: Throttle reached cruise ENTER threshold ({new_throttle_position:.2f}). Eligibility timer started.")
                self.time_at_cruise_throttle_start = current_time # Use monotonic time
                self.is_eligible_for_cruise_sound = False # Reset eligibility, needs sustain period
        
        elif not self.is_currently_cruising and new_throttle_position < config.CRUISE_THROTTLE_ENTER_THRESHOLD:
            # If throttle drops below enter threshold before cruise is active, reset timer
            if self.time_at_cruise_throttle_start != 0:
                # print(f"ENGINE_SIM_CP: Throttle ({new_throttle_position:.2f}) dropped below cruise ENTER before activation. Resetting timer.")
                self.time_at_cruise_throttle_start = 0 
                self.is_eligible_for_cruise_sound = False

        # --- Accel Burst Logic ---
        if config.ENABLE_ACCEL_BURST and self.state in [EngineState.IDLE, EngineState.RUNNING]:
            is_significant_increase = new_throttle_position > (self.throttle_baseline_for_accel_burst + config.ACCEL_BURST_THROTTLE_THRESHOLD)
            is_to_high_throttle = new_throttle_position >= config.ACCEL_BURST_MIN_NEW_THROTTLE
            was_at_low_throttle = self.throttle_baseline_for_accel_burst <= config.ACCEL_BURST_MAX_OLD_THROTTLE

            if is_significant_increase and is_to_high_throttle and was_at_low_throttle:
                if self.audio_manager.play_accel_burst():
                    self.accel_burst_effect_active_until = current_time + \
                        (config.SOUND_DURATIONS["accel_burst"] * config.ACCEL_BURST_EFFECT_DURATION_MULTIPLIER)
                    # print(f"ENGINE_SIM_CP: ---> ACCEL BURST SFX. Effect until {self.accel_burst_effect_active_until:.2f}")
                    self.throttle_baseline_for_accel_burst = new_throttle_position 
                    if self.is_currently_cruising:
                        # print("ENGINE_SIM_CP: Accel burst ended cruise mode.")
                        self._reset_cruise_state()
            
            elif new_throttle_position <= self.throttle_baseline_for_accel_burst: # Throttle decreased or same
                self.throttle_baseline_for_accel_burst = new_throttle_position
            # Gradual increase in baseline if throttle creeps up slowly
            elif new_throttle_position < (self.throttle_baseline_for_accel_burst + config.ACCEL_BURST_BASELINE_CREEP_THRESHOLD):
                self.throttle_baseline_for_accel_burst = new_throttle_position

        self.previous_throttle_position = self.throttle_position 
        self.throttle_position = new_throttle_position


    def update(self):
        current_time = time.monotonic() # Use monotonic time
        dt = current_time - self.last_update_time
        if dt <= 0.0001: dt = 0.001 # Prevent division by zero or excessively small dt
        self.last_update_time = current_time

        # Update audio manager (handles crossfades, etc.)
        if self.audio_manager: self.audio_manager.update() 
        else: return # Should not happen if initialized correctly

        self.previous_rpm = self.current_rpm

        # --- State Machine ---
        if self.state == EngineState.STARTING:
            target_idle_rpm = config.IDLE_RPM
            time_in_starting_state = current_time - self.start_time_for_state
            
            # Ramp RPM up during starter sound
            if self.current_rpm < target_idle_rpm:
                rpm_to_gain = target_idle_rpm # Total RPM to gain from 0
                # Duration for RPM ramp, slightly less than sound to allow sound to finish "naturally"
                duration = max(0.1, config.STARTER_SOUND_DURATION_TARGET_S - 0.3)
                rate = rpm_to_gain / duration if duration > 0 else rpm_to_gain * 10 # RPM per second
                self.current_rpm += rate * dt
            self.current_rpm = min(self.current_rpm, target_idle_rpm) # Cap at idle RPM

            sfx_busy = self.audio_manager.is_sfx_starter_shutdown_busy()
            # Starter sound considered done if SFX channel is free, it was played, and some time has passed
            starter_done_conditions_met = (not sfx_busy and self.starter_sound_played_once and time_in_starting_state > 0.5)
            
            if (starter_done_conditions_met and self.current_rpm >= target_idle_rpm) or \
               time_in_starting_state > config.STARTER_TIMEOUT_S:
                # print(f"ENGINE_SIM_CP: Starting finished. SFX Busy: {sfx_busy}, PlayedOnce: {self.starter_sound_played_once}, TimeInState: {time_in_starting_state:.2f}, RPM: {self.current_rpm:.0f}")
                self.current_rpm = config.IDLE_RPM # Ensure it settles at IDLE_RPM
                self.state = EngineState.IDLE
                # print(f"ENGINE_SIM_CP: State -> IDLE. RPM: {self.current_rpm:.0f}.")
                self.starter_sound_played_once = False # Reset for next start
                self.throttle_baseline_for_accel_burst = self.throttle_position # Set baseline for accel
                self._reset_cruise_state()


        elif self.state == EngineState.IDLE or self.state == EngineState.RUNNING:
            target_rpm = config.IDLE_RPM # Default target is idle
            if self.throttle_position > config.THROTTLE_EFFECTIVELY_ZERO: # If throttle applied
                if self.state == EngineState.IDLE: 
                    self.state = EngineState.RUNNING # Transition from IDLE to RUNNING
                    # print(f"ENGINE_SIM_CP: State -> RUNNING (throttle applied)")
                
                # If cruising, target RPM is MAX_RPM (sound handles the "cruise" feel)
                if self.is_currently_cruising and self.throttle_position >= config.CRUISE_THROTTLE_MAINTAIN_THRESHOLD:
                    target_rpm = config.MAX_RPM
                # If in cruise entry throttle range (but not yet cruising), also target MAX_RPM
                elif self.throttle_position >= config.CRUISE_THROTTLE_ENTER_THRESHOLD:
                     target_rpm = config.MAX_RPM 
                # Standard running: RPM based on throttle position
                else: 
                     # Use a power curve for more natural throttle response
                     throttle_effect = pow(self.throttle_position, 0.7) 
                     target_rpm = config.IDLE_RPM + (config.MAX_RPM - config.IDLE_RPM) * throttle_effect
            
            rpm_diff = target_rpm - self.current_rpm
            
            # Determine accel/decel rates
            current_decel_rate = config.RPM_DECEL_RATE
            current_idle_return_rate = config.RPM_IDLE_RETURN_RATE

            # If decel pop effect is lingering and throttle is off, slow down RPM fall
            if current_time < self.decel_pop_linger_active_until and \
               self.throttle_position < config.THROTTLE_EFFECTIVELY_ZERO and rpm_diff < 0:
                current_decel_rate *= config.DECEL_POP_RPM_FALL_RATE_MODIFIER
                if self.throttle_position < 0.01: # Very low throttle
                     current_idle_return_rate *= config.DECEL_POP_RPM_FALL_RATE_MODIFIER

            rate_factor = config.RPM_ACCEL_RATE if rpm_diff > 0 else current_decel_rate
            # If throttle is off and RPM is dropping towards idle
            if self.throttle_position < config.THROTTLE_EFFECTIVELY_ZERO and rpm_diff < 0 :
                rate_factor = current_idle_return_rate # Use specific idle return rate
                if self.is_currently_cruising: 
                    # print("ENGINE_SIM_CP: Throttle released while cruising, exiting cruise.")
                    self._reset_cruise_state() # Exit cruise if throttle released
            
            change = rate_factor * dt # Calculate RPM change for this frame
            if rpm_diff > 0: # Accelerating
                self.current_rpm += change
                if self.current_rpm > target_rpm: self.current_rpm = target_rpm # Cap at target
            elif rpm_diff < 0: # Decelerating
                self.current_rpm -= change
                if self.current_rpm < target_rpm: self.current_rpm = target_rpm # Floor at target

            # Transition from RUNNING to IDLE if throttle is off and RPM is near idle
            if self.throttle_position < config.THROTTLE_EFFECTIVELY_ZERO and \
               self.current_rpm <= config.IDLE_RPM + 50 and self.state == EngineState.RUNNING: 
                # Only transition to IDLE if decel pop effect is not active
                if current_time >= self.decel_pop_linger_active_until:
                    self.state = EngineState.IDLE
                    # print(f"ENGINE_SIM_CP: State -> IDLE (throttle off, RPM near idle)")
                    self.current_rpm = config.IDLE_RPM # Settle at IDLE_RPM
                    self.throttle_baseline_for_accel_burst = self.throttle_position # Update baseline
                    self.decel_pop_background_override_key = None # Clear decel pop override sound
                    if self.is_currently_cruising:
                        # print("ENGINE_SIM_CP: Transitioning to IDLE from cruise, exiting cruise.")
                        self._reset_cruise_state() # Exit cruise if transitioning to IDLE
            
            # Clamp RPM to valid range for current state
            min_for_state = config.IDLE_RPM if self.state == EngineState.IDLE else config.MIN_RPM
            self.current_rpm = max(min_for_state, min(self.current_rpm, config.MAX_RPM))


        elif self.state == EngineState.SHUTTING_DOWN:
            time_in_state = current_time - self.start_time_for_state
            sfx_busy = self.audio_manager.is_sfx_starter_shutdown_busy()
            # Shutdown considered done if SFX channel is free and some time has passed
            shutdown_sound_done = not sfx_busy and time_in_state > 0.5
            
            # Timeout for shutdown process
            shutdown_sound_duration = config.SOUND_DURATIONS.get("shutdown", 5.0) # Default if not in config
            max_shutdown_time = shutdown_sound_duration + 2.0 # Allow sound to play plus buffer

            # Rapidly decrease RPM during shutdown
            self.current_rpm -= config.RPM_DECEL_RATE * 2.0 * dt 
            
            # Conditions to transition to OFF state
            if self.current_rpm <= 5 or \
               (shutdown_sound_done and self.current_rpm < config.MIN_RPM / 4) or \
               time_in_state > max_shutdown_time:
                # print(f"ENGINE_SIM_CP: Shutdown finished. SFX Busy: {sfx_busy}, TimeInState: {time_in_state:.2f}, RPM: {self.current_rpm:.0f}")
                self.current_rpm = 0
                self.state = EngineState.OFF
                # print(f"ENGINE_SIM_CP: State -> OFF. Shutdown complete.")
                self.throttle_baseline_for_accel_burst = 0.0 
                self._reset_cruise_state()


        # Calculate RPM change rate for SFX logic
        self.rpm_change_rate = (self.current_rpm - self.previous_rpm) / dt if dt > 0.00001 else 0 

        # --- SFX Logic (Decel Pop) ---
        if config.ENABLE_DECEL_POPS and self.state in [EngineState.RUNNING, EngineState.IDLE]:
            # Conditions for playing decel pop:
            # 1. Throttle just closed sharply from a significantly open position
            throttle_just_closed_sharply = (self.throttle_position < config.THROTTLE_EFFECTIVELY_ZERO and
                                           self.previous_throttle_position > config.THROTTLE_SIGNIFICANTLY_OPEN)
            # 2. Engine is decelerating sharply (negative RPM change rate)
            is_decelerating_sharply = self.rpm_change_rate < config.LOAD_THRESHOLD_DECEL
            
            if is_decelerating_sharply and throttle_just_closed_sharply and \
               self.current_rpm > config.DECEL_POP_RPM_THRESHOLD:
                if random.random() < config.DECEL_POP_CHANCE: # Random chance to play
                    if self.audio_manager.play_decel_pop():
                        # print(f"ENGINE_SIM_CP: ---> DECEL POP SFX PLAYED.")
                        self.decel_pop_linger_active_until = current_time + config.DECEL_POP_LINGER_DURATION_S
                        
                        # Determine background sound during decel pop (usually low_rpm)
                        current_loop = self.audio_manager.current_loop_sound_key
                        fading_to = self.audio_manager.crossfade_to_sound_key if self.audio_manager.is_crossfading else None
                        self.decel_pop_background_override_key = fading_to if fading_to else current_loop
                        
                        # Force background to low_rpm if it was higher or idle
                        if self.decel_pop_background_override_key in ["high_rpm", "mid_rpm", "cruise", "idle"]: 
                            self.decel_pop_background_override_key = "low_rpm"
                        
                        if self.is_currently_cruising:
                            # print("ENGINE_SIM_CP: Decel pop occurred, exiting cruise mode.")
                            self._reset_cruise_state() # Exit cruise if decel pop occurs
        
        # Clear decel pop linger effect if throttle is reapplied or effect times out
        if self.throttle_position > config.THROTTLE_SIGNIFICANTLY_OPEN and \
           current_time > self.decel_pop_linger_active_until: 
            self.decel_pop_linger_active_until = 0 
            self.decel_pop_background_override_key = None
        
        # --- Logging (optional, can be spammy on serial) ---
        if self.update_call_count % self.log_interval_updates == 0: # Log periodically
            # print(f"ESIM_CP St:{self.state} RPM:{self.current_rpm:.0f} Thr:{self.throttle_position:.2f} Change:{self.rpm_change_rate:.0f} CruiseElig:{self.is_eligible_for_cruise_sound} CruiseAct:{self.is_currently_cruising} CruiseTStart:{self.time_at_cruise_throttle_start:.1f}")
            pass # Comment out print to reduce serial traffic
        self.update_call_count +=1
        
        # Update engine sound based on current state and RPM
        if self.audio_manager: self._update_engine_sound(current_time) 

        # Ensure all engine sounds are stopped if engine is OFF
        if self.state == EngineState.OFF and self.audio_manager and \
           self.audio_manager.is_any_engine_sound_playing(ignore_sfx=True): # Check only engine loops
            # print("ENGINE_SIM_CP: Engine is OFF, stopping all engine sounds.")
            self.audio_manager.stop_all_engine_sounds()


    def _update_engine_sound(self, current_sim_time): # current_sim_time is time.monotonic()
        if not self.audio_manager: return
        target_sound_key = None
        
        # Determine the "effective" current sound, considering ongoing crossfades
        current_am_loop = self.audio_manager.current_loop_sound_key
        is_fading_to_sound = self.audio_manager.crossfade_to_sound_key if self.audio_manager.is_crossfading else None
        effective_current_sound = is_fading_to_sound if is_fading_to_sound else current_am_loop

        # --- State-based sound selection ---
        if self.state == EngineState.STARTING or self.state == EngineState.SHUTTING_DOWN:
            # Sounds for these states are handled by play_sfx in start_engine/stop_engine
            pass 
        elif self.state == EngineState.IDLE:
            target_sound_key = "idle"
        elif self.state == EngineState.RUNNING:
            # --- Default RPM-based sound selection ---
            # Determine sound based on RPM ranges, with some overlap for hysteresis
            if self.current_rpm < config.RPM_RANGES["low_rpm"][0] + 50 : target_sound_key = "idle"
            elif self.current_rpm < config.RPM_RANGES["low_rpm"][1] - 100: target_sound_key = "low_rpm"
            elif self.current_rpm < config.RPM_RANGES["mid_rpm"][1] - 150: target_sound_key = "mid_rpm"
            else: target_sound_key = "high_rpm"

            # --- Hysteresis for RPM sounds (prevents rapid switching at boundaries) ---
            # If a sound is already playing (or fading to), prefer to keep it if RPM is within a wider range
            if effective_current_sound and not self.is_currently_cruising : 
                if effective_current_sound == "idle" and self.current_rpm < config.RPM_RANGES["low_rpm"][1] * 0.95:
                    target_sound_key = "idle"
                elif effective_current_sound == "low_rpm" and \
                     config.RPM_RANGES["low_rpm"][0] * 0.9 < self.current_rpm < config.RPM_RANGES["mid_rpm"][0] * 1.05:
                    target_sound_key = "low_rpm"
                elif effective_current_sound == "mid_rpm" and \
                     config.RPM_RANGES["mid_rpm"][0] * 0.95 < self.current_rpm < config.RPM_RANGES["high_rpm"][0] * 1.05:
                    target_sound_key = "mid_rpm"
            
            # --- Cruise Sound Logic ---
            if config.ENABLE_CRUISE_SOUND:
                can_enter_cruise_throttle = self.throttle_position >= config.CRUISE_THROTTLE_ENTER_THRESHOLD
                can_maintain_cruise_throttle = self.throttle_position >= config.CRUISE_THROTTLE_MAINTAIN_THRESHOLD
                is_at_cruise_rpm = self.current_rpm >= config.CRUISE_RPM_THRESHOLD

                if self.is_currently_cruising: # If already in cruise mode
                    if can_maintain_cruise_throttle and is_at_cruise_rpm:
                        target_sound_key = "cruise" 
                    else:
                        # This case should ideally be handled by _reset_cruise_state() in set_throttle or update()
                        # If cruise conditions are no longer met, self.is_currently_cruising should be false.
                        # Default RPM logic will pick the sound.
                        # print(f"ENGINE_SIM_CP: Cruise conditions lost (Thr:{self.throttle_position:.2f} RPM:{self.current_rpm:.0f}). Cruise flag was {self.is_currently_cruising}")
                        pass # Fall through to default RPM logic

                elif can_enter_cruise_throttle and is_at_cruise_rpm: 
                    # Conditions met to potentially enter cruise mode
                    # Must be on high_rpm sound and sustain it for a duration at cruise throttle
                    if effective_current_sound == "high_rpm" and not self.audio_manager.is_crossfading:
                        if self.time_at_cruise_throttle_start > 0: 
                            time_spent_at_cruise_thr = current_sim_time - self.time_at_cruise_throttle_start
                            if time_spent_at_cruise_thr >= config.CRUISE_HIGH_RPM_SUSTAIN_S:
                                self.is_eligible_for_cruise_sound = True
                                # print(f"ENGINE_SIM_CP: Cruise ELIGIBLE after {time_spent_at_cruise_thr:.2f}s on high_rpm at cruise throttle.")
                        
                    if self.is_eligible_for_cruise_sound:
                        target_sound_key = "cruise"
                        self.is_currently_cruising = True # Activate cruise mode
                        # print(f"ENGINE_SIM_CP: *** Transitioning TO CRUISE sound. ***")
                
                elif not can_enter_cruise_throttle and self.time_at_cruise_throttle_start > 0:
                     # Throttle dropped below entry threshold before cruise fully activated
                     self.time_at_cruise_throttle_start = 0
                     self.is_eligible_for_cruise_sound = False
                     # print(f"ENGINE_SIM_CP: Cruise eligibility timer reset (throttle {self.throttle_position:.2f} below enter threshold).")


            # --- SFX Overrides (Accel Burst, Decel Pop) ---
            # These can temporarily change the target engine sound
            active_sfx_override = False
            if current_sim_time < self.accel_burst_effect_active_until:
                # During accel burst, might want to use a mid-range sound even if RPM is high
                if target_sound_key == "high_rpm" or target_sound_key == "cruise":
                    target_sound_key = "mid_rpm" 
                if self.is_currently_cruising:
                    # print("ENGINE_SIM_CP: Accel burst effect active, temporarily overriding cruise sound & state.")
                    self._reset_cruise_state() # Accel burst cancels cruise
                active_sfx_override = True
            
            # If not overridden by accel burst, check for decel pop override
            if not active_sfx_override and \
               current_sim_time < self.decel_pop_linger_active_until and \
               self.throttle_position < config.THROTTLE_EFFECTIVELY_ZERO: # Throttle must be off
                if self.decel_pop_background_override_key:
                    # If a specific background sound was set for decel pop, use it
                    if target_sound_key != self.decel_pop_background_override_key:
                         target_sound_key = self.decel_pop_background_override_key
                # Fallback if no specific override, or if current target is idle/cruise
                elif target_sound_key == "idle" or target_sound_key == "cruise": 
                    target_sound_key = "low_rpm" # Default to low_rpm during decel pop
                
                if self.is_currently_cruising:
                    # print("ENGINE_SIM_CP: Decel pop effect active, temporarily overriding cruise sound & state.")
                    self._reset_cruise_state() # Decel pop cancels cruise

        elif self.state == EngineState.OFF:
            # If engine is off, ensure no engine loop sounds are playing
            if self.audio_manager.is_any_engine_sound_playing(ignore_sfx=True):
                 self.audio_manager.stop_all_engine_sounds()
            self._reset_cruise_state() # Ensure cruise state is reset
            return # No further sound updates needed for OFF state

        # --- Final Sound Update Call to Audio Manager ---
        if target_sound_key:
            # Determine if the sound decision is new or if sounds need to be restarted
            is_new_sound_decision = (target_sound_key != effective_current_sound)
            # Check if engine should be making sound but isn't (e.g., after SFX finishes)
            engine_should_be_playing_loop = self.state in [EngineState.IDLE, EngineState.RUNNING]
            no_engine_loop_is_active = (not self.audio_manager.mixer.voice[self.audio_manager.engine_voice_idx1].playing and \
                                        not self.audio_manager.mixer.voice[self.audio_manager.engine_voice_idx2].playing and \
                                        not self.audio_manager.is_crossfading)


            if is_new_sound_decision or (engine_should_be_playing_loop and no_engine_loop_is_active):
                # Minimal logging for sound changes to reduce spam
                # if target_sound_key != effective_current_sound or no_engine_loop_is_active : 
                #     print(f"ENGINE_SIM_CP: Sound Out => Target: '{target_sound_key}' (PrevEff: '{effective_current_sound}', EngLoopActive:{not no_engine_loop_is_active}, Cruise:{self.is_currently_cruising})")
                pass
            
            self.audio_manager.update_engine_sound(target_sound_key)

    def get_rpm(self): return self.current_rpm
    def get_state(self): return self.state