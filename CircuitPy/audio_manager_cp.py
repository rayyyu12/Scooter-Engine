# audio_manager_cp.py
import audiocore
import audiomixer
import time
# import os # Not strictly needed if paths are directly from config
import config_cp as config 

class AudioManagerCP:
    def __init__(self, audio_output):
        self.audio_out = audio_output
        self.mixer = audiomixer.Mixer(
            voice_count=config.NUM_MIXER_VOICES,
            sample_rate=config.AUDIO_SAMPLE_RATE,
            channel_count=1, 
            bits_per_sample=16,
            samples_signed=True
        )
        self.audio_out.play(self.mixer)

        self.sounds = {} 

        self.engine_voice_idx1 = config.ENGINE_LOOP_VOICE_1
        self.engine_voice_idx2 = config.ENGINE_LOOP_VOICE_2
        self.sfx_startshut_voice_idx = config.SFX_STARTSHUT_VOICE
        self.sfx_accel_voice_idx = config.SFX_ACCEL_VOICE
        self.sfx_decel_voice_idx = config.SFX_DECEL_VOICE

        self.active_engine_voice_idx = self.engine_voice_idx1
        self.inactive_engine_voice_idx = self.engine_voice_idx2

        self.current_loop_sound_key = None
        self.is_crossfading = False
        self.crossfade_start_time = 0
        self.crossfade_from_sound_key = None
        self.crossfade_to_sound_key = None

        self.last_pop_time = 0 # Uses time.monotonic()
        self.last_accel_burst_time = 0 # Uses time.monotonic()
        
        self.load_sounds()
        print("AUDIO_MAN_CP: AudioManagerCP initialized.")

    def load_sounds(self):
        print("AUDIO_MAN_CP: Starting sound loading...")
        for key, path in config.SOUND_FILES.items():
            try:
                wave_file = audiocore.WaveFile(open(path, "rb"))
                self.sounds[key] = wave_file
                # print(f"AUDIO_MAN_CP: Loaded: {key} (Rate: {wave_file.sample_rate}, Ch: {wave_file.channel_count})")
                if wave_file.sample_rate != config.AUDIO_SAMPLE_RATE:
                    print(f"AUDIO_MAN_CP: WARNING - Rate mismatch for {key}! Mixer: {config.AUDIO_SAMPLE_RATE}, File: {wave_file.sample_rate}.")
                if wave_file.channel_count > 1 and self.mixer.channel_count == 1:
                     print(f"AUDIO_MAN_CP: WARNING - {key} is stereo but mixer is mono.")
            except OSError as e:
                print(f"AUDIO_MAN_CP: Error loading sound {key} from {path}: {e}")
            except Exception as e:
                print(f"AUDIO_MAN_CP: Generic error loading {key}: {e}")
        print("AUDIO_MAN_CP: Sound loading complete.")

    def get_sound(self, key):
        if key is None: return None
        return self.sounds.get(key)

    def play_sfx(self, key, voice_idx, volume_multiplier=1.0, loop=False):
        sound = self.get_sound(key)
        if sound:
            if self.mixer.voice[voice_idx].playing and not loop: # Allow interrupting if it's a loop (though SFX rarely loop)
                # print(f"AUDIO_MAN_CP: SFX Voice {voice_idx} busy with non-loop, '{key}' not played.")
                return False 

            # print(f"AUDIO_MAN_CP: ---> SFX PLAYING: '{key}' on voice {voice_idx}")
            self.mixer.voice[voice_idx].level = config.SFX_VOLUME * volume_multiplier
            self.mixer.play(sound, voice=voice_idx, loop=loop)
            return True
        # print(f"AUDIO_MAN_CP: SFX sound '{key}' not found.")
        return False

    def play_accel_burst(self):
        if not config.ENABLE_ACCEL_BURST: return False
        current_time = time.monotonic()
        # Use ACCEL_BURST_COOLDOWN_S from config
        if current_time - self.last_accel_burst_time > config.ACCEL_BURST_COOLDOWN_S:
            vol = config.SFX_VOLUME * config.ACCEL_BURST_SFX_VOLUME_MULTIPLIER
            if self.play_sfx("accel_burst", self.sfx_accel_voice_idx, volume_multiplier=min(1.0, vol)):
                self.last_accel_burst_time = current_time
                return True
        return False

    def play_decel_pop(self):
        if not config.ENABLE_DECEL_POPS: return False
        current_time = time.monotonic()
        # Use DECEL_POP_COOLDOWN_S from config
        if current_time - self.last_pop_time > config.DECEL_POP_COOLDOWN_S:
            vol = config.SFX_VOLUME * config.DECEL_POP_SFX_VOLUME_MULTIPLIER
            if self.play_sfx("decel_pop", self.sfx_decel_voice_idx, volume_multiplier=min(1.0, vol)):
                self.last_pop_time = current_time
                return True
        return False

    def update_engine_sound(self, target_sound_key):
        sound_to_play_obj = self.get_sound(target_sound_key)
        if not sound_to_play_obj:
            return

        if self.is_crossfading and self.crossfade_to_sound_key == target_sound_key:
            return

        if self.is_crossfading and self.crossfade_to_sound_key != target_sound_key:
            self.mixer.stop(voice=self.active_engine_voice_idx)
            self.mixer.stop(voice=self.inactive_engine_voice_idx)
            self.is_crossfading = False
            self._start_crossfade(target_sound_key)
            return

        if target_sound_key == self.current_loop_sound_key and not self.is_crossfading:
            if not self.mixer.voice[self.active_engine_voice_idx].playing or \
               self.mixer.voice[self.active_engine_voice_idx].sample != sound_to_play_obj:
                self.mixer.voice[self.active_engine_voice_idx].level = config.MAIN_ENGINE_VOLUME
                self.mixer.play(sound_to_play_obj, voice=self.active_engine_voice_idx, loop=True)
            return

        if (target_sound_key != self.current_loop_sound_key or self.current_loop_sound_key is None) and not self.is_crossfading:
            self._start_crossfade(target_sound_key)
            return

    def _start_crossfade(self, new_sound_key):
        from_sound_key_for_fade = self.current_loop_sound_key
        new_sound_obj = self.get_sound(new_sound_key)

        if not new_sound_obj: return
        if from_sound_key_for_fade == new_sound_key and self.mixer.voice[self.active_engine_voice_idx].playing:
            return 

        self.is_crossfading = True
        self.crossfade_start_time = time.monotonic()
        self.crossfade_from_sound_key = from_sound_key_for_fade
        self.crossfade_to_sound_key = new_sound_key

        previous_active_voice_idx = self.active_engine_voice_idx
        self.active_engine_voice_idx = self.inactive_engine_voice_idx
        self.inactive_engine_voice_idx = previous_active_voice_idx

        self.mixer.play(new_sound_obj, voice=self.active_engine_voice_idx, loop=True)
        self.mixer.voice[self.active_engine_voice_idx].level = 0.0

        old_sound_obj = self.get_sound(self.crossfade_from_sound_key)
        if old_sound_obj:
            if not self.mixer.voice[self.inactive_engine_voice_idx].playing or \
               self.mixer.voice[self.inactive_engine_voice_idx].sample != old_sound_obj:
                self.mixer.play(old_sound_obj, voice=self.inactive_engine_voice_idx, loop=True)
            self.mixer.voice[self.inactive_engine_voice_idx].level = config.MAIN_ENGINE_VOLUME
        else: 
            self.mixer.stop(voice=self.inactive_engine_voice_idx) # Ensure inactive is stopped if no 'from' sound

    def _handle_crossfade(self):
        if not self.is_crossfading: return

        elapsed_time = time.monotonic() - self.crossfade_start_time
        progress = min(elapsed_time / config.CROSSFADE_DURATION_S, 1.0)

        vol_to = config.MAIN_ENGINE_VOLUME * progress
        vol_from = config.MAIN_ENGINE_VOLUME * (1.0 - progress)

        sound_to_obj = self.get_sound(self.crossfade_to_sound_key)
        sound_from_obj = self.get_sound(self.crossfade_from_sound_key)
        
        if sound_to_obj and self.mixer.voice[self.active_engine_voice_idx].playing:
             # Ensure the correct sample is playing on the active voice
            if self.mixer.voice[self.active_engine_voice_idx].sample != sound_to_obj:
                self.mixer.play(sound_to_obj, voice=self.active_engine_voice_idx, loop=True)
            self.mixer.voice[self.active_engine_voice_idx].level = vol_to
        
        if sound_from_obj and self.mixer.voice[self.inactive_engine_voice_idx].playing:
            if self.mixer.voice[self.inactive_engine_voice_idx].sample != sound_from_obj:
                self.mixer.play(sound_from_obj, voice=self.inactive_engine_voice_idx, loop=True)
            self.mixer.voice[self.inactive_engine_voice_idx].level = vol_from
        elif not sound_from_obj: 
             self.mixer.voice[self.inactive_engine_voice_idx].level = 0.0 # Should already be stopped or silent

        if progress >= 1.0:
            if sound_from_obj and self.mixer.voice[self.inactive_engine_voice_idx].playing:
                self.mixer.stop(voice=self.inactive_engine_voice_idx)
            elif not sound_from_obj: # Ensure it's stopped if there was no from_sound
                self.mixer.stop(voice=self.inactive_engine_voice_idx)

            self.current_loop_sound_key = self.crossfade_to_sound_key
            self.is_crossfading = False
            self.crossfade_from_sound_key = None
            # self.crossfade_to_sound_key = None # Cleared when is_crossfading is false
            
            if sound_to_obj and self.mixer.voice[self.active_engine_voice_idx].playing:
                 self.mixer.voice[self.active_engine_voice_idx].level = config.MAIN_ENGINE_VOLUME

    def stop_engine_sounds_for_shutdown(self):
        # Quick stop rather than fadeout for simplicity on CP
        if self.mixer.voice[self.engine_voice_idx1].playing:
            self.mixer.stop(voice=self.engine_voice_idx1)
        if self.mixer.voice[self.engine_voice_idx2].playing:
            self.mixer.stop(voice=self.engine_voice_idx2)
        self.current_loop_sound_key = None
        self.is_crossfading = False

    def stop_all_engine_sounds(self):
        if self.mixer.voice[self.engine_voice_idx1].playing:
            self.mixer.stop(voice=self.engine_voice_idx1)
        if self.mixer.voice[self.engine_voice_idx2].playing:
            self.mixer.stop(voice=self.engine_voice_idx2)
        self.current_loop_sound_key = None
        self.is_crossfading = False

    def stop_all_sounds(self):
        for i in range(self.mixer.voice_count): # Use mixer's voice_count
            self.mixer.stop(voice=i)
        self.current_loop_sound_key = None
        self.is_crossfading = False

    def quit(self): 
        self.stop_all_sounds()
        if self.audio_out:
            # self.audio_out.stop() # Stop playback on the output device
            self.audio_out.deinit() # Release hardware resources
        print("AUDIO_MAN_CP: Audio system deinitialized.")

    def update(self): 
        if self.is_crossfading:
            self._handle_crossfade()

    def is_sfx_starter_shutdown_busy(self):
        return self.mixer.voice[self.sfx_startshut_voice_idx].playing

    def is_any_engine_sound_playing(self, ignore_sfx=False):
        e1_playing = self.mixer.voice[self.engine_voice_idx1].playing
        e2_playing = self.mixer.voice[self.engine_voice_idx2].playing
        
        if ignore_sfx:
            return e1_playing or e2_playing or self.is_crossfading

        sfx_ss_busy = self.mixer.voice[self.sfx_startshut_voice_idx].playing
        sfx_accel_busy = self.mixer.voice[self.sfx_accel_voice_idx].playing
        sfx_decel_busy = self.mixer.voice[self.sfx_decel_voice_idx].playing
        
        return e1_playing or e2_playing or self.is_crossfading or sfx_ss_busy or sfx_accel_busy or sfx_decel_busy