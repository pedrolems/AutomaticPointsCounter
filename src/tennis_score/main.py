"""Ponto de entrada: python -m tennis_score.main [opções]"""

import argparse
import random

from .audio import TTS, Umpire
from .core.enums import FinalSetFormat, Language, Player
from .core.rules import MatchConfig
from .core.score import Score
from .i18n import set_language, t


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Contador automático de pontos de tênis")
    ap.add_argument("--ui", choices=("gui", "cli"), default="gui")
    ap.add_argument("--lang", choices=[l.value for l in Language], default="pt")
    ap.add_argument("--p1", default=None, help="Nome do jogador 1")
    ap.add_argument("--p2", default=None, help="Nome do jogador 2")
    ap.add_argument("--best-of", type=int, choices=(1, 3, 5), default=3)
    ap.add_argument("--final-set", choices=[f.value for f in FinalSetFormat], default=FinalSetFormat.TIEBREAK_7.value)
    ap.add_argument("--no-ad", action="store_true", help="Ponto decisivo em 40-40")
    ap.add_argument("--first-server", choices=("1", "2", "random"), default="random")
    ap.add_argument("--mute", action="store_true", help="Desliga a voz do umpire")
    return ap.parse_args(argv)


def main(argv=None) -> None:
    args = parse_args(argv)
    lang = Language(args.lang)
    set_language(lang)
    names = [args.p1 or t("player_n", n=1), args.p2 or t("player_n", n=2)]
    config = MatchConfig(args.best_of, FinalSetFormat(args.final_set), args.no_ad)
    first = None if args.first_server == "random" else Player(int(args.first_server) - 1)

    if args.ui == "gui":
        try:
            from .ui.gui import run_gui
        except ImportError:
            print(t("no_tk"))
            args.ui = "cli"
        else:
            run_gui(config, names, first, lang, sound=not args.mute)
            return

    from .ui.cli import run_cli
    score = Score(config, first if first is not None else random.choice(list(Player)))
    run_cli(score, Umpire(names, lang), TTS(lang, enabled=not args.mute), names)


if __name__ == "__main__":
    main()
