"""Reconocimiento de voz local con Vosk y síntesis de voz local con pyttsx3."""
import json
import queue
import threading


class VoiceIO:
    def __init__(self, model_path, on_heard, on_error):
        self.model_path = model_path
        self.on_heard = on_heard  # Invocado en hilo: solo queue.put, nunca Tk directo.
        self.on_error = on_error
        self.stop_event = threading.Event()
        self.mic_stop = threading.Event()
        self.speaking = threading.Event()
        self.speech_queue = queue.Queue()
        self._mic_thread = None
        self._tts_thread = None
        self._tts_thread = threading.Thread(target=self._synth_loop, daemon=True, name='speech-output')
        self._tts_thread.start()

    def start_mic(self):
        if self._mic_thread and self._mic_thread.is_alive():
            return
        if not self.model_path.is_dir():
            raise RuntimeError('No encuentro el modelo español de Vosk. Consulta README.md.')
        self.mic_stop.clear()
        self._mic_thread = threading.Thread(target=self._recognize_loop, daemon=True, name='microphone')
        self._mic_thread.start()

    def stop_mic(self):
        self.mic_stop.set()

    def say(self, text):
        if text.strip() and not self.stop_event.is_set():
            self.speech_queue.put(text[:500])

    def close(self):
        self.stop_event.set()
        self.mic_stop.set()
        self.speech_queue.put(None)

    def _recognize_loop(self):
        try:
            import sounddevice as sd
            from vosk import Model, KaldiRecognizer, SetLogLevel
            SetLogLevel(-1)
            model = Model(str(self.model_path))
            recognizer = KaldiRecognizer(model, 16000)
            audio_queue = queue.Queue(maxsize=12)

            def callback(indata, frames, time_info, status):
                if self.speaking.is_set() or self.mic_stop.is_set():
                    return
                try:
                    audio_queue.put_nowait(bytes(indata))
                except queue.Full:
                    pass

            with sd.RawInputStream(samplerate=16000, blocksize=4000,
                                   dtype='int16', channels=1, callback=callback):
                while not self.mic_stop.is_set() and not self.stop_event.is_set():
                    try:
                        audio = audio_queue.get(timeout=0.2)
                    except queue.Empty:
                        continue
                    if self.speaking.is_set():
                        recognizer.Reset()
                        continue
                    if recognizer.AcceptWaveform(audio):
                        text = json.loads(recognizer.Result()).get('text', '').strip()
                        if text:
                            self.on_heard(text)
        except Exception as exc:
            self.on_error(f'Voz (micrófono): {exc}')

    def _synth_loop(self):
        engine = None
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty('rate', 170)
        except Exception as exc:
            self.on_error(f'Voz (salida): {exc}')
        while not self.stop_event.is_set():
            try:
                item = self.speech_queue.get(timeout=0.3)
            except queue.Empty:
                continue
            if item is None:
                return
            if engine:
                self.speaking.set()
                try:
                    engine.say(item)
                    engine.runAndWait()
                except Exception as exc:
                    self.on_error(f'Síntesis de voz: {exc}')
                finally:
                    self.speaking.clear()
