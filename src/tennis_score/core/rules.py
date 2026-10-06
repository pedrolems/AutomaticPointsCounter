"""Regras de pontuação do tênis profissional (funções puras, sem estado)."""

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

from .enums import CourtSide, FinalSetFormat, Player

POINT_NAMES = ("0", "15", "30", "40")

CHANGEOVER_SECONDS = 90   # descanso na troca de lado (após os games ímpares)
SET_BREAK_SECONDS = 120   # descanso entre um set e outro


@dataclass(frozen=True)
class MatchConfig:
    best_of: int = 3                                   # 1, 3 ou 5 sets
    final_set: FinalSetFormat = FinalSetFormat.TIEBREAK_7
    no_ad: bool = False                                # 40-40 => ponto decisivo

    def __post_init__(self):
        if self.best_of not in (1, 3, 5):
            raise ValueError("best_of deve ser 1, 3 ou 5")

    @property
    def sets_to_win(self) -> int:
        return self.best_of // 2 + 1


@dataclass(frozen=True)
class TiebreakRule:
    trigger_games: int      # placar de games (igual para os dois) que dispara o tiebreak
    target_points: int      # 7 ou 10
    replaces_set: bool = False  # True: o tiebreak É o set (match tiebreak)


def is_deciding_set(sets_won: Sequence[int], config: MatchConfig) -> bool:
    need = config.sets_to_win - 1
    return sets_won[0] == need and sets_won[1] == need


def tiebreak_rule_for(config: MatchConfig, deciding: bool) -> Optional[TiebreakRule]:
    if not deciding:
        return TiebreakRule(6, 7)
    fmt = config.final_set
    if fmt == FinalSetFormat.ADVANTAGE:
        return None
    if fmt == FinalSetFormat.TIEBREAK_7:
        return TiebreakRule(6, 7)
    if fmt == FinalSetFormat.TIEBREAK_10:
        return TiebreakRule(6, 10)
    if fmt == FinalSetFormat.TIEBREAK_7_AT_12:
        return TiebreakRule(12, 7)
    return TiebreakRule(0, 10, replaces_set=True)


def _lead_winner(a: int, b: int) -> Player:
    return Player.ONE if a > b else Player.TWO


def game_winner(points: Sequence[int], no_ad: bool = False) -> Optional[Player]:
    a, b = points
    if max(a, b) < 4:
        return None
    if no_ad:
        return _lead_winner(a, b)
    return _lead_winner(a, b) if abs(a - b) >= 2 else None


def tiebreak_winner(points: Sequence[int], target: int) -> Optional[Player]:
    a, b = points
    if max(a, b) >= target and abs(a - b) >= 2:
        return _lead_winner(a, b)
    return None


def set_winner(games: Sequence[int]) -> Optional[Player]:
    """Set sem tiebreak: 6 games com 2 de diferença (6-4, 7-5, ...)."""
    a, b = games
    if max(a, b) >= 6 and abs(a - b) >= 2:
        return _lead_winner(a, b)
    return None


def should_start_tiebreak(games: Sequence[int], rule: Optional[TiebreakRule]) -> bool:
    return rule is not None and games[0] == games[1] == rule.trigger_games


def is_deuce(points: Sequence[int]) -> bool:
    return points[0] == points[1] and points[0] >= 3


def advantage_holder(points: Sequence[int]) -> Optional[Player]:
    a, b = points
    if max(a, b) >= 4 and abs(a - b) == 1:
        return _lead_winner(a, b)
    return None


def point_labels(points: Sequence[int], no_ad: bool = False) -> Tuple[str, str]:
    """Placar de um game em texto: ('15','30'), ('40','40'), ('Ad','40')."""
    a, b = points
    if max(a, b) <= 3:
        return POINT_NAMES[a], POINT_NAMES[b]
    if a == b:
        return "40", "40"
    holder = advantage_holder(points)
    if holder is None:  # jogo já decidido; mostra 40 do vencedor
        return ("40", POINT_NAMES[min(b, 3)]) if a > b else (POINT_NAMES[min(a, 3)], "40")
    return ("Ad", "40") if holder == Player.ONE else ("40", "Ad")


def tiebreak_server(first_server: Player, points_played: int) -> Player:
    """Quem saca no próximo ponto do tiebreak: 1 ponto do primeiro, depois 2 e 2 alternados."""
    return first_server if ((points_played + 1) // 2) % 2 == 0 else first_server.opponent


def tiebreak_change_ends(points_played: int) -> bool:
    """No tiebreak a troca de lado acontece a cada 6 pontos."""
    return points_played > 0 and points_played % 6 == 0


def change_ends_after_game(total_games_in_set: int) -> bool:
    """Troca de lado após o 1º, 3º, 5º... game do set (e ao fim do set se total ímpar)."""
    return total_games_in_set % 2 == 1


def serve_court(points_played: int) -> CourtSide:
    """Pontos pares (0, 2, 4...) sacam do lado deuce; ímpares do lado ad. Vale também no tiebreak."""
    return CourtSide.DEUCE if points_played % 2 == 0 else CourtSide.AD