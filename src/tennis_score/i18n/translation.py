"""Traduções da interface (textos de botões/menus). As falas do umpire ficam em audio/sentences."""

from ..core.enums import Language

_STRINGS = {
    Language.PT: {
        "app_title": "Contador Automático de Pontos",
        "point_for": "Ponto para {name}",
        "undo": "Desfazer",
        "new_match": "Nova partida",
        "sound_on": "Som: ligado",
        "sound_off": "Som: desligado",
        "language_button": "English",
        "sets_header": "SETS",
        "games_header": "GAMES",
        "points_header": "PTS",
        "tiebreak_header": "TB",
        "serving_deuce": "{name} saca do lado direito (deuce)",
        "serving_ad": "{name} saca do lado esquerdo (vantagem)",
        "change_ends": "↔ Troca de lado",
        "rest_game": "Descanso entre games: {time}",
        "rest_set": "Intervalo entre sets: {time}",
        "rest_over": "Tempo esgotado — podem voltar a jogar",
        "deuce": "Iguais",
        "advantage": "Vantagem {name}",
        "deciding_point": "Ponto decisivo",
        "tiebreak": "Tiebreak",
        "match_over": "Fim de jogo — vitória de {name}",
        "umpire": "Umpire",
        "setup_title": "Nova partida",
        "player_n": "Jogador {n}",
        "format": "Formato",
        "best_of": "Melhor de {n} sets",
        "final_set": "Set decisivo",
        "final_tiebreak7": "Tiebreak de 7 em 6-6",
        "final_tiebreak10": "Tiebreak de 10 em 6-6",
        "final_tiebreak7_12": "Tiebreak de 7 em 12-12",
        "final_advantage": "Sem tiebreak (2 games de diferença)",
        "final_match_tiebreak": "Super tiebreak de 10 no lugar do set",
        "no_ad": "Sem vantagem (ponto decisivo em 40-40)",
        "first_server": "Primeiro sacador",
        "random": "Sorteio",
        "start": "Iniciar",
        "cancel": "Cancelar",
        "cli_help": "Comandos: 1 = ponto jogador 1 | 2 = ponto jogador 2 | u = desfazer | q = sair",
        "cli_prompt": "Ponto para> ",
        "no_tk": "Tkinter não encontrado; usando o modo terminal.",
    },
    Language.EN: {
        "app_title": "Automatic Points Counter",
        "point_for": "Point {name}",
        "undo": "Undo",
        "new_match": "New match",
        "sound_on": "Sound: on",
        "sound_off": "Sound: off",
        "language_button": "Português",
        "sets_header": "SETS",
        "games_header": "GAMES",
        "points_header": "PTS",
        "tiebreak_header": "TB",
        "serving_deuce": "{name} serves from the deuce court",
        "serving_ad": "{name} serves from the ad court",
        "change_ends": "↔ Change ends",
        "rest_game": "Changeover rest: {time}",
        "rest_set": "Set break: {time}",
        "rest_over": "Time is up — resume play",
        "deuce": "Deuce",
        "advantage": "Advantage {name}",
        "deciding_point": "Deciding point",
        "tiebreak": "Tiebreak",
        "match_over": "Game over — {name} wins",
        "umpire": "Umpire",
        "setup_title": "New match",
        "player_n": "Player {n}",
        "format": "Format",
        "best_of": "Best of {n} sets",
        "final_set": "Deciding set",
        "final_tiebreak7": "7-point tiebreak at 6-6",
        "final_tiebreak10": "10-point tiebreak at 6-6",
        "final_tiebreak7_12": "7-point tiebreak at 12-12",
        "final_advantage": "No tiebreak (win by 2 games)",
        "final_match_tiebreak": "10-point match tiebreak instead of set",
        "no_ad": "No-ad (deciding point at 40-40)",
        "first_server": "First server",
        "random": "Random",
        "start": "Start",
        "cancel": "Cancel",
        "cli_help": "Commands: 1 = point player 1 | 2 = point player 2 | u = undo | q = quit",
        "cli_prompt": "Point to> ",
        "no_tk": "Tkinter not found; falling back to terminal mode.",
    },
}

_current = Language.PT


def set_language(language: Language) -> None:
    global _current
    _current = Language(language)


def get_language() -> Language:
    return _current


def t(key: str, **kwargs) -> str:
    text = _STRINGS[_current].get(key) or _STRINGS[Language.EN].get(key, key)
    return text.format(**kwargs) if kwargs else text


def all_translations(key: str, **kwargs) -> set:
    """O mesmo texto em todos os idiomas (serve para reconhecer um texto padrão já traduzido)."""
    return {(s[key].format(**kwargs) if kwargs else s[key]) for s in _STRINGS.values() if key in s}