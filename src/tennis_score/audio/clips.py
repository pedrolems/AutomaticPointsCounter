"""Toca os áudios gravados do umpire (assets/audio/<idioma>/<nome>.<ext>).

Cada áudio é achado pelo "nome base" do arquivo, sem diferenciar maiúsculas de minúsculas e
ignorando as extensões: `15-0.m4a.mp4`, `VANTAGEM.m4a.mp4`, `15-0.wav`... tudo funciona.
A pasta é lida a cada fala, então dá para colocar um áudio novo com o programa aberto.

Como tocar (nenhuma biblioteca precisa ser instalada):
  - Windows: `.wav` pelo módulo `winsound` (o mais confiável); outros formatos pelo MCI,
    a API de mídia do próprio Windows (via ctypes), que nem sempre abre .mp4/.m4a.
  - macOS: `afplay`.
  - Qualquer sistema: `ffplay`, `mpv` ou `vlc`, se estiverem no PATH (também servem de
    reserva no Windows, caso o MCI não consiga abrir o formato do arquivo).
"""

import queue
import shutil
import subprocess
import sys
import threading
import time
import wave
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Union

from ..core.enums import Language

# <raiz do projeto>/assets/audio
AUDIO_ROOT = Path(__file__).resolve().parents[3] / "assets" / "audio"
AUDIO_EXTENSIONS = {".mp4", ".m4a", ".aac", ".mp3", ".wav", ".ogg", ".flac"}

# Um "cue" é a chave de um áudio ("15-0") ou uma tupla de alternativas em ordem de preferência
# (toca a primeira que existir).
Cue = Union[str, Sequence[str]]

_STOP = object()

_COMMAND_PLAYERS = (
    ("afplay",),
    ("ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"),
    ("mpv", "--no-video", "--really-quiet"),
    ("cvlc", "--play-and-exit", "--quiet"),
    ("vlc", "--intf", "dummy", "--play-and-exit", "--quiet"),
)


def _index(folder: Path) -> Dict[str, Path]:
    """{nome base em minúsculas: arquivo} de uma pasta de áudios."""
    if not folder.is_dir():
        return {}
    files: Dict[str, Path] = {}
    # .wav primeiro: se existir o mesmo áudio em vários formatos, o WAV é o que toca em qualquer PC
    for f in sorted(folder.iterdir(), key=lambda f: (f.suffix.lower() != ".wav", f.name)):
        if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS:
            files.setdefault(f.name.split(".")[0].lower(), f)
    return files


class _BackendError(Exception):
    """Este player não conseguiu tocar o arquivo."""


class _WinsoundBackend:
    """Toca arquivos .wav com o módulo winsound (já vem com o Python no Windows)."""

    extensions = {".wav"}
    name = "winsound (Windows)"

    def __init__(self) -> None:
        import winsound  # ImportError fora do Windows
        self._winsound = winsound

    def play(self, path: Path, aborted: Callable[[], bool]) -> None:
        try:
            with wave.open(str(path), "rb") as w:
                duration = w.getnframes() / float(w.getframerate())
            self._winsound.PlaySound(str(path), self._winsound.SND_FILENAME | self._winsound.SND_ASYNC)
        except (wave.Error, EOFError, OSError, RuntimeError) as exc:
            raise _BackendError(str(exc))
        started = time.monotonic()
        while not aborted() and time.monotonic() - started < duration + 0.05:
            time.sleep(0.02)
        self._winsound.PlaySound(None, self._winsound.SND_PURGE)


class _MciBackend:
    """Player do Windows (winmm/MCI). Só funciona no Windows; o import falha nos outros."""

    ALIAS = "apc_clip"

    def __init__(self) -> None:
        import ctypes
        self._winmm = ctypes.windll.winmm  # AttributeError fora do Windows
        self._buf = ctypes.create_unicode_buffer(256)
        self.name = "MCI (Windows)"

    def _send(self, command: str) -> int:
        self._buf.value = ""
        return self._winmm.mciSendStringW(command, self._buf, len(self._buf), 0)

    def _error_text(self, code: int) -> str:
        self._winmm.mciGetErrorStringW(code, self._buf, len(self._buf))
        return f"erro MCI {code}: {self._buf.value}"

    def play(self, path: Path, aborted: Callable[[], bool]) -> None:
        self._send(f"close {self.ALIAS}")
        err = self._send(f'open "{path}" type mpegvideo alias {self.ALIAS}')
        if err:
            raise _BackendError(self._error_text(err))
        try:
            err = self._send(f"play {self.ALIAS}")
            if err:
                raise _BackendError(self._error_text(err))
            self._send(f"status {self.ALIAS} length")
            length_s = (int(self._buf.value) / 1000) if self._buf.value.isdigit() else 5.0
            started = time.monotonic()
            while not aborted() and time.monotonic() - started < length_s + 1.0:
                time.sleep(0.02)
                self._send(f"status {self.ALIAS} mode")
                if self._buf.value == "stopped" and time.monotonic() - started > 0.15:
                    break
        finally:
            self._send(f"stop {self.ALIAS}")
            self._send(f"close {self.ALIAS}")


