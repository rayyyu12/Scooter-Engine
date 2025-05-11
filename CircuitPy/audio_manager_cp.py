# audio_manager_cp.py
import audiocore
import audiomixer
import time
import os # For os.path.exists, though less critical if paths are hardcoded
import config_cp as config # Use the CircuitPython config

class AudioManagerCP:
    def __init__(self, audio_output): # audio_output is I2SOut or PWMAudioOut
        self.audio_out = audio_output
        self.mixer = audiomixer.Mixer(
            voice_count=config.NUM_MIXER_VOICES,
            sample_rate=config.AUDIO_SAMPLE_RATE,
            channel_count=1, # Assuming mono WAVs. Change to 2 if stereo and your DAC supports it.
            bits_per_sample=16,
            samples_signed=True
        )
        self.audio_out.play(self.mixer) # Play the mixer an ETERNITY

        self.sounds = {} # To store WaveFile objects

        # Voice assignments from config
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

        self.last_pop_time = 0
        self.last_accel_burst_time = 0
        
        self.xfade_log_counter = 0 # For less spammy logging

        self.load_sounds()
        print("AUDIO_MAN_CP: AudioManagerCP initialized.")

    def load_sounds(self):
        print("AUDIO_MAN_CP: Starting sound loading...")
        for key, path in config.SOUND_FILES.items():
            try:
                # Note: os.path.exists might not be fully reliable or necessary
                # if you are sure about your SD card paths.
                # For CircuitPython, WaveFile objects are typically kept open.
                wave_file = audiocore.WaveFile(open(path, "rb"))
                self.sounds[key] = wave_file
                print(f"AUDIO_MAN_CP: Loaded: {key} (SampleRate: {wave_file.sample_rate}, Channels: {wave_file.channel_count})")
                if wave_file.sample_rate != config.AUDIO_SAMPLE_RATE:
                    print(f"AUDIO_MAN_CP: WARNING - Sample rate mismatch for {key}! Expected {config.AUDIO_SAMPLE_RATE}, got {wave_file.sample_rate}. Playback issues may occur.")
                if wave_file.channel_count > 1 and self.mixer.channel_count == 1: # Assuming mono mixer
                     print(f"AUDIO_MAN_CP: WARNING - {key} is stereo but mixer is mono. Will play left channel.")

            except OSError as e:
                print(f"AUDIO_MAN_CP: Error loading sound {key} from {path}: {e}")
            except Exception as e:
                print(f"AUDIO_MAN_CP: Generic error loading sound {key}: {e}")
        print("AUDIO_MAN_CP: Sound loading complete.")

    def get_sound(self, key):
        if key is None: return None
        return self.sounds.get(key)

    def play_sfx(self, key, voice_idx, volume_multiplier=1.0, loop=False):
        sound = self.get_sound(key)
        if sound:
            if self.mixer.voice[voice_idx].playing:
                # print(f"AUDIO_MAN_CP: SFX Voice {voice_idx} busy, '{key}' not played.")
                return False # Don't interrupt existing SFX on this dedicated channel easily

            # print(f"AUDIO_MAN_CP: ---> SFX PLAYING: '{key}' on voice {voice_idx}")
            self.mixer.voice[voice_idx].level = config.SFX_VOLUME * volume_multiplier
            self.mixer.play(sound, voice=voice_idx, loop=loop)
            return True
        # print(f"AUDIO_MAN_CP: SFX sound '{key}' not found.")
        return False

    def play_accel_burst(self):
        if not config.ENABLE_ACCEL_BURST: return False
        current_time = time.monotonic()
        if current_time - self.last_accel_burst_time > config.ACCEL_BURST_COOLDOWN_S:
            vol = config.SFX_VOLUME * config.ACCEL_BURST_SFX_VOLUME_MULTIPLIER
            if self.play_sfx("accel_burst", self.sfx_accel_voice_idx, volume_multiplier=min(1.0, vol)):
                self.last_accel_burst_time = current_time
                return True
        return False

    def play_decel_pop(self):
        if not config.ENABLE_DECEL_POPS: return False
        current_time = time.monotonic()
        if current_time - self.last_pop_time > config.DECEL_POP_COOLDOWN_S:
            vol = config.SFX_VOLUME * config.DECEL_POP_SFX_VOLUME_MULTIPLIER
            if self.play_sfx("decel_pop", self.sfx_decel_voice_idx, volume_multiplier=min(1.0, vol)):
                self.last_pop_time = current_time
                return True
        return False

    def update_engine_sound(self, target_sound_key):
        sound_to_play_obj = self.get_sound(target_sound_key)
        if not sound_to_play_obj:
            # print(f"AUDIO_MAN_CP: WARN - update_engine_sound with '{target_sound_key}', sound not found.")
            return

        # If already crossfading TO this sound, do nothing
        if self.is_crossfading and self.crossfade_to_sound_key == target_sound_key:
            return

        # If crossfading to something ELSE, stop current crossfade and start a new one
        if self.is_crossfading and self.crossfade_to_sound_key != target_sound_key:
            # print(f"AUDIO_MAN_CP: Crossfade interrupted. New target: {target_sound_key}")
            self.mixer.stop(voice=self.active_engine_voice_idx)
            self.mixer.stop(voice=self.inactive_engine_voice_idx)
            self.is_crossfading = False
            self._start_crossfade(target_sound_key)
            return

        # If not crossfading and target is current sound, ensure it's playing
        if target_sound_key == self.current_loop_sound_key and not self.is_crossfading:
            if not self.mixer.voice[self.active_engine_voice_idx].playing or \
               self.mixer.voice[self.active_engine_voice_idx].sample != sound_to_play_obj: # Check if correct sound is playing
                # print(f"AUDIO_MAN_CP: Restarting '{target_sound_key}' on active voice {self.active_engine_voice_idx}")
                self.mixer.voice[self.active_engine_voice_idx].level = config.MAIN_ENGINE_VOLUME
                self.mixer.play(sound_to_play_obj, voice=self.active_engine_voice_idx, loop=True)
            return

        # If no sound playing or different sound, start crossfade (or direct play if no current sound)
        if (target_sound_key != self.current_loop_sound_key or self.current_loop_sound_key is None) and not self.is_crossfading:
            self._start_crossfade(target_sound_key)
            return

    def _start_crossfade(self, new_sound_key):
        from_sound_key_for_fade = self.current_loop_sound_key
        new_sound_obj = self.get_sound(new_sound_key)

        if not new_sound_obj:
            # print(f"AUDIO_MAN_CP: XFADE ERR - New sound '{new_sound_key}' not found.")
            return
        if from_sound_key_for_fade == new_sound_key and self.mixer.voice[self.active_engine_voice_idx].playing:
            # print(f"AUDIO_MAN_CP: XFADE INFO - Already playing '{new_sound_key}'. No crossfade needed.")
            return # Already on this sound, no fade needed

        # print(f"AUDIO_MAN_CP: XFADE START: From '{from_sound_key_for_fade}' To '{new_sound_key}'")

        self.is_crossfading = True
        self.crossfade_start_time = time.monotonic()
        self.crossfade_from_sound_key = from_sound_key_for_fade
        self.crossfade_to_sound_key = new_sound_key
        self.xfade_log_counter = 0

        # Swap active and inactive voices
        previous_active_voice_idx = self.active_engine_voice_idx
        self.active_engine_voice_idx = self.inactive_engine_voice_idx
        self.inactive_engine_voice_idx = previous_active_voice_idx

        # Play new sound on the (now) active voice, starting at 0 volume
        self.mixer.play(new_sound_obj, voice=self.active_engine_voice_idx, loop=True)
        self.mixer.voice[self.active_engine_voice_idx].level = 0.0

        # Ensure old sound is playing on the (now) inactive voice at full volume (it will be faded out)
        old_sound_obj = self.get_sound(self.crossfade_from_sound_key)
        if old_sound_obj:
            if not self.mixer.voice[self.inactive_engine_voice_idx].playing or \
               self.mixer.voice[self.inactive_engine_voice_idx].sample != old_sound_obj:
                self.mixer.play(old_sound_obj, voice=self.inactive_engine_voice_idx, loop=True)
            self.mixer.voice[self.inactive_engine_voice_idx].level = config.MAIN_ENGINE_VOLUME
        else: # If there was no previous sound, ensure inactive channel is silent
            self.mixer.stop(voice=self.inactive_engine_voice_idx)


    def _handle_crossfade(self):
        if not self.is_crossfading: return

        elapsed_time = time.monotonic() - self.crossfade_start_time
        progress = min(elapsed_time / config.CROSSFADE_DURATION_S, 1.0)

        vol_to = config.MAIN_ENGINE_VOLUME * progress
        vol_from = config.MAIN_ENGINE_VOLUME * (1.0 - progress)

        sound_to_obj = self.get_sound(self.crossfade_to_sound_key)
        sound_from_obj = self.get_sound(self.crossfade_from_sound_key)
        
        # For debugging, log occasionally
        # log_this_time = (self.xfade_log_counter % 60 == 0) # e.g. every ~second if loop is fast
        # if log_this_time:
        #    print(f"AM_XFADE: Prog:{progress:.2f} ToV:{self.active_engine_voice_idx} ({vol_to:.2f}), FromV:{self.inactive_engine_voice_idx} ({vol_from:.2f})")
        # self.xfade_log_counter +=1

        if sound_to_obj and self.mixer.voice[self.active_engine_voice_idx].playing:
            self.mixer.voice[self.active_engine_voice_idx].level = vol_to
        
        if sound_from_obj and self.mixer.voice[self.inactive_engine_voice_idx].playing:
            self.mixer.voice[self.inactive_engine_voice_idx].level = vol_from
        elif not sound_from_obj: # If there was no "from" sound, ensure inactive channel stays silent
             self.mixer.voice[self.inactive_engine_voice_idx].level = 0.0


        if progress >= 1.0:
            # print(f"AUDIO_MAN_CP: XFADE END. To: '{self.crossfade_to_sound_key}'")
            if sound_from_obj and self.mixer.voice[self.inactive_engine_voice_idx].playing:
                self.mixer.stop(voice=self.inactive_engine_voice_idx)
            
            self.current_loop_sound_key = self.crossfade_to_sound_key
            self.is_crossfading = False
            self.crossfade_from_sound_key = None
            self.crossfade_to_sound_key = None
            # Ensure the final sound is at full volume
            if sound_to_obj and self.mixer.voice[self.active_engine_voice_idx].playing:
                 self.mixer.voice[self.active_engine_voice_idx].level = config.MAIN_ENGINE_VOLUME


    def stop_engine_sounds_for_shutdown(self):
        # A more graceful stop for engine loops during shutdown SFX
        # For CircuitPython, a quick fade might be complex; direct stop is simpler.
        # Or, just let the shutdown SFX play over them if it's on a different voice.
        # We can just stop them to ensure they don't interfere with shutdown sfx.
        if self.mixer.voice[self.engine_voice_idx1].playing:
            self.mixer.voice[self.engine_voice_idx1].level = 0.0 # Quick "fade"
            self.mixer.stop(voice=self.engine_voice_idx1)
        if self.mixer.voice[self.engine_voice_idx2].playing:
            self.mixer.voice[self.engine_voice_idx2].level = 0.0 # Quick "fade"
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
        for i in range(config.NUM_MIXER_VOICES):
            self.mixer.stop(voice=i)
        self.current_loop_sound_key = None
        self.is_crossfading = False

    def quit(self): # In CircuitPython, deinit might be needed for pins
        self.stop_all_sounds()
        if self.audio_out:
            self.audio_out.deinit()
        print("AUDIO_MAN_CP: Audio system deinitialized.")

    def update(self): # Called from the main loop
        if self.is_crossfading:
            self._handle_crossfade()
        # Keep the mixer playing (it should always be, via self.audio_out.play(self.mixer) in __init__)
        # If not self.audio_out.playing and self.mixer: # This check might be redundant
        #    self.audio_out.play(self.mixer)


    def is_sfx_starter_shutdown_busy(self):
        return self.mixer.voice[self.sfx_startshut_voice_idx].playing

    def is_any_engine_sound_playing(self, ignore_sfx=False):
        # Check if any of the dedicated engine loop voices are active
        e1_playing = self.mixer.voice[self.engine_voice_idx1].playing
        e2_playing = self.mixer.voice[self.engine_voice_idx2].playing
        
        if ignore_sfx:
            return e1_playing or e2_playing or self.is_crossfading

        sfx_ss_busy = self.mixer.voice[self.sfx_startshut_voice_idx].playing
        sfx_accel_busy = self.mixer.voice[self.sfx_accel_voice_idx].playing
        sfx_decel_busy = self.mixer.voice[self.sfx_decel_voice_idx].playing
        
        return e1_playing or e2_playing or self.is_crossfading or sfx_ss_busy or sfx_accel_busy or sfx_decel_busy