"""Interface gráfica (Tkinter): placar, nomes, indicador de saque e botões de ponto."""

import math
import random
import time
import tkinter as tk
from tkinter import ttk
from typing import List, Optional, Sequence

from ..audio import TTS, Umpire
from ..core.enums import FinalSetFormat, Language, Player
from ..core.rules import MatchConfig
from ..core.score import MatchOver, Score
from ..i18n import all_translations, get_language, set_language, t
from .common import has_change_ends, rest_period, serving_text, set_cell, situation_text

BG = "#10271b"
PANEL = "#17382a"
PANEL_ACTIVE = "#1f4d39"
FG = "#f2f5f3"
MUTED = "#8fb3a0"
ACCENT = "#f4d03f"
BTN = "#2e7d5b"
BTN_ACTIVE = "#3a9a70"

FINAL_SET_KEYS = {
    FinalSetFormat.TIEBREAK_7: "final_tiebreak7",
    FinalSetFormat.TIEBREAK_10: "final_tiebreak10",
    FinalSetFormat.TIEBREAK_7_AT_12: "final_tiebreak7_12",
    FinalSetFormat.ADVANTAGE: "final_advantage",
    FinalSetFormat.MATCH_TIEBREAK: "final_match_tiebreak",
}


class ScoreboardApp(tk.Tk):
    def __init__(self, config: MatchConfig, names: Sequence[str], first_server: Optional[Player],
                 language: Language, sound: bool = True):
        super().__init__()
        self.config_ = config
        self.names: List[str] = list(names)
        self.first_server = first_server
        set_language(language)
        self.umpire = Umpire(self.names, language)
        self.tts = TTS(language, enabled=sound)
        self.sound = sound
        self.last_call = ""
        self.notice = ""
        self._rest_job = None     # agendamento (after) do cronômetro de descanso
        self._rest_kind = None    # "game" (90 s) ou "set" (120 s); None = sem descanso em andamento
        self._rest_end = 0.0
        self._rest_over = False
        self.score = self._new_score()

        self.configure(bg=BG)
        self.minsize(720, 490)
        self._build()
        self.bind("<Left>", lambda e: self._point(Player.ONE))
        self.bind("<Right>", lambda e: self._point(Player.TWO))
        self.bind("<Control-z>", lambda e: self._undo())
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._start_announcement()
        self.refresh()

    # ------------------------------------------------------------ setup
    def _new_score(self) -> Score:
        server = self.first_server if self.first_server is not None else random.choice(list(Player))
        return Score(self.config_, server)

    def _start_announcement(self) -> None:
        self._last_events = None  # eventos do último ponto (para refazer a fala ao trocar de idioma)
        self.last_call = self.umpire.opening(self.score)
        self.tts.speak(self.last_call)

    def _build(self) -> None:
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=16, pady=(12, 0))
        self.title_lbl = tk.Label(top, fg=ACCENT, bg=BG, font=("Helvetica", 16, "bold"))
        self.title_lbl.pack(side="left")
        self.lang_btn = self._small_button(top, self._toggle_language)
        self.sound_btn = self._small_button(top, self._toggle_sound)
        self.new_btn = self._small_button(top, self._new_match)
        self.undo_btn = self._small_button(top, self._undo)
        for b in (self.lang_btn, self.sound_btn, self.new_btn, self.undo_btn):
            b.pack(side="right", padx=3)

        self.board = tk.Frame(self, bg=PANEL)
        self.board.pack(fill="x", padx=16, pady=14)

        self.situation_lbl = tk.Label(self, fg=ACCENT, bg=BG, font=("Helvetica", 14, "bold"))
        self.situation_lbl.pack()
        self.call_lbl = tk.Label(self, fg=FG, bg=BG, font=("Helvetica", 13, "italic"),
                                 wraplength=680, justify="center")
        self.call_lbl.pack(pady=(4, 0))
        self.serve_lbl = tk.Label(self, fg=MUTED, bg=BG, font=("Helvetica", 10))
        self.serve_lbl.pack(pady=(6, 0))
        self.rest_lbl = tk.Label(self, fg=ACCENT, bg=BG, font=("Helvetica", 18, "bold"))
        self.rest_lbl.pack(pady=(8, 0))

        btns = tk.Frame(self, bg=BG)
        btns.pack(fill="x", padx=16, pady=16, side="bottom")
        btns.columnconfigure((0, 1), weight=1, uniform="b")
        self.point_btns = []
        for p in (Player.ONE, Player.TWO):
            b = tk.Button(btns, bg=BTN, fg="white", activebackground=BTN_ACTIVE, activeforeground="white",
                          font=("Helvetica", 15, "bold"), relief="flat", pady=16, cursor="hand2",
                          command=lambda p=p: self._point(p))
            b.grid(row=0, column=int(p), sticky="ew", padx=6)
            self.point_btns.append(b)

    def _small_button(self, parent, cmd) -> tk.Button:
        return tk.Button(parent, command=cmd, bg=PANEL, fg=FG, activebackground=PANEL_ACTIVE,
                         activeforeground=FG, relief="flat", font=("Helvetica", 10), padx=10, pady=4,
                         cursor="hand2")

    # ------------------------------------------------------------ ações
    def _point(self, player: Player) -> None:
        try:
            events = self.score.point_won(player)
        except MatchOver:
            return
        calls = self.umpire.announce(events, self.score)
        self._last_events = events
        self.last_call = " ".join(calls)
        self.notice = t("change_ends") if has_change_ends(events) else ""
        self.tts.speak(self.last_call, clips=self.umpire.clips(events))
        self._start_rest(rest_period(events))  # um novo ponto sempre encerra o descanso anterior
        self.refresh()

    def _undo(self) -> None:
        if self.score.undo():
            self._last_events = None
            self.last_call, self.notice = "", ""
            self.tts.speak("", interrupt=True)
            self._stop_rest()
            self.refresh()

    def _toggle_language(self) -> None:
        new = Language.EN if get_language() == Language.PT else Language.PT
        set_language(new)
        self.umpire.set_language(new)
        self.tts.set_language(new)
        self._retranslate_state()
        self.refresh()

    def _retranslate_state(self) -> None:
        """Refaz no novo idioma o que já estava escrito: nomes padrão, última fala e aviso."""
        for i, name in enumerate(self.names):
            if name in all_translations("player_n", n=i + 1):  # "Jogador 1" / "Player 1"
                self.names[i] = t("player_n", n=i + 1)
        self.umpire.set_names(self.names)
        if self._last_events is not None:
            self.last_call = " ".join(self.umpire.announce(self._last_events, self.score))
        elif self.last_call:  # ainda é a abertura ("X ao saque"): nenhum ponto foi jogado
            self.last_call = self.umpire.opening(self.score)
        if self.notice:
            self.notice = t("change_ends")

    def _toggle_sound(self) -> None:
        self.sound = not self.sound
        self.tts.set_enabled(self.sound)
        self.refresh()

    def _new_match(self) -> None:
        dlg = NewMatchDialog(self, self.names, self.config_)
        self.wait_window(dlg)
        if dlg.result:
            self.names, self.config_, self.first_server = dlg.result
            self.umpire.set_names(self.names)
            self.score = self._new_score()
            self.notice = ""
            self._stop_rest()
            self._start_announcement()
            self.refresh()

    # ------------------------------------------------------------ descanso (cronômetro)
    def _start_rest(self, rest) -> None:
        """Inicia o descanso `("game"|"set", segundos)`; None só cancela o que estiver rodando."""
        self._stop_rest()
        if rest is None:
            return
        self._rest_kind, seconds = rest
        self._rest_end = time.monotonic() + seconds
        self._tick_rest()

    def _stop_rest(self) -> None:
        if self._rest_job is not None:
            self.after_cancel(self._rest_job)
            self._rest_job = None
        self._rest_kind = None
        self._rest_over = False

    def _tick_rest(self) -> None:
        if self._rest_end - time.monotonic() <= 0:
            self._rest_job = None
            self._rest_over = True
            self.bell()
        else:
            self._rest_job = self.after(200, self._tick_rest)
        self.rest_lbl.config(text=self._rest_text())

    def _rest_text(self) -> str:
        if self._rest_kind is None:
            return " "
        if self._rest_over:
            return t("rest_over")
        left = max(0, math.ceil(self._rest_end - time.monotonic()))
        return t("rest_set" if self._rest_kind == "set" else "rest_game", time=f"{left // 60:02d}:{left % 60:02d}")

    def _close(self) -> None:
        self._stop_rest()
        self.tts.shutdown()
        self.destroy()

    # ------------------------------------------------------------ desenho
    def refresh(self) -> None:
        s = self.score
        self.title(t("app_title"))
        self.title_lbl.config(text=t("app_title"))
        self.lang_btn.config(text=t("language_button"))
        self.sound_btn.config(text=t("sound_on") if self.sound else t("sound_off"))
        self.new_btn.config(text=t("new_match"))
        self.undo_btn.config(text=t("undo"), state="normal" if s.can_undo else "disabled")
        for p, b in zip(Player, self.point_btns):
            b.config(text=t("point_for", name=self.names[p]), state="disabled" if s.is_over else "normal")

        self._draw_board()
        situation = situation_text(s, self.names)
        self.situation_lbl.config(text="   ".join(x for x in (situation, self.notice) if x) or " ")
        self.call_lbl.config(text=f"{t('umpire')}: “{self.last_call}”" if self.last_call else " ")
        self.serve_lbl.config(text=serving_text(s, self.names) or " ")
        self.rest_lbl.config(text=self._rest_text())

    def _draw_board(self) -> None:
        for w in self.board.winfo_children():
            w.destroy()
        s = self.score
        over = s.is_over
        labels = [str(i + 1) for i in range(len(s.sets))]
        cur_col = 2 + len(s.sets)
        pts_col = cur_col + (0 if over else 1)
        self.board.columnconfigure(1, weight=1)

        head = {"font": ("Helvetica", 9, "bold"), "fg": MUTED, "bg": PANEL}
        for i, txt in enumerate(labels):
            tk.Label(self.board, text=f"S{txt}", **head).grid(row=0, column=2 + i, padx=10, pady=(8, 0))
        if not over:
            tk.Label(self.board, text=t("games_header"), **head).grid(row=0, column=cur_col, padx=10, pady=(8, 0))
            header = t("tiebreak_header") if s.in_tiebreak else t("points_header")
            tk.Label(self.board, text=header, **head).grid(row=0, column=pts_col, padx=14, pady=(8, 0))

        pts = s.point_labels()
        for p in Player:
            row = 1 + int(p)
            is_server = (p == s.server) and not over
            # indicador discreto de saque: pequena bolinha antes do nome
            tk.Label(self.board, text="●" if is_server else " ", fg=ACCENT, bg=PANEL,
                     font=("Helvetica", 9)).grid(row=row, column=0, padx=(14, 2), pady=8)
            is_winner = over and s.winner == p
            tk.Label(self.board, text=self.names[p], fg=ACCENT if is_winner else FG, bg=PANEL,
                     font=("Helvetica", 22, "bold"), anchor="w").grid(row=row, column=1, sticky="w", padx=4)
            for i, r in enumerate(s.sets):
                bold = "bold" if r.winner == p else "normal"
                tk.Label(self.board, text=set_cell(r, p), fg=FG, bg=PANEL,
                         font=("Helvetica", 22, bold), width=3).grid(row=row, column=2 + i, padx=6)
            if not over:
                tk.Label(self.board, text=str(s.games[p]), fg=FG, bg=PANEL_ACTIVE,
                         font=("Helvetica", 26, "bold"), width=3).grid(row=row, column=cur_col, padx=6)
                tk.Label(self.board, text=pts[p], fg=ACCENT, bg=BG,
                         font=("Helvetica", 30, "bold"), width=3).grid(row=row, column=pts_col, padx=(10, 14))
        tk.Frame(self.board, bg=PANEL, height=6).grid(row=3, column=0)


class NewMatchDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, names: Sequence[str], config: MatchConfig):
        super().__init__(parent)
        self.title(t("setup_title"))
        self.configure(bg=BG, padx=20, pady=16)
        self.transient(parent)
        self.resizable(False, False)
        self.result = None

        self.n1 = tk.StringVar(value=names[0])
        self.n2 = tk.StringVar(value=names[1])
        self.best_of = tk.IntVar(value=config.best_of)
        self.final = tk.StringVar(value=config.final_set.value)
        self.no_ad = tk.BooleanVar(value=config.no_ad)
        self.server = tk.StringVar(value="random")

        def label(text, row):
            tk.Label(self, text=text, fg=MUTED, bg=BG, anchor="w").grid(row=row, column=0, sticky="w", pady=4)

        for i, var in enumerate((self.n1, self.n2)):
            label(t("player_n", n=i + 1), i)
            tk.Entry(self, textvariable=var, width=26).grid(row=i, column=1, columnspan=2, sticky="ew", pady=4)

        label(t("format"), 2)
        for col, n in enumerate((3, 5), start=1):
            tk.Radiobutton(self, text=t("best_of", n=n), variable=self.best_of, value=n, fg=FG, bg=BG,
                           selectcolor=PANEL, activebackground=BG, activeforeground=FG).grid(row=2, column=col, sticky="w")

        label(t("final_set"), 3)
        self._final_map = {t(k): f for f, k in FINAL_SET_KEYS.items()}
        self.final_box = ttk.Combobox(self, state="readonly", width=34, values=list(self._final_map))
        self.final_box.set(t(FINAL_SET_KEYS[config.final_set]))
        self.final_box.grid(row=3, column=1, columnspan=2, sticky="ew", pady=4)

        tk.Checkbutton(self, text=t("no_ad"), variable=self.no_ad, fg=FG, bg=BG, selectcolor=PANEL,
                       activebackground=BG, activeforeground=FG).grid(row=4, column=0, columnspan=3, sticky="w")

        label(t("first_server"), 5)
        opts = tk.Frame(self, bg=BG)
        opts.grid(row=5, column=1, columnspan=2, sticky="w")
        for val, txt in (("0", "1"), ("1", "2"), ("random", t("random"))):
            tk.Radiobutton(opts, text=txt, variable=self.server, value=val, fg=FG, bg=BG, selectcolor=PANEL,
                           activebackground=BG, activeforeground=FG).pack(side="left", padx=4)

        bar = tk.Frame(self, bg=BG)
        bar.grid(row=6, column=0, columnspan=3, pady=(14, 0), sticky="e")
        tk.Button(bar, text=t("cancel"), command=self.destroy).pack(side="left", padx=4)
        tk.Button(bar, text=t("start"), command=self._ok, bg=BTN, fg="white").pack(side="left", padx=4)
        self.grab_set()

    def _ok(self) -> None:
        names = [self.n1.get().strip() or t("player_n", n=1), self.n2.get().strip() or t("player_n", n=2)]
        cfg = MatchConfig(best_of=self.best_of.get(),
                          final_set=self._final_map[self.final_box.get()],
                          no_ad=self.no_ad.get())
        srv = self.server.get()
        first = None if srv == "random" else Player(int(srv))
        self.result = (names, cfg, first)
        self.destroy()


def run_gui(config: MatchConfig, names: Sequence[str], first_server: Optional[Player],
            language: Language, sound: bool = True) -> None:
    ScoreboardApp(config, names, first_server, language, sound).mainloop()