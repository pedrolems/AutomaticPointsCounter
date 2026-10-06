"""Enumerações do projeto.

Um Enum é uma lista fechada de valores com nome. Em vez de espalhar "strings mágicas"
("p1", "deuce", "en"...) ou números soltos (0, 1) pelo código, damos nome a cada opção.
Isso evita erros de digitação, deixa o código legível e permite que o editor/IDE
autocomplete e que o Python reclame quando um valor não existe.
"""

from enum import Enum, IntEnum


class Player(IntEnum):
    """Os dois jogadores. É IntEnum para poder ser usado direto como índice de lista."""

    ONE = 0
    TWO = 1

    @property
    def opponent(self) -> "Player":
        return Player(1 - self.value)


class FinalSetFormat(str, Enum):
    """Como o set decisivo é decidido (varia por torneio)."""

    TIEBREAK_7 = "tiebreak7"            # tiebreak de 7 pontos em 6-6 (padrão ATP/WTA)
    TIEBREAK_10 = "tiebreak10"          # tiebreak de 10 pontos em 6-6 (Grand Slams atuais)
    TIEBREAK_7_AT_12 = "tiebreak7_12"   # tiebreak de 7 pontos em 12-12 (estilo Wimbledon antigo)
    ADVANTAGE = "advantage"             # sem tiebreak: vence quem abrir 2 games (Roland Garros antigo)
    MATCH_TIEBREAK = "match_tiebreak"   # super tiebreak de 10 pontos no lugar do set (duplas, Laver Cup)


class EventType(Enum):
    """Tipos de evento gerados a cada ponto. O umpire e a UI reagem a eles."""

    POINT = "point"                     # ponto normal dentro de um game
    DEUCE = "deuce"
    ADVANTAGE = "advantage"
    DECIDING_POINT = "deciding_point"   # ponto decisivo (formato no-ad em 40-40)
    TIEBREAK_POINT = "tiebreak_point"
    GAME = "game"
    SET = "set"
    MATCH = "match"
    TIEBREAK_START = "tiebreak_start"
    CHANGE_ENDS = "change_ends"


class CourtSide(Enum):
    """Lado da quadra de onde o sacador saca."""

    DEUCE = "deuce"   # lado direito (pontos pares)
    AD = "ad"         # lado esquerdo (pontos ímpares)


class Language(str, Enum):
    """Idiomas suportados e o arquivo de frases do umpire de cada um."""

    PT = "pt"
    EN = "en"

    @property
    def sentences_file(self) -> str:
        return {"pt": "portuguese.json", "en": "english.json"}[self.value]

    @property
    def audio_dir(self) -> str:
        """Pasta (dentro de assets/audio) com os áudios gravados do idioma."""
        return {"pt": "pt-br", "en": "en"}[self.value]