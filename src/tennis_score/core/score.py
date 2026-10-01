"""Estado da partida: pontos, games, sets, sacador e histórico (undo)."""

import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from . import rules
from .enums import CourtSide, EventType, Player
from .rules import MatchConfig, TiebreakRule


class MatchOver(Exception):
    """Levantada ao tentar marcar ponto depois do fim da partida."""


@dataclass
class SetResult:
    games: Tuple[int, int]
    winner: Player
    tiebreak: Optional[Tuple[int, int]] = None  # pontos do tiebreak, se houve
    match_tiebreak: bool = False                # o set foi um super tiebreak

    def score_for(self, player: Player) -> Tuple[int, int]:
        """(pontos do player, pontos do adversário) — na visão do player."""
        a, b = self.tiebreak if self.match_tiebreak else self.games
        return (a, b) if player == Player.ONE else (b, a)

    def __str__(self) -> str:
        if self.match_tiebreak:
            return f"[{self.tiebreak[0]}-{self.tiebreak[1]}]"
        text = f"{self.games[0]}-{self.games[1]}"
        if self.tiebreak:
            text += f"({min(self.tiebreak)})"
        return text


@dataclass
class Event:
    type: EventType
    player: Optional[Player] = None
    data: Dict[str, Any] = field(default_factory=dict)


class Score:
    def __init__(self, config: Optional[MatchConfig] = None, first_server: Player = Player.ONE):
        self.config = config or MatchConfig()
        self.first_server = first_server
        self.game_server: Player = first_server  # quem iniciou o game/tiebreak atual
        self.sets: List[SetResult] = []
        self.winner: Optional[Player] = None
        self.games: List[int] = [0, 0]
        self.points: List[int] = [0, 0]
        self.set_rule: Optional[TiebreakRule] = None
        self.tiebreak_rule: Optional[TiebreakRule] = None  # não-None => tiebreak em andamento
        self._history: List[dict] = []
        self._begin_set()

    # ------------------------------------------------------------ consultas
    @property
    def in_tiebreak(self) -> bool:
        return self.tiebreak_rule is not None

    @property
    def sets_won(self) -> Tuple[int, int]:
        return (
            sum(1 for s in self.sets if s.winner == Player.ONE),
            sum(1 for s in self.sets if s.winner == Player.TWO),
        )

    @property
    def set_number(self) -> int:
        return len(self.sets) + 1

    @property
    def is_over(self) -> bool:
        return self.winner is not None

    @property
    def server(self) -> Player:
        if self.in_tiebreak:
            return rules.tiebreak_server(self.game_server, sum(self.points))
        return self.game_server

    @property
    def receiver(self) -> Player:
        return self.server.opponent

    @property
    def serve_court(self) -> CourtSide:
        return rules.serve_court(sum(self.points))

    @property
    def can_undo(self) -> bool:
        return bool(self._history)

    def point_labels(self) -> Tuple[str, str]:
        if self.in_tiebreak:
            return str(self.points[0]), str(self.points[1])
        return rules.point_labels(self.points, self.config.no_ad)

    # ------------------------------------------------------------ ações
    def point_won(self, player: Player) -> List[Event]:
        if self.is_over:
            raise MatchOver()
        self._history.append(self._snapshot())
        self.points[player] += 1
        total = sum(self.points)

        if self.in_tiebreak:
            w = rules.tiebreak_winner(self.points, self.tiebreak_rule.target_points)
            if w is not None:
                return self._finish_game(w, tiebreak=tuple(self.points))
            events = [Event(EventType.TIEBREAK_POINT, player, self._point_data())]
            if rules.tiebreak_change_ends(total):
                events.append(Event(EventType.CHANGE_ENDS, player))
            return events

        w = rules.game_winner(self.points, self.config.no_ad)
        if w is not None:
            return self._finish_game(w)
        return [self._point_event(player)]

    def undo(self) -> bool:
        if not self._history:
            return False
        self.__dict__.update(self._history.pop())
        return True

    # ------------------------------------------------------------ internos
    def _snapshot(self) -> dict:
        return {k: copy.deepcopy(v) for k, v in self.__dict__.items() if k != "_history"}

    def _point_data(self) -> dict:
        return {"points": tuple(self.points), "server": self.server}

    def _point_event(self, player: Player) -> Event:
        data = self._point_data()
        if rules.is_deuce(self.points):
            kind = EventType.DECIDING_POINT if self.config.no_ad else EventType.DEUCE
            return Event(kind, player, data)
        holder = rules.advantage_holder(self.points)
        if holder is not None:
            return Event(EventType.ADVANTAGE, holder, data)
        return Event(EventType.POINT, player, data)

    def _begin_set(self) -> None:
        self.games = [0, 0]
        self.points = [0, 0]
        deciding = rules.is_deciding_set(self.sets_won, self.config)
        self.set_rule = rules.tiebreak_rule_for(self.config, deciding)
        self.tiebreak_rule = self.set_rule if (self.set_rule and self.set_rule.replaces_set) else None

    def _finish_game(self, w: Player, tiebreak: Optional[Tuple[int, int]] = None) -> List[Event]:
        self.games[w] += 1
        events = [Event(EventType.GAME, w, {"games": tuple(self.games), "server": self.game_server})]
        replaces_set = tiebreak is not None and self.set_rule is not None and self.set_rule.replaces_set
        set_over = tiebreak is not None or rules.set_winner(self.games) is not None
        total_games = sum(self.games)

        self.game_server = self.game_server.opponent
        self.points = [0, 0]
        self.tiebreak_rule = None

        if set_over:
            result = SetResult(tuple(self.games), w, tiebreak, replaces_set)
            self.sets.append(result)
            events.append(Event(EventType.SET, w, {
                "set_number": len(self.sets), "result": result, "sets_won": self.sets_won,
            }))
            if self.sets_won[w] >= self.config.sets_to_win:
                self.winner = w
                events.append(Event(EventType.MATCH, w, {"sets": list(self.sets)}))
                return events
            if rules.change_ends_after_game(total_games):
                events.append(Event(EventType.CHANGE_ENDS, w))
            self._begin_set()
            return events

        if rules.change_ends_after_game(total_games):
            events.append(Event(EventType.CHANGE_ENDS, w))
        if rules.should_start_tiebreak(self.games, self.set_rule):
            self.tiebreak_rule = self.set_rule
            events.append(Event(EventType.TIEBREAK_START, None, {"games": tuple(self.games)}))
        return events