class _CommandBackend:
    """Toca chamando um programa externo (afplay, ffplay, mpv, vlc)."""

    def __init__(self, argv: Sequence[str]) -> None:
        self._argv = list(argv)
        self.name = Path(argv[0]).stem

    def play(self, path: Path, aborted: Callable[[], bool]) -> None:
        try:
            proc = subprocess.Popen(
                [*self._argv, str(path)], stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except OSError as exc:
            raise _BackendError(str(exc))
        was_aborted = False
        try:
            while proc.poll() is None:
                if aborted():
                    was_aborted = True
                    break
                time.sleep(0.02)
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.wait()
        if not was_aborted and proc.returncode != 0:
            raise _BackendError(f"{self.name} terminou com código {proc.returncode}")


def _make_backends() -> list:
    backends: list = []
    if sys.platform == "win32":
        for backend_class in (_WinsoundBackend, _MciBackend):
            try:
                backends.append(backend_class())
            except Exception:
                pass
    for argv in _COMMAND_PLAYERS:
        exe = shutil.which(argv[0])
        if exe:
            backends.append(_CommandBackend((exe, *argv[1:])))
    return backends


class ClipPlayer:
    """Fila de áudios tocada numa thread própria (não trava a interface)."""

    def __init__(self, root: Path = AUDIO_ROOT) -> None:
        self.root = Path(root)
        self._q: "queue.Queue" = queue.Queue()
        self._generation = 0          # sobe a cada interrupção; áudios antigos se cancelam
        self._thread: Optional[threading.Thread] = None
        self._warned: set = set()

    # ------------------------------------------------------------ API
    def has_recordings(self, language: Language) -> bool:
        """True se o idioma tem pelo menos um áudio gravado (então só os áudios são usados)."""
        return bool(_index(self.root / Language(language).audio_dir))

    def resolve(self, language: Language, cues: Sequence[Cue]) -> List[Path]:
        """Arquivos que existem para os cues pedidos; cues sem áudio são simplesmente pulados."""
        folder = self.root / Language(language).audio_dir
        files = _index(folder)
        found: List[Path] = []
        for cue in cues:
            keys = (cue,) if isinstance(cue, str) else tuple(cue)
            path = next((files[k.lower()] for k in keys if k.lower() in files), None)
            if path is not None:
                found.append(path)
            elif keys:
                self._warn(f"falta:{language}:{keys[0].lower()}",
                           f"[áudio] falta o áudio '{keys[0]}' em {folder} (nada será falado neste ponto).")
        return found

    def play(self, language: Language, cues: Sequence[Cue], interrupt: bool = True) -> None:
        paths = self.resolve(language, cues)
        if interrupt:
            self.stop()
        if not paths:
            return
        self._ensure_thread()
        self._q.put((self._generation, paths))

    def stop(self) -> None:
        """Corta o áudio em andamento e esvazia a fila."""
        self._generation += 1
        try:
            while True:
                self._q.get_nowait()
        except queue.Empty:
            pass

    def shutdown(self) -> None:
        self.stop()
        if self._thread is not None:
            self._q.put(_STOP)

    # ------------------------------------------------------------ internos
    def _ensure_thread(self) -> None:
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._worker, daemon=True)
            self._thread.start()

    def _worker(self) -> None:
        backends = _make_backends()
        while True:
            item = self._q.get()
            if item is _STOP:
                return
            generation, paths = item
            for path in paths:
                if generation != self._generation:
                    break
                self._play_one(backends, path, lambda g=generation: g != self._generation)

    def _play_one(self, backends: list, path: Path, aborted: Callable[[], bool]) -> None:
        failed, last_error = [], None
        for backend in list(backends):
            exts = getattr(backend, "extensions", None)
            if exts and path.suffix.lower() not in exts:
                continue  # este player só toca outros formatos; não é falha
            try:
                backend.play(path, aborted)
            except _BackendError as exc:
                failed.append(backend)
                last_error = f"{backend.name}: {exc}"
                continue
            for bad in failed:  # outro player conseguiu: este não serve para estes arquivos
                backends.remove(bad)
            return
        if not backends:
            self._warn("sem-player", "[áudio] nenhum player de áudio disponível neste computador.")
        else:
            self._warn(path.name, f"[áudio] não consegui tocar {path.name} ({last_error or 'nenhum player compatível'}).")

    def _warn(self, key: str, message: str) -> None:
        if key not in self._warned:
            self._warned.add(key)
            print(message, file=sys.stderr)