# audio_manager.py
import pygame
import time
# import config # Config values will be passed in __init__
import os

class AudioManager:
    def __init__(self, mixer_frequency, mixer_size, mixer_channels, mixer_buffer,
                 num_audio_channels, sound_files, sfx_volume, main_engine_volume,
                 crossfade_duration_ms, accel_burst_cooldown_ms, decel_pop_cooldown_ms,
                 enable_accel_burst, enable_decel_pops):
        
        self.sounds = {}
        self.engine_channel1 = None
        self.engine_channel2 = None
        self.sfx_channel = None
        self.burst_pop_channel = None
        self.pop_channel = None # Alias

        self.active_engine_channel = None
        self.inactive_engine_channel = None
        self.current_loop_sound_key = None
        self.is_crossfading = False
        self.crossfade_start_time = 0
        self.crossfade_from_sound_key = None
        self.crossfade_to_sound_key = None
        self.last_pop_time = 0
        self.last_accel_burst_time = 0
        self.xfade_log_counter = 0 

        self.sound_files_config = sound_files
        self.sfx_volume_config = sfx_volume
        self.main_engine_volume_config = main_engine_volume
        self.crossfade_duration_ms_config = crossfade_duration_ms
        self.accel_burst_cooldown_ms_config = accel_burst_cooldown_ms
        self.decel_pop_cooldown_ms_config = decel_pop_cooldown_ms
        self.enable_accel_burst_config = enable_accel_burst
        self.enable_decel_pops_config = enable_decel_pops

        try:
            if not pygame.mixer.get_init():
                 pygame.mixer.init(
                    frequency=mixer_frequency,
                    size=mixer_size,
                    channels=mixer_channels,
                    buffer=mixer_buffer
                )
            else:
                print("AUDIO_MAN: Pygame mixer was already initialized.")
            
            current_num_channels = pygame.mixer.get_num_channels()
            if current_num_channels < num_audio_channels:
                 pygame.mixer.set_num_channels(num_audio_channels)
            
            print(f"AUDIO_MAN: Pygame mixer ready. Num channels: {pygame.mixer.get_num_channels()}.")

        except pygame.error as e:
            print(f"AUDIO_MAN: FATAL Error initializing pygame.mixer: {e}")
            return 

        self.load_sounds()

        if pygame.mixer.get_init():
            total_channels = pygame.mixer.get_num_channels()
            if total_channels >= 4:
                self.engine_channel1 = pygame.mixer.Channel(0)
                self.engine_channel2 = pygame.mixer.Channel(1)
                self.sfx_channel = pygame.mixer.Channel(2)
                self.burst_pop_channel = pygame.mixer.Channel(3)
                self.pop_channel = self.burst_pop_channel

                print(f"AUDIO_MAN: Channels: Eng1({self.engine_channel1}), Eng2({self.engine_channel2}), "
                      f"SFX({self.sfx_channel}), Burst/Pop({self.burst_pop_channel})")
                
                self.active_engine_channel = self.engine_channel1
                self.inactive_engine_channel = self.engine_channel2
            else:
                print(f"AUDIO_MAN: WARNING - Not enough audio channels available ({total_channels}). Need at least 4.")
                if total_channels >=2 :
                    self.engine_channel1 = pygame.mixer.Channel(0)
                    self.engine_channel2 = pygame.mixer.Channel(1)
                    self.active_engine_channel = self.engine_channel1
                    self.inactive_engine_channel = self.engine_channel2
                    print("AUDIO_MAN: Assigned only engine channels due to limited total channels.")
        else:
            print("AUDIO_MAN: Mixer not initialized after init attempt. Audio will be disabled.")

    def load_sounds(self):
        if not pygame.mixer.get_init():
             print("AUDIO_MAN (LoadSounds): Mixer not available.")
             return
        print("AUDIO_MAN: Starting sound loading...")
        for key, path in self.sound_files_config.items():
            if os.path.exists(path):
                try:
                    sound_obj = pygame.mixer.Sound(path)
                    if sound_obj.get_length() > 0:
                        self.sounds[key] = sound_obj
                    else:
                        print(f"AUDIO_MAN: WARNING - Sound loaded but has ZERO LENGTH: {key} from {path}")
                        self.sounds[key] = None
                except pygame.error as e:
                    print(f"AUDIO_MAN: Error loading sound {key} from {path}: {e}")
                    self.sounds[key] = None 
            else:
                print(f"AUDIO_MAN: Sound file NOT FOUND: {path} for key: {key}")
                self.sounds[key] = None
        for key, sound in self.sounds.items(): # To confirm what was loaded
            if sound:
                print(f"AUDIO_MAN: Confirmed Loaded: {key} (len: {sound.get_length():.2f}s)")
            else:
                print(f"AUDIO_MAN: Confirmed Not Loaded: {key}")
        print("AUDIO_MAN: Sound loading complete.")


    def get_sound(self, key):
        if key is None: return None
        return self.sounds.get(key)

    def play_sfx(self, key, volume_multiplier=1.0, loops=0, on_channel=None):
        if not pygame.mixer.get_init() : 
            return
        channel_to_use = on_channel or self.sfx_channel 
        if not channel_to_use:
            print(f"AUDIO_MAN (PlaySFX): No valid channel for SFX '{key}'.")
            return

        sound = self.get_sound(key)
        if sound:
            sound.set_volume(self.sfx_volume_config * volume_multiplier)
            channel_to_use.play(sound, loops=loops)
            print(f"AUDIO_MAN: ---> SFX PLAYING: '{key}' on {channel_to_use} (Sound: {sound})")
        else:
            print(f"AUDIO_MAN (PlaySFX): Sound '{key}' not available to play.")

    def play_accel_burst(self):
        if not pygame.mixer.get_init() or not self.burst_pop_channel: return
        if not self.enable_accel_burst_config: return
        current_time_ms = time.time() * 1000
        if current_time_ms - self.last_accel_burst_time > self.accel_burst_cooldown_ms_config:
            sound = self.get_sound("accel_burst")
            if sound and not self.burst_pop_channel.get_busy():
                sound.set_volume(self.sfx_volume_config * 0.9) 
                self.burst_pop_channel.play(sound)
                self.last_accel_burst_time = current_time_ms

    def play_decel_pop(self):
        if not pygame.mixer.get_init() or not self.pop_channel: return
        if not self.enable_decel_pops_config: return
        current_time_ms = time.time() * 1000
        if current_time_ms - self.last_pop_time > self.decel_pop_cooldown_ms_config:
            sound = self.get_sound("decel_pop")
            if sound and not self.pop_channel.get_busy():
                sound.set_volume(self.sfx_volume_config * 0.7)
                self.pop_channel.play(sound)
                self.last_pop_time = current_time_ms

    def update_engine_sound(self, target_sound_key):
        if not pygame.mixer.get_init() or not self.active_engine_channel or not self.inactive_engine_channel:
            return
        
        sound_to_play_obj = self.get_sound(target_sound_key)
        if not sound_to_play_obj:
            return

        if self.is_crossfading and self.crossfade_to_sound_key == target_sound_key:
            return

        if self.is_crossfading and self.crossfade_to_sound_key != target_sound_key:
            print(f"AUDIO_MAN: XFADE INTERRUPT: Current fade to '{self.crossfade_to_sound_key}' interrupted by new target '{target_sound_key}'.")
            print(f"AUDIO_MAN: XFADE INTERRUPT: Base for new fade will be '{self.current_loop_sound_key}'.")
            self.active_engine_channel.stop() 
            self.inactive_engine_channel.stop()
            self.is_crossfading = False 
            self._start_crossfade(target_sound_key) 
            return

        if target_sound_key == self.current_loop_sound_key and not self.is_crossfading:
            if not self.active_engine_channel.get_busy() or self.active_engine_channel.get_sound() != sound_to_play_obj:
                sound_to_play_obj.set_volume(self.main_engine_volume_config)
                self.active_engine_channel.play(sound_to_play_obj, loops=-1)
            return

        if self.current_loop_sound_key is None and not self.is_crossfading:
            print(f"AUDIO_MAN: Playing initial loop '{target_sound_key}' (Sound: {sound_to_play_obj}) on AC: {self.active_engine_channel}")
            sound_to_play_obj.set_volume(self.main_engine_volume_config) # Set volume on sound obj, though channel vol overrides
            self.active_engine_channel.set_volume(self.main_engine_volume_config) # Set channel volume
            self.active_engine_channel.play(sound_to_play_obj, loops=-1)
            self.current_loop_sound_key = target_sound_key
            return

        if target_sound_key != self.current_loop_sound_key and not self.is_crossfading:
            self._start_crossfade(target_sound_key)
            return

    def _start_crossfade(self, new_sound_key):
        if not pygame.mixer.get_init() or not self.active_engine_channel or not self.inactive_engine_channel : return
        
        from_sound_key_for_fade = self.current_loop_sound_key 
        new_sound_obj = self.get_sound(new_sound_key)

        if not new_sound_obj:
            print(f"AUDIO_MAN (XF-Start): Cannot crossfade, new sound '{new_sound_key}' (Obj: {new_sound_obj}) not loaded.")
            return 
        if from_sound_key_for_fade == new_sound_key: return

        print(f"AUDIO_MAN: XFADE Start: FROM '{from_sound_key_for_fade}' TO '{new_sound_key}'.")
        print(f"AUDIO_MAN: XFADE Start: Current Active Ch: {self.active_engine_channel}, Inactive Ch: {self.inactive_engine_channel}")

        self.is_crossfading = True
        self.crossfade_start_time = time.time() * 1000
        self.crossfade_from_sound_key = from_sound_key_for_fade 
        self.crossfade_to_sound_key = new_sound_key
        self.xfade_log_counter = 0

        previous_active_channel = self.active_engine_channel
        self.active_engine_channel = self.inactive_engine_channel # This will play the new sound
        self.inactive_engine_channel = previous_active_channel    # This has the old sound
        
        print(f"AUDIO_MAN: XFADE Start: Swapped. New Active Ch (for '{new_sound_key}'): {self.active_engine_channel}, New Inactive Ch (for '{from_sound_key_for_fade}'): {self.inactive_engine_channel}")

        # --- Modification Start ---
        # Explicitly stop the channel that is about to become the new active channel
        print(f"AUDIO_MAN: XFADE Start: Attempting to stop New Active Ch: {self.active_engine_channel} before playing new sound.")
        self.active_engine_channel.stop() 
        print(f"AUDIO_MAN: XFADE Start: New Active Ch: {self.active_engine_channel} stopped. Busy: {self.active_engine_channel.get_busy()}, Sound: {self.active_engine_channel.get_sound()}")
        # --- Modification End ---

        # Play new sound on the new active channel (starts silent, fades in)
        # new_sound_obj.set_volume(0) # Sound object's base volume, channel volume is separate
        self.active_engine_channel.set_volume(0) # Set channel volume to 0 for fade in
        self.active_engine_channel.play(new_sound_obj, loops=-1)
        
        # Add immediate checks
        new_active_sound_on_ch = self.active_engine_channel.get_sound()
        new_active_busy_status = self.active_engine_channel.get_busy()
        new_active_volume = self.active_engine_channel.get_volume()
        print(f"AUDIO_MAN: XFADE Start: Played '{new_sound_key}' (Obj: {new_sound_obj}) on New Active Ch: {self.active_engine_channel}. ChVol: {new_active_volume:.2f}. Busy: {new_active_busy_status}. Sound on Ch: {new_active_sound_on_ch}")

        old_sound_obj = self.get_sound(self.crossfade_from_sound_key)
        if old_sound_obj:
            current_inactive_sound_on_ch = self.inactive_engine_channel.get_sound()
            current_inactive_busy_status = self.inactive_engine_channel.get_busy()
            if current_inactive_sound_on_ch != old_sound_obj or not current_inactive_busy_status:
                print(f"AUDIO_MAN: XFADE Start INFO: Old sound '{self.crossfade_from_sound_key}' (Obj: {old_sound_obj}) needs to be (re)started on New Inactive Ch {self.inactive_engine_channel} (Currently: {current_inactive_sound_on_ch}, Busy: {current_inactive_busy_status}). Restarting for fade-out.")
                self.inactive_engine_channel.play(old_sound_obj, loops=-1) # Ensure it's playing to fade out
            
            self.inactive_engine_channel.set_volume(self.main_engine_volume_config) # Start fade from full
            final_inactive_sound_on_ch = self.inactive_engine_channel.get_sound()
            final_inactive_busy_status = self.inactive_engine_channel.get_busy()
            final_inactive_volume = self.inactive_engine_channel.get_volume()
            print(f"AUDIO_MAN: XFADE Start: Ensured '{self.crossfade_from_sound_key}' (Obj: {old_sound_obj}) is on New Inactive Ch {self.inactive_engine_channel}. ChVol: {final_inactive_volume:.2f}. Busy: {final_inactive_busy_status}. Sound on Ch: {final_inactive_sound_on_ch}")
        elif self.inactive_engine_channel.get_busy():
            print(f"AUDIO_MAN: XFADE Start: No 'from_sound_key', but New Inactive Ch {self.inactive_engine_channel} was busy. Setting volume for fade out.")
            self.inactive_engine_channel.set_volume(self.main_engine_volume_config)


    def _handle_crossfade(self):
        if not self.is_crossfading or not pygame.mixer.get_init() or not self.active_engine_channel or not self.inactive_engine_channel:
            return

        elapsed_time_ms = (time.time() * 1000) - self.crossfade_start_time
        progress = min(elapsed_time_ms / self.crossfade_duration_ms_config, 1.0)

        vol_to = self.main_engine_volume_config * progress
        vol_from = self.main_engine_volume_config * (1.0 - progress)
        
        sound_to_obj = self.get_sound(self.crossfade_to_sound_key)
        sound_from_obj = self.get_sound(self.crossfade_from_sound_key)

        log_this_time = False
        if self.xfade_log_counter % 30 == 0: 
            log_this_time = True

        if sound_to_obj :
            # Ensure correct sound is playing on the active channel before setting volume
            if self.active_engine_channel.get_sound() != sound_to_obj:
                if log_this_time: print(f"AUDIO_MAN: XFADE Handle WARNING: Active Ch {self.active_engine_channel} sound mismatch! Expected '{self.crossfade_to_sound_key}' (Obj:{sound_to_obj}), Got: {self.active_engine_channel.get_sound()}. Forcing play.")
                self.active_engine_channel.play(sound_to_obj, loops=-1) 
            if self.active_engine_channel.get_busy(): self.active_engine_channel.set_volume(vol_to)
            if log_this_time: print(f"AUDIO_MAN: XFADE Handle: ActiveCh ({self.active_engine_channel}) '{self.crossfade_to_sound_key}' Vol set to {vol_to:.2f}. CurrentChVol: {self.active_engine_channel.get_volume():.2f}")
        
        if sound_from_obj:
            if self.inactive_engine_channel.get_sound() != sound_from_obj:
                if log_this_time: print(f"AUDIO_MAN: XFADE Handle WARNING: Inactive Ch {self.inactive_engine_channel} sound mismatch! Expected '{self.crossfade_from_sound_key}' (Obj:{sound_from_obj}), Got: {self.inactive_engine_channel.get_sound()}. Forcing play for fade.")
                self.inactive_engine_channel.play(sound_from_obj, loops=-1)
            if self.inactive_engine_channel.get_busy(): self.inactive_engine_channel.set_volume(vol_from)
            if log_this_time: print(f"AUDIO_MAN: XFADE Handle: InactiveCh ({self.inactive_engine_channel}) '{self.crossfade_from_sound_key}' Vol set to {vol_from:.2f}. CurrentChVol: {self.inactive_engine_channel.get_volume():.2f}")
        elif self.inactive_engine_channel.get_busy(): 
            self.inactive_engine_channel.set_volume(vol_from)
            if log_this_time: print(f"AUDIO_MAN: XFADE Handle: InactiveCh ({self.inactive_engine_channel}) (no specific from_sound) Vol set to {vol_from:.2f}. CurrentChVol: {self.inactive_engine_channel.get_volume():.2f}")

        self.xfade_log_counter +=1

        if progress >= 1.0:
            print(f"AUDIO_MAN: XFADE Complete: Target was '{self.crossfade_to_sound_key}'. From was '{self.crossfade_from_sound_key}'")
            
            if sound_from_obj and self.inactive_engine_channel.get_busy():
                if self.inactive_engine_channel.get_sound() == sound_from_obj:
                    self.inactive_engine_channel.stop()
                    print(f"AUDIO_MAN: XFADE Complete: Stopped old sound '{self.crossfade_from_sound_key}' (Obj:{sound_from_obj}) on InactiveCh {self.inactive_engine_channel}.")
                else:
                    print(f"AUDIO_MAN: XFADE Complete WARNING: Did not stop sound on InactiveCh {self.inactive_engine_channel}, it wasn't '{self.crossfade_from_sound_key}'. Sound was: {self.inactive_engine_channel.get_sound()}")
            elif not sound_from_obj and self.inactive_engine_channel.get_busy():
                self.inactive_engine_channel.stop()
                print(f"AUDIO_MAN: XFADE Complete: Stopped busy InactiveCh {self.inactive_engine_channel} (no specific from_sound).")

            self.current_loop_sound_key = self.crossfade_to_sound_key
            self.is_crossfading = False
            
            if sound_to_obj:
                # Ensure the new sound is playing and at full volume
                if self.active_engine_channel.get_sound() != sound_to_obj or not self.active_engine_channel.get_busy():
                    print(f"AUDIO_MAN: XFADE Complete WARNING: ActiveCh {self.active_engine_channel} had wrong sound {self.active_engine_channel.get_sound()} or not busy. Re-playing '{self.current_loop_sound_key}'.")
                    self.active_engine_channel.play(sound_to_obj, loops=-1)
                
                self.active_engine_channel.set_volume(self.main_engine_volume_config)
                print(f"AUDIO_MAN: XFADE Complete: Set ActiveCh {self.active_engine_channel} ('{self.current_loop_sound_key}') to full volume {self.main_engine_volume_config}. CurrentChVol: {self.active_engine_channel.get_volume():.2f}")
            else:
                print(f"AUDIO_MAN: XFADE Complete WARNING: Target sound obj '{self.current_loop_sound_key}' is None. ActiveCh {self.active_engine_channel} not set.")

    def stop_engine_sounds_for_shutdown(self):
        if not pygame.mixer.get_init(): return
        print("AUDIO_MAN: Stopping engine loops for shutdown process.")
        fade_time_ms = self.crossfade_duration_ms_config // 2 
        if self.engine_channel1 and self.engine_channel1.get_busy():
            self.engine_channel1.fadeout(fade_time_ms) 
        if self.engine_channel2 and self.engine_channel2.get_busy():
            self.engine_channel2.fadeout(fade_time_ms) 
        self.current_loop_sound_key = None 
        self.is_crossfading = False 

    def stop_all_engine_sounds(self): 
        if not pygame.mixer.get_init(): return
        if self.engine_channel1 and self.engine_channel1.get_busy(): self.engine_channel1.stop()
        if self.engine_channel2 and self.engine_channel2.get_busy(): self.engine_channel2.stop()
        self.current_loop_sound_key = None
        self.is_crossfading = False

    def stop_all_sounds(self): 
        if not pygame.mixer.get_init(): return
        pygame.mixer.stop() 
        self.current_loop_sound_key = None
        self.is_crossfading = False

    def quit(self):
        if pygame.mixer.get_init():
            pygame.mixer.quit()

    def update(self):
        if not pygame.mixer.get_init(): return
        if self.is_crossfading:
            self._handle_crossfade()
    
    def is_sfx_channel_busy(self):
        if not pygame.mixer.get_init() or not self.sfx_channel: return False
        return self.sfx_channel.get_busy()

    def is_any_engine_sound_playing(self):
        if not pygame.mixer.get_init(): return False
        c1_busy = self.engine_channel1 and self.engine_channel1.get_busy()
        c2_busy = self.engine_channel2 and self.engine_channel2.get_busy()
        return c1_busy or c2_busy or self.is_crossfading