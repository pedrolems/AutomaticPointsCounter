"""Interface de terminal."""

from typing import Sequence

from ..audio import TTS, Umpire
from ..core.enums import Player
from ..core.score import Score
from ..i18n import t
from .common import has_change_ends, serving_text, set_cell, situation_text


def render_scoreboard(score: Score, names: Sequence[str]) -> str:
    width = max(len(n) for n in names) + 2
    pts = score.point_labels()
    lines = []
    for p in (Player.ONE, Player.TWO):
        dot = "●" if (p == score.server and not score.is_over) else " "
        sets = " ".join(f"{set_cell(r, p):>3}" for r in score.sets)
        cur = "" if score.is_over else f"{score.games[p]:>3}"
        lines.append(f"{dot} {names[p]:<{width}}{sets} {cur}   {'' if score.is_over else pts[p]:>3}")
    return "\n".join(lines)


def run_cli(score: Score, umpire: Umpire, tts: TTS, names: Sequence[str]) -> None:
    print(t("cli_help"))
    opening = umpire.opening(score)
    print(f"[{t('umpire')}] {opening}")
    tts.speak(opening)
    print(render_scoreboard(score, names))
    while not score.is_over:
        try:
            cmd = input(t("cli_prompt")).strip().lower()
        except (EOFError, KeyboardInterrupt):
            break
        if cmd in ("q", "quit", "sair"):
            break
        if cmd in ("u", "undo"):
            score.undo()
        elif cmd in ("1", "2"):
            events = score.point_won(Player.ONE if cmd == "1" else Player.TWO)
            calls = umpire.announce(events, score)
            text = " ".join(calls)
            print(f"[{t('umpire')}] {text}")
            tts.speak(text, clips=umpire.clips(events))
            if has_change_ends(events):
                print(t("change_ends"))
        else:
            continue
        print(render_scoreboard(score, names))
        extra = situation_text(score, names)
        if extra:
            print(extra)
        serving = serving_text(score, names)
        if serving:
            print(serving)
    tts.shutdown()