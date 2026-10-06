"""Umpire: transforma eventos do placar em frases faladas, usando os templates em sentences/."""

import json
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

from ..core.enums import EventType, Language, Player
from ..core.rules import POINT_NAMES
from ..core.score import Event, Score

SENTENCES_DIR = Path(__file__).parent / "sentences"


def load_sentences(language: Language) -> dict:
    with open(SENTENCES_DIR / language.sentences_file, encoding="utf-8") as f:
        return json.load(f)


class Umpire:
    def __init__(self, names: Sequence[str] = ("Player 1", "Player 2"), language: Language = Language.EN):
        self.names = list(names)
        self.set_language(language)

    def set_language(self, language: Language) -> None:
        self.language = Language(language)
        data = load_sentences(self.language)
        self._words: List[str] = data["point_words"]
        self._ordinals: List[str] = data["ordinals"]
        self._counts: List[str] = data["count_words"]
        self._tpl: Dict[str, str] = data["templates"]
        self._clip_names: Dict[str, str] = data.get("clips", {})

    def set_names(self, names: Sequence[str]) -> None:
        self.names = list(names)

    # ------------------------------------------------------------ API
    def opening(self, score: Score) -> str:
        return self._tpl["serve"].format(player=self.names[score.server])

    def announce(self, events: Sequence[Event], score: Score) -> List[str]:
        """Devolve as frases a falar para os eventos de um ponto (só o que é necessário)."""
        types = {e.type for e in events}
        phrases: List[str] = []
        for e in events:
            t = e.type
            if t == EventType.MATCH:
                phrases.append(self._match(e))
            elif t == EventType.SET and EventType.MATCH not in types:
                phrases.append(self._set(e))
            elif t == EventType.GAME and not ({EventType.SET, EventType.MATCH} & types):
                phrases.append(self._game(e))
            elif t in (EventType.POINT, EventType.TIEBREAK_POINT):
                phrases.append(self._point(e, tiebreak=t == EventType.TIEBREAK_POINT))
            elif t == EventType.DEUCE:
                phrases.append(self._tpl["deuce"])
            elif t == EventType.DECIDING_POINT:
                phrases.append(self._tpl["deciding_point"])
            elif t == EventType.ADVANTAGE:
                phrases.append(self._tpl["advantage"].format(player=self.names[e.player]))
            elif t == EventType.TIEBREAK_START:
                phrases.append(self._tpl["tiebreak_start"])
        return phrases

    def clips(self, events: Sequence[Event]) -> List[Tuple[str, ...]]:
        """Áudios gravados a tocar para os eventos de um ponto (o que não tem gravação fica de fora).

        Cada item é uma tupla de chaves em ordem de preferência. Os placares seguem a leitura do
        umpire, sempre com o sacador primeiro: "15-0" = sacador 15, recebedor 0.
        """
        types = {e.type for e in events}
        cues: List[Tuple[str, ...]] = []
        for e in events:
            if e.type == EventType.POINT:
                server: Player = e.data["server"]
                s, r = e.data["points"][server], e.data["points"][server.opponent]
                cues.append((f"{POINT_NAMES[min(s, 3)]}-{POINT_NAMES[min(r, 3)]}",))
            elif e.type == EventType.DEUCE:
                # idiomas com áudio próprio de "deuce" (inglês) usam ele; os demais cantam 40-40
                cues.append(tuple(k for k in (self._clip_names.get("deuce"), "40-40") if k))
            elif e.type == EventType.DECIDING_POINT:
                # sem áudio próprio de "ponto decisivo", cantar o placar 40-40 ainda informa
                cues.append(tuple(k for k in (self._clip_names.get("deciding_point"), "40-40") if k))
            elif e.type == EventType.ADVANTAGE and "advantage" in self._clip_names:
                cues.append((self._clip_names["advantage"],))
            elif e.type == EventType.MATCH and "match" in self._clip_names:
                cues.append((self._clip_names["match"],))
            elif (e.type == EventType.SET and EventType.MATCH not in types
                  or e.type == EventType.GAME and not ({EventType.SET, EventType.MATCH} & types)):
                if "game" in self._clip_names:
                    cues.append((self._clip_names["game"],))
        return cues

    # ------------------------------------------------------------ frases
    def _point(self, e: Event, tiebreak: bool) -> str:
        server: Player = e.data["server"]
        p = e.data["points"]
        s, r = p[server], p[server.opponent]
        fmt = (lambda n: str(n)) if tiebreak else (lambda n: self._words[n])
        if s == r:
            return self._tpl["tiebreak_all" if tiebreak else "point_all"].format(points=fmt(s))
        return self._tpl["tiebreak_point" if tiebreak else "point"].format(
            server_points=fmt(s), receiver_points=fmt(r))

    def _game(self, e: Event) -> str:
        g = e.data["games"]
        w = e.player
        name = self.names[w]
        if g[0] == g[1]:
            return self._tpl["game_all"].format(player=name, n=g[0])
        leader = Player.ONE if g[0] > g[1] else Player.TWO
        return self._tpl["game_leads"].format(
            player=name, leader=self.names[leader], high=max(g), low=min(g))

    def _set(self, e: Event) -> str:
        w = e.player
        result = e.data["result"]
        mine, theirs = result.score_for(w)
        text = self._tpl["set"].format(
            ordinal=self._ordinals[e.data["set_number"] - 1], player=self.names[w],
            high=mine, low=theirs)
        won = e.data["sets_won"]
        if won[0] == won[1]:
            text += " " + self._tpl["sets_all"].format(n=self._counts[won[0]])
        else:
            leader = Player.ONE if won[0] > won[1] else Player.TWO
            text += " " + self._tpl["sets_leads"].format(
                leader=self.names[leader], high=self._counts[max(won)], low=self._counts[min(won)])
        return text

    def _match(self, e: Event) -> str:
        w = e.player
        parts = []
        for result in e.data["sets"]:
            a, b = result.score_for(w)
            parts.append(self._tpl["set_score"].format(a=a, b=b))
        return self._tpl["match"].format(
            player=self.names[w], scores=self._tpl["set_score_join"].join(parts))