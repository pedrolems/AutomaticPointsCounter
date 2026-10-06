"""Text-to-speech em thread separada (não trava a interface).

Usa pyttsx3 (offline) se estiver instalado; caso contrário fica mudo sem quebrar nada.
Instalar: pip install pyttsx3

Idiomas que têm áudios gravados em assets/audio (ex.: português) não usam a voz sintética:
tocam só os áudios gravados (ver clips.py); o que ainda não foi gravado fica sem voz.
"""

import queue
import threading
from typing import Optional, Sequence

from ..core.enums import Language
from .clips import ClipPlayer, Cue

_STOP = object()

_VOICE_HINTS = {
    Language.PT: ("pt-br", "pt_br", "brazil", "portuguese", "portugu", "pt-pt", "pt_"),
    Language.EN: ("en-us", "en_us", "en-gb", "english", "en_"),
}


class TTS:
    def __init__(self, language: Language = Language.EN, enabled: bool = True, rate: int = 165):
        self.language = Language(language)
        self.enabled = enabled
        self.rate = rate
        self._q: "queue.Queue" = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._clips = ClipPlayer()
        self.available = self._check_backend()

    @staticmethod
    def _check_backend() -> bool:
        try:
            import pyttsx3  # noqa: F401
            return True
        except Exception:
            return False

    def set_language(self, language: Language) -> None:
        self.language = Language(language)

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        if not enabled:
            self._drain()
            self._clips.stop()

    def speak(self, text: str, interrupt: bool = True, clips: Sequence[Cue] = ()) -> None:
        """Fala `text` com a voz sintética; se o idioma tem áudios gravados, toca `clips` no lugar."""
        if self._clips.has_recordings(self.language):
            if self.enabled:
                self._clips.play(self.language, clips, interrupt)
            return
        if not (self.enabled and self.available and text):
            return
        if interrupt:
            self._drain()
        self._ensure_thread()
        self._q.put((self.language, text))

    def shutdown(self) -> None:
        self._clips.shutdown()
        if self._thread:
            self._drain()
            self._q.put(_STOP)

    # ------------------------------------------------------------ internos
    def _drain(self) -> None:
        try:
            while True:
                self._q.get_nowait()
        except queue.Empty:
            pass

    def _ensure_thread(self) -> None:
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._worker, daemon=True)
            self._thread.start()

    def _worker(self) -> None:
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", self.rate)
        except Exception:
            self.available = False
            return
        current = None
        while True:
            item = self._q.get()
            if item is _STOP:
                return
            lang, text = item
            try:
                if lang != current:
                    self._select_voice(engine, lang)
                    current = lang
                engine.say(text)
                engine.runAndWait()
            except Exception:
                pass

    @staticmethod
    def _select_voice(engine, lang: Language) -> None:
        hints = _VOICE_HINTS[lang]
        for voice in engine.getProperty("voices"):
            blob = f"{voice.id} {voice.name} {getattr(voice, 'languages', '')}".lower()
            if any(h in blob for h in hints):
                engine.setProperty("voice", voice.id)
                return