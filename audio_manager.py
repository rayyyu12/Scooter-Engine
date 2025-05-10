# audio_manager.py
import pygame
import time
import os
import config # Import config to use its values directly

class AudioManager:
    def __init__(self, mixer_frequency, mixer_size, mixer_channels, mixer_buffer,
                 num_audio_channels, sound_files, sfx_volume, main_engine_volume,
                 crossfade_duration_ms, accel_burst_cooldown_ms, decel_pop_cooldown_ms,
                 enable_accel_burst, enable_decel_pops): # These params from main are now less critical if using global config
        
        self.sounds = {}
        self.engine_channel1 = None
        self.engine_channel2 = None
        self.sfx_channel = None
        self.burst_pop_channel = None # Used for both accel burst and decel pop
        self.pop_channel = None # Alias for burst_pop_channel

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

        # Using global config values now
        self.sound_files_config = config.SOUND_FILES
        self.sfx_volume_config = config.SFX_VOLUME
        self.main_engine_volume_config = config.MAIN_ENGINE_VOLUME
        self.crossfade_duration_ms_config = config.CROSSFADE_DURATION_MS
        self.accel_burst_cooldown_ms_config = config.ACCEL_BURST_COOLDOWN_MS
        self.decel_pop_cooldown_ms_config = config.DECEL_POP_COOLDOWN_MS
        self.enable_accel_burst_config = config.ENABLE_ACCEL_BURST
        self.enable_decel_pops_config = config.ENABLE_DECEL_POPS


        try:
            if not pygame.mixer.get_init():
                 pygame.mixer.init(
                    frequency=config.MIXER_FREQUENCY,
                    size=config.MIXER_SIZE,
                    channels=config.MIXER_CHANNELS,
                    buffer=config.MIXER_BUFFER_SIZE
                )
            else:
                print("AUDIO_MAN: Pygame mixer was already initialized.")
            
            current_num_channels = pygame.mixer.get_num_channels()
            if current_num_channels < config.NUM_AUDIO_CHANNELS:
                 pygame.mixer.set_num_channels(config.NUM_AUDIO_CHANNELS)
            print(f"AUDIO_MAN: Pygame mixer ready. Num channels: {pygame.mixer.get_num_channels()}.")

        except pygame.error as e:
            print(f"AUDIO_MAN: FATAL Error initializing pygame.mixer: {e}")
            return 

        self.load_sounds() # Uses self.sound_files_config (which is config.SOUND_FILES)

        if pygame.mixer.get_init():
            total_channels = pygame.mixer.get_num_channels()
            if total_channels >= 4: # Need at least 4 for dedicated roles
                self.engine_channel1 = pygame.mixer.Channel(0)
                self.engine_channel2 = pygame.mixer.Channel(1)
                self.sfx_channel = pygame.mixer.Channel(2)      # For starter, shutdown
                self.burst_pop_channel = pygame.mixer.Channel(3) # For accel_burst, decel_pop
                self.pop_channel = self.burst_pop_channel # Alias

                print(f"AUDIO_MAN: Channels: Eng1({self.engine_channel1}), Eng2({self.engine_channel2}), "
                      f"SFX({self.sfx_channel}), Burst/Pop({self.burst_pop_channel})")
                
                self.active_engine_channel = self.engine_channel1
                self.inactive_engine_channel = self.engine_channel2
            # ... (rest of channel assignment logic)
        # ... (rest of __init__)


    def load_sounds(self): # Uses self.sound_files_config
        if not pygame.mixer.get_init(): return
        print("AUDIO_MAN: Starting sound loading...")
        for key, path in self.sound_files_config.items(): #Iterate over self.sound_files_config
            if os.path.exists(path):
                try:
                    sound_obj = pygame.mixer.Sound(path)
                    if sound_obj.get_length() > 0: self.sounds[key] = sound_obj
                    else:
                        print(f"AUDIO_MAN: WARNING - ZERO LENGTH: {key} from {path}")
                        self.sounds[key] = None
                except pygame.error as e:
                    print(f"AUDIO_MAN: Error loading sound {key} from {path}: {e}")
                    self.sounds[key] = None 
            else:
                print(f"AUDIO_MAN: Sound file NOT FOUND: {path} for key: {key}")
                self.sounds[key] = None
        for key, sound in self.sounds.items():
            if sound: print(f"AUDIO_MAN: Confirmed Loaded: {key} (len: {sound.get_length():.2f}s)")
            else: print(f"AUDIO_MAN: Confirmed Not Loaded: {key}")
        print("AUDIO_MAN: Sound loading complete.")

    def get_sound(self, key):
        if key is None: return None
        return self.sounds.get(key)

    def play_sfx(self, key, volume_multiplier=1.0, loops=0, on_channel=None):
        if not pygame.mixer.get_init() : return False
        channel_to_use = on_channel or self.sfx_channel 
        if not channel_to_use:
            # print(f"AUDIO_MAN (PlaySFX): No valid channel for SFX '{key}'.")
            return False

        sound = self.get_sound(key)
        if sound:
            # Use the global SFX_VOLUME from config and the passed multiplier
            sound.set_volume(config.SFX_VOLUME * volume_multiplier)
            channel_to_use.play(sound, loops=loops)
            # print(f"AUDIO_MAN: ---> SFX PLAYING: '{key}' on {channel_to_use}")
            return True
        return False

    def play_accel_burst(self):
        if not pygame.mixer.get_init() or not self.burst_pop_channel: return False
        if not self.enable_accel_burst_config: return False

        current_time_ms = time.time() * 1000
        if current_time_ms - self.last_accel_burst_time > self.accel_burst_cooldown_ms_config:
            sound = self.get_sound("accel_burst")
            if sound:
                if not self.burst_pop_channel.get_busy(): # Only play if channel is free
                    vol = config.SFX_VOLUME * config.ACCEL_BURST_SFX_VOLUME_MULTIPLIER
                    sound.set_volume(min(1.0, vol)) # Cap at 1.0
                    self.burst_pop_channel.play(sound)
                    self.last_accel_burst_time = current_time_ms
                    print(f"AUDIO_MAN: ---> ACCEL BURST PLAYING (Vol: {vol:.2f})")
                    return True
                # else: print("AUDIO_MAN: Accel burst channel busy.")
            # else: print(f"AUDIO_MAN: Accel burst sound not loaded.")
        return False

    def play_decel_pop(self):
        if not pygame.mixer.get_init() or not self.pop_channel: return False
        if not self.enable_decel_pops_config: return False

        current_time_ms = time.time() * 1000
        if current_time_ms - self.last_pop_time > self.decel_pop_cooldown_ms_config:
            sound = self.get_sound("decel_pop")
            if sound:
                if not self.pop_channel.get_busy(): # Only play if channel is free
                    vol = config.SFX_VOLUME * config.DECEL_POP_SFX_VOLUME_MULTIPLIER
                    sound.set_volume(min(1.0, vol)) # Cap at 1.0
                    self.pop_channel.play(sound) # pop_channel is an alias for burst_pop_channel
                    self.last_pop_time = current_time_ms
                    print(f"AUDIO_MAN: ---> DECEL POP PLAYING (Vol: {vol:.2f})")
                    return True
                # else: print("AUDIO_MAN: Decel pop channel busy.")
            # else: print(f"AUDIO_MAN: Decel pop sound not loaded.")
        return False

    # ... (update_engine_sound, _start_crossfade, _handle_crossfade, and other methods remain the same as the previous working version)
    # Ensure that the __init__ method in AudioManager correctly uses the global config for its settings
    # if the parameters passed to it are just for legacy reasons. My change above makes it use global config.

    def update_engine_sound(self, target_sound_key):
        if not pygame.mixer.get_init() or not self.active_engine_channel or not self.inactive_engine_channel:
            return
        sound_to_play_obj = self.get_sound(target_sound_key)
        if not sound_to_play_obj: return

        if self.is_crossfading and self.crossfade_to_sound_key == target_sound_key: return
        if self.is_crossfading and self.crossfade_to_sound_key != target_sound_key:
            self.active_engine_channel.stop(); self.inactive_engine_channel.stop()
            self.is_crossfading = False 
            self._start_crossfade(target_sound_key); return

        if target_sound_key == self.current_loop_sound_key and not self.is_crossfading:
            if not self.active_engine_channel.get_busy() or self.active_engine_channel.get_sound() != sound_to_play_obj:
                self.active_engine_channel.set_volume(self.main_engine_volume_config)
                self.active_engine_channel.play(sound_to_play_obj, loops=-1)
            return

        if self.current_loop_sound_key is None and not self.is_crossfading:
            self.active_engine_channel.set_volume(self.main_engine_volume_config)
            self.active_engine_channel.play(sound_to_play_obj, loops=-1)
            self.current_loop_sound_key = target_sound_key; return

        if target_sound_key != self.current_loop_sound_key and not self.is_crossfading:
            self._start_crossfade(target_sound_key); return

    def _start_crossfade(self, new_sound_key):
        if not pygame.mixer.get_init() or not self.active_engine_channel or not self.inactive_engine_channel : return
        from_sound_key_for_fade = self.current_loop_sound_key 
        new_sound_obj = self.get_sound(new_sound_key)
        if not new_sound_obj or from_sound_key_for_fade == new_sound_key: return

        self.is_crossfading = True; self.crossfade_start_time = time.time() * 1000
        self.crossfade_from_sound_key = from_sound_key_for_fade 
        self.crossfade_to_sound_key = new_sound_key; self.xfade_log_counter = 0
        previous_active_channel = self.active_engine_channel
        self.active_engine_channel = self.inactive_engine_channel 
        self.inactive_engine_channel = previous_active_channel    
        self.active_engine_channel.stop() 
        self.active_engine_channel.set_volume(0)
        self.active_engine_channel.play(new_sound_obj, loops=-1)
        old_sound_obj = self.get_sound(self.crossfade_from_sound_key)
        if old_sound_obj:
            current_inactive_sound_on_ch = self.inactive_engine_channel.get_sound(); current_inactive_busy_status = self.inactive_engine_channel.get_busy()
            if current_inactive_sound_on_ch != old_sound_obj or not current_inactive_busy_status:
                self.inactive_engine_channel.play(old_sound_obj, loops=-1)
            self.inactive_engine_channel.set_volume(self.main_engine_volume_config)
        elif self.inactive_engine_channel.get_busy():
            self.inactive_engine_channel.set_volume(self.main_engine_volume_config)

    def _handle_crossfade(self):
        if not self.is_crossfading or not pygame.mixer.get_init() or not self.active_engine_channel or not self.inactive_engine_channel: return
        elapsed_time_ms = (time.time() * 1000) - self.crossfade_start_time
        progress = min(elapsed_time_ms / self.crossfade_duration_ms_config, 1.0)
        vol_to = self.main_engine_volume_config * progress; vol_from = self.main_engine_volume_config * (1.0 - progress)
        sound_to_obj = self.get_sound(self.crossfade_to_sound_key); sound_from_obj = self.get_sound(self.crossfade_from_sound_key)
        log_this_time = (self.xfade_log_counter % 120 == 0) # Even less verbose

        if sound_to_obj :
            if self.active_engine_channel.get_sound() != sound_to_obj:
                if log_this_time: print(f"AM (XF_H WARN): AC {self.active_engine_channel} mismatch! Exp '{self.crossfade_to_sound_key}', Got: {self.active_engine_channel.get_sound()}. Force play.")
                self.active_engine_channel.play(sound_to_obj, loops=-1) 
            if self.active_engine_channel.get_busy(): self.active_engine_channel.set_volume(vol_to)
        
        if sound_from_obj:
            if self.inactive_engine_channel.get_sound() != sound_from_obj:
                if log_this_time: print(f"AM (XF_H WARN): IC {self.inactive_engine_channel} mismatch! Exp '{self.crossfade_from_sound_key}', Got: {self.inactive_engine_channel.get_sound()}. Force play.")
                self.inactive_engine_channel.play(sound_from_obj, loops=-1)
            if self.inactive_engine_channel.get_busy(): self.inactive_engine_channel.set_volume(vol_from)
        elif self.inactive_engine_channel.get_busy(): self.inactive_engine_channel.set_volume(vol_from)
        self.xfade_log_counter +=1

        if progress >= 1.0:
            if sound_from_obj and self.inactive_engine_channel.get_busy() and self.inactive_engine_channel.get_sound() == sound_from_obj:
                self.inactive_engine_channel.stop()
            elif not sound_from_obj and self.inactive_engine_channel.get_busy(): self.inactive_engine_channel.stop()
            self.current_loop_sound_key = self.crossfade_to_sound_key; self.is_crossfading = False
            if sound_to_obj:
                if self.active_engine_channel.get_sound() != sound_to_obj or not self.active_engine_channel.get_busy():
                    self.active_engine_channel.play(sound_to_obj, loops=-1)
                self.active_engine_channel.set_volume(self.main_engine_volume_config)

    def stop_engine_sounds_for_shutdown(self): # Uses self.crossfade_duration_ms_config
        if not pygame.mixer.get_init(): return
        fade_time_ms = self.crossfade_duration_ms_config // 2 
        if self.engine_channel1 and self.engine_channel1.get_busy(): self.engine_channel1.fadeout(fade_time_ms) 
        if self.engine_channel2 and self.engine_channel2.get_busy(): self.engine_channel2.fadeout(fade_time_ms) 
        self.current_loop_sound_key = None; self.is_crossfading = False 

    def stop_all_engine_sounds(self): 
        if not pygame.mixer.get_init(): return
        if self.engine_channel1 and self.engine_channel1.get_busy(): self.engine_channel1.stop()
        if self.engine_channel2 and self.engine_channel2.get_busy(): self.engine_channel2.stop()
        self.current_loop_sound_key = None; self.is_crossfading = False

    def stop_all_sounds(self): 
        if not pygame.mixer.get_init(): return
        pygame.mixer.stop(); self.current_loop_sound_key = None; self.is_crossfading = False

    def quit(self):
        if pygame.mixer.get_init(): pygame.mixer.quit()

    def update(self):
        if not pygame.mixer.get_init(): return
        if self.is_crossfading: self._handle_crossfade()
    
    def is_sfx_channel_busy(self):
        if not pygame.mixer.get_init() or not self.sfx_channel: return False
        return self.sfx_channel.get_busy()

    def is_any_engine_sound_playing(self):
        if not pygame.mixer.get_init(): return False
        c1 = self.engine_channel1 and self.engine_channel1.get_busy()
        c2 = self.engine_channel2 and self.engine_channel2.get_busy()
        return c1 or c2 or self.is_crossfading