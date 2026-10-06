"""Funções compartilhadas entre a interface gráfica e a de terminal."""

from typing import Optional, Sequence, Tuple

from ..core.enums import CourtSide, EventType, Player
from ..core.rules import CHANGEOVER_SECONDS, SET_BREAK_SECONDS
from ..core.score import Event, Score
from ..i18n import t

_SUPERSCRIPT = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")


def set_cell(result, player: Player) -> str:
    """Games de um set concluído para um jogador, com o tiebreak do perdedor em sobrescrito."""
    if result.match_tiebreak:
        return str(result.tiebreak[player])
    text = str(result.games[player])
    if result.tiebreak and result.winner != player:
        text += str(result.tiebreak[player]).translate(_SUPERSCRIPT)
    return text


def situation_text(score: Score, names: Sequence[str]) -> str:
    """Situação atual do game: deuce, vantagem, tiebreak etc. ('' se nada especial)."""
    if score.is_over:
        return t("match_over", name=names[score.winner])
    if score.in_tiebreak:
        return t("tiebreak")
    p = score.points
    if p[0] == p[1] and p[0] >= 3:
        return t("deciding_point") if score.config.no_ad else t("deuce")
    if max(p) >= 4 and abs(p[0] - p[1]) == 1:
        return t("advantage", name=names[Player.ONE if p[0] > p[1] else Player.TWO])
    return ""


def serving_text(score: Score, names: Sequence[str]) -> str:
    if score.is_over:
        return ""
    key = "serving_deuce" if score.serve_court == CourtSide.DEUCE else "serving_ad"
    return t(key, name=names[score.server])


def has_change_ends(events: Sequence[Event]) -> bool:
    return any(e.type == EventType.CHANGE_ENDS for e in events)


def rest_period(events: Sequence[Event]) -> Optional[Tuple[str, int]]:
    """Descanso a cronometrar depois de um ponto: ("set", 120), ("game", 90) ou None.

    Set: 120 s entre um set e outro (não há descanso quando a partida acaba).
    Game: 90 s só quando há troca de lado (games ímpares); nos pares e no tiebreak não para.
    """
    types = {e.type for e in events}
    if EventType.MATCH in types:
        return None
    if EventType.SET in types:
        return "set", SET_BREAK_SECONDS
    if EventType.GAME in types and EventType.CHANGE_ENDS in types:
        return "game", CHANGEOVER_SECONDS
    return None