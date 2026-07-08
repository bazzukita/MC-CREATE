import os
import re
import threading
import time
from datetime import datetime
import tkinter as tk
import tkinter.filedialog as fd
import tkinter.messagebox as mb

import customtkinter as ctk
import pystray
from PIL import Image

# RAM options: label → MB
RAM_OPTIONS = {
    "512 MB":            512,
    "1 GB  (1 024 MB)":  1024,
    "2 GB  (2 048 MB)":  2048,
    "4 GB  (4 096 MB)":  4096,
    "8 GB  (8 192 MB)":  8192,
    "16 GB (16 384 MB)": 16384,
    "24 GB (24 576 MB)": 24576,
    "32 GB (32 768 MB)": 32768,
    "Personalizado":     -1,
}
RAM_LABELS = list(RAM_OPTIONS.keys())

def mb_to_label(mb: int) -> str:
    if mb >= 1024:
        gb = mb / 1024
        return f"{gb:.0f} GB" if gb == int(gb) else f"{gb:.1f} GB"
    return f"{mb} MB"

from server_manager import JavaNotFoundError, JavaVersionError, ServerManager




SERVER_TYPES = ["Vanilla", "Paper", "Fabric", "Forge"]

DIFFICULTY_OPTIONS = ["peaceful", "easy", "normal", "hard"]
GAMEMODE_OPTIONS   = ["survival", "creative", "adventure", "spectator"]


# ── Info card ─────────────────────────────────────────────────────────────────

class InfoCard(ctk.CTkFrame):
    def __init__(self, parent, label, value="—", icon="", on_click=None, **kwargs):
        super().__init__(parent, corner_radius=10, **kwargs)
        self._label_text = (icon + " " + label) if icon else label
        self._lbl = ctk.CTkLabel(self, text=self._label_text,
                                  font=ctk.CTkFont(size=10), text_color="gray55")
        self._lbl.pack(pady=(10, 0), padx=12)
        self._val = ctk.CTkLabel(self, text=value, font=ctk.CTkFont(size=16, weight="bold"))
        self._val.pack(pady=(2, 10), padx=12)

        if on_click:
            self.configure(cursor="hand2")
            for w in (self, self._lbl, self._val):
                w.bind("<Button-1>", lambda e: on_click())
                w.bind("<Enter>", lambda e: self._val.configure(text_color="#52e07a"))
                w.bind("<Leave>", lambda e: self._val.configure(text_color=("gray10", "gray90")))

    def set(self, value):
        self._val.configure(text=value)


# ── Main app ──────────────────────────────────────────────────────────────────

class MCCreateApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("MC Create")
        self.geometry("1150x720")
        self.minsize(960, 600)

        self.manager = ServerManager()
        self.selected_server = None
        self._java_upgrade_offered: dict[str, bool] = {}
        self._start_times: dict[str, float] = {}
        self._player_counts: dict[str, int] = {}
        self._uptime_job = None
        self._auto_backup_timers: dict[str, object] = {}
        self._console_buffers: dict[str, str] = {}
        self._tray_icon = None

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        self._refresh_list()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ── Sidebar ──
        sidebar = ctk.CTkFrame(self, width=230, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.grid_rowconfigure(2, weight=1)
        sidebar.grid_columnconfigure(0, weight=1)

        logo_frame = ctk.CTkFrame(sidebar, fg_color=("#1a6b2e", "#1a6b2e"), corner_radius=0)
        logo_frame.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(logo_frame, text="⛏  MC Create",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color="white").pack(pady=18, padx=20)

        ctk.CTkLabel(sidebar, text="SERVIDORES",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="gray50").grid(row=1, column=0, padx=16, pady=(14, 4), sticky="w")

        self.list_frame = ctk.CTkScrollableFrame(sidebar, fg_color="transparent")
        self.list_frame.grid(row=2, column=0, padx=8, pady=0, sticky="nsew")
        self.list_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            sidebar, text="＋  Nuevo servidor",
            command=self._open_create, height=38,
            font=ctk.CTkFont(size=13)
        ).grid(row=3, column=0, padx=12, pady=14, sticky="ew")

        # ── Main panel ──
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=12, pady=12)
        main.grid_rowconfigure(3, weight=1)
        main.grid_columnconfigure(0, weight=1)

        # Header
        header = ctk.CTkFrame(main, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        header.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(
            header, text="Selecciona un servidor",
            font=ctk.CTkFont(size=20, weight="bold"), anchor="w")
        self.title_label.grid(row=0, column=0, sticky="w")

        self.status_dot = ctk.CTkLabel(
            header, text="● Detenido",
            text_color="#e05252", font=ctk.CTkFont(size=13))
        self.status_dot.grid(row=1, column=0, sticky="w")

        # Controls bar
        bar = ctk.CTkFrame(main, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="ew", pady=(0, 10))

        self.btn_start = ctk.CTkButton(
            bar, text="▶  Iniciar", width=110, height=36,
            font=ctk.CTkFont(size=13), command=self._start, state="disabled")
        self.btn_start.pack(side="left", padx=(0, 5))

        self.btn_stop = ctk.CTkButton(
            bar, text="■  Detener", width=110, height=36,
            font=ctk.CTkFont(size=13), command=self._stop, state="disabled",
            fg_color="#c0392b", hover_color="#922b21")
        self.btn_stop.pack(side="left", padx=(0, 5))

        self.btn_kill = ctk.CTkButton(
            bar, text="⚡ Kill", width=100, height=36,
            font=ctk.CTkFont(size=13), command=self._kill, state="disabled",
            fg_color="#7d3c98", hover_color="#5b2c6f")
        self.btn_kill.pack(side="left", padx=(0, 5))

        self.btn_mods = ctk.CTkButton(
            bar, text="🧩  Mods", width=100, height=36,
            font=ctk.CTkFont(size=13), command=self._open_mods, state="disabled",
            fg_color="#2e6b4f", hover_color="#1e4b35")
        self.btn_mods.pack(side="left", padx=(0, 5))

        self.btn_players = ctk.CTkButton(
            bar, text="👥  Jugadores", width=115, height=36,
            font=ctk.CTkFont(size=13), command=self._open_players, state="disabled",
            fg_color="#1a5276", hover_color="#154360")
        self.btn_players.pack(side="left", padx=(0, 5))

        self.btn_backup = ctk.CTkButton(
            bar, text="💾  Backup", width=100, height=36,
            font=ctk.CTkFont(size=13), command=self._open_backup, state="disabled",
            fg_color="#6d4c1a", hover_color="#4d340e")
        self.btn_backup.pack(side="left", padx=(0, 5))

        self.btn_folder = ctk.CTkButton(
            bar, text="📁  Carpeta", width=100, height=36,
            font=ctk.CTkFont(size=13), command=self._open_folder, state="disabled",
            fg_color="#2d6a8f", hover_color="#1d4a6f")
        self.btn_folder.pack(side="left", padx=(0, 5))

        self.btn_props = ctk.CTkButton(
            bar, text="⚙  Ajustes", width=100, height=36,
            font=ctk.CTkFont(size=13), command=self._open_settings, state="disabled",
            fg_color="#5a5a5a", hover_color="#3a3a3a")
        self.btn_props.pack(side="left", padx=(0, 5))

        self.btn_delete = ctk.CTkButton(
            bar, text="🗑  Eliminar", width=100, height=36,
            font=ctk.CTkFont(size=13), command=self._delete, state="disabled",
            fg_color="#5a1a1a", hover_color="#3a0a0a")
        self.btn_delete.pack(side="right")

        # Info cards — fila 1 (4 cards) + fila 2 (3 cards)
        cards_outer = ctk.CTkFrame(main, fg_color="transparent")
        cards_outer.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        cards_outer.grid_columnconfigure(0, weight=1)

        row1 = ctk.CTkFrame(cards_outer, fg_color="transparent")
        row1.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        for i in range(4):
            row1.grid_columnconfigure(i, weight=1)

        row2 = ctk.CTkFrame(cards_outer, fg_color="transparent")
        row2.grid(row=1, column=0, sticky="ew")
        for i in range(3):
            row2.grid_columnconfigure(i, weight=1)

        self.card_ip      = InfoCard(row1, "IP LOCAL",  "—", "🌐", on_click=self._copy_ip_port)
        self.card_port    = InfoCard(row1, "PUERTO",    "—", "🔌", on_click=self._edit_port)
        self.card_ram   = InfoCard(row1, "RAM",     "—", "💾", on_click=self._edit_ram)
        self.card_cores = InfoCard(row1, "NÚCLEOS", "—", "⚡", on_click=self._edit_cores)

        self.card_ip.grid   (row=0, column=0, padx=4, sticky="ew")
        self.card_port.grid (row=0, column=1, padx=4, sticky="ew")
        self.card_ram.grid  (row=0, column=2, padx=4, sticky="ew")
        self.card_cores.grid(row=0, column=3, padx=4, sticky="ew")

        self.card_version = InfoCard(row2, "VERSIÓN",   "—", "📦")
        self.card_players = InfoCard(row2, "JUGADORES", "—", "👥")
        self.card_uptime  = InfoCard(row2, "TIEMPO",    "—", "⏱")

        self.card_version.grid(row=0, column=0, padx=4, sticky="ew")
        self.card_players.grid(row=0, column=1, padx=4, sticky="ew")
        self.card_uptime.grid (row=0, column=2, padx=4, sticky="ew")

        # Console
        console_frame = ctk.CTkFrame(main)
        console_frame.grid(row=3, column=0, sticky="nsew", pady=(0, 8))
        console_frame.grid_rowconfigure(1, weight=1)
        console_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(console_frame, text="CONSOLA",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="gray50").grid(row=0, column=0, padx=12, pady=(8, 2), sticky="w")

        self.console = ctk.CTkTextbox(
            console_frame, font=ctk.CTkFont(family="Consolas", size=12),
            state="disabled", wrap="word",
            fg_color="#0d0d0d", text_color="#c8ffc8", border_width=0)
        self.console.grid(row=1, column=0, padx=6, pady=(0, 6), sticky="nsew")

        # Command row
        cmd_row = ctk.CTkFrame(main, fg_color="transparent")
        cmd_row.grid(row=4, column=0, sticky="ew")
        cmd_row.grid_columnconfigure(0, weight=1)

        self.cmd_entry = ctk.CTkEntry(
            cmd_row, placeholder_text="Escribe un comando...",
            height=36, font=ctk.CTkFont(size=13))
        self.cmd_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.cmd_entry.bind("<Return>", self._send_cmd)

        ctk.CTkButton(cmd_row, text="Enviar", width=90, height=36,
                      command=self._send_cmd).grid(row=0, column=1)

    # ── Server list ───────────────────────────────────────────────────────────

    def _refresh_list(self):
        for w in self.list_frame.winfo_children():
            w.destroy()

        servers = self.manager.list_servers()
        if not servers:
            ctk.CTkLabel(self.list_frame, text="Sin servidores",
                         text_color="gray55").pack(pady=16)
            return

        for s in servers:
            active = self.manager.is_running(s["name"])
            card = ctk.CTkFrame(self.list_frame, corner_radius=8,
                                fg_color=("#2a6b3a", "#1e4a28") if active else ("gray85", "gray20"))
            card.pack(fill="x", pady=3, padx=2)
            card.grid_columnconfigure(0, weight=1)

            n = ctk.CTkLabel(card, text=s["name"],
                             font=ctk.CTkFont(size=13, weight="bold"), anchor="w")
            n.grid(row=0, column=0, padx=10, pady=(8, 0), sticky="w")
            s_type = s.get("server_type", "vanilla").capitalize()
            i = ctk.CTkLabel(card, text=f"{s_type} v{s['version']}  •  {s['ram']} MB",
                             font=ctk.CTkFont(size=10), text_color="gray60", anchor="w")
            i.grid(row=1, column=0, padx=10, pady=(0, 8), sticky="w")
            d = ctk.CTkLabel(card, text="●" if active else "○",
                             text_color="#52e07a" if active else "gray50",
                             font=ctk.CTkFont(size=14))
            d.grid(row=0, column=1, rowspan=2, padx=10)

            for w in (card, n, i, d):
                w.bind("<Button-1>", lambda e, name=s["name"]: self._select(name))

    def _select(self, name):
        self.selected_server = name
        cfg = self.manager.servers[name]
        self.title_label.configure(text=name)
        for btn in (self.btn_delete, self.btn_folder, self.btn_props,
                    self.btn_mods, self.btn_players, self.btn_backup):
            btn.configure(state="normal")
        self._restart_auto_backup(name)
        s_type = cfg.get("server_type", "vanilla").capitalize()
        self.card_version.set(f"{s_type} {cfg['version']}")
        self.card_ram.set(mb_to_label(cfg["ram"]))
        self.card_port.set(str(self.manager.get_port(name)))
        self.card_ip.set(self.manager.get_local_ip())
        cores = cfg.get("cores")
        self.card_cores.set("Todos" if not cores else f"{cores} núcl.")
        self.card_players.set("0")
        self.card_uptime.set("—")
        running = self.manager.is_running(name)
        self._set_running(running)

        # Cargar buffer de consola de este servidor
        self.console.configure(state="normal")
        self.console.delete("1.0", "end")
        self.console.insert("end", self._console_buffers.get(name, ""))
        self.console.see("end")
        self.console.configure(state="disabled")

        if running and self.manager.is_orphan(name):
            self._log(
                f"[MC Create] Servidor «{name}» detectado en ejecución (sesión anterior).\n"
                "[MC Create] La consola no está disponible. Usa '⚡ Forzar' para detenerlo.\n"
            )


    def _set_running(self, running: bool):
        name = self.selected_server
        if running:
            self.status_dot.configure(text="● Ejecutando", text_color="#52e07a")
            self.btn_start.configure(state="disabled")
            orphan = self.manager.is_orphan(name) if name else False
            self.btn_stop.configure(state="disabled" if orphan else "normal")
            self.btn_kill.configure(state="normal")
        else:
            self.status_dot.configure(text="● Detenido", text_color="#e05252")
            self.btn_start.configure(state="normal" if name else "disabled")
            self.btn_stop.configure(state="disabled")
            self.btn_kill.configure(state="disabled")
            self._stop_uptime()

    # ── Uptime ────────────────────────────────────────────────────────────────

    def _start_uptime(self, name: str):
        self._start_times[name] = time.time()
        self._tick_uptime()

    def _tick_uptime(self):
        name = self.selected_server
        t0 = self._start_times.get(name) if name else None
        if t0 and self.manager.is_running(name):
            e = int(time.time() - t0)
            h, r = divmod(e, 3600)
            m, s = divmod(r, 60)
            self.card_uptime.set(f"{h:02d}:{m:02d}:{s:02d}")
            self._uptime_job = self.after(1000, self._tick_uptime)

    def _stop_uptime(self):
        if self._uptime_job:
            self.after_cancel(self._uptime_job)
            self._uptime_job = None
        self.card_uptime.set("—")

    # ── Actions ───────────────────────────────────────────────────────────────

    def _start(self):
        if not self.selected_server:
            return
        try:
            self.manager.check_java()
            self._do_start()
        except (JavaNotFoundError, JavaVersionError):
            self._download_java_then_start()

    def _download_java_then_start(self):
        self.btn_start.configure(state="disabled")
        self._log("[MC Create] Java no encontrado. Descargando automáticamente...\n")

        def _worker():
            try:
                self.manager.download_java(
                    progress_cb=lambda msg: self.after(0, lambda m=msg: self._log(f"[Java] {m}\n"))
                )
                self.after(0, self._do_start)
            except Exception as e:
                self.after(0, lambda: (
                    self._log(f"[MC Create] Error descargando Java: {e}\n"),
                    self.btn_start.configure(state="normal"),
                ))

        threading.Thread(target=_worker, daemon=True).start()

    def _do_start(self):
        name = self.selected_server
        self._java_upgrade_offered[name] = False
        self._player_counts[name] = 0
        self.card_players.set("0")
        self._log(f"[MC Create] Iniciando «{name}»...\n")
        try:
            ok = self.manager.start_server(
                name,
                output_cb=lambda line, n=name: self._on_server_line(n, line),
            )
        except Exception as e:
            mb.showerror("Error", str(e))
            self.btn_start.configure(state="normal")
            return
        if ok:
            self._set_running(True)
            self._start_uptime(name)
            self._refresh_list()
        else:
            mb.showerror("Error", f"El servidor «{name}» ya está en ejecución.")

    def _stop(self):
        if not self.selected_server:
            return
        self._log("[MC Create] Enviando comando stop...\n")
        self.manager.stop_server(self.selected_server)

    def _kill(self):
        if not self.selected_server:
            return
        if mb.askyesno("Forzar cierre", "¿Terminar el proceso del servidor forzosamente?\nPueden perderse datos no guardados."):
            self._log("[MC Create] Forzando cierre del servidor...\n")
            self.manager.kill_server(self.selected_server)
            self._set_running(False)
            self.card_players.set("0")
            self._refresh_list()

    def _send_cmd(self, _event=None):
        cmd = self.cmd_entry.get().strip()
        if cmd and self.selected_server:
            self.manager.send_command(self.selected_server, cmd)
            self._log(f"> {cmd}\n")
            self.cmd_entry.delete(0, "end")

    def _delete(self):
        if not self.selected_server:
            return
        if mb.askyesno("Confirmar", f"¿Eliminar «{self.selected_server}»?\nSe borrarán todos sus archivos."):
            name = self.selected_server
            self.manager.delete_server(name)
            self._console_buffers.pop(name, None)
            self._player_counts.pop(name, None)
            self._start_times.pop(name, None)
            self.selected_server = None
            self.title_label.configure(text="Selecciona un servidor")
            self._cancel_auto_backup(name)
            for btn in (self.btn_start, self.btn_stop, self.btn_kill,
                        self.btn_delete, self.btn_folder, self.btn_props,
                        self.btn_mods, self.btn_players, self.btn_backup):
                btn.configure(state="disabled")
            for c in (self.card_ip, self.card_port, self.card_ram, self.card_cores,
                      self.card_version, self.card_players, self.card_uptime):
                c.set("—")
            self._refresh_list()

    def _open_folder(self):
        if self.selected_server:
            os.startfile(self.manager.servers[self.selected_server]["path"])

    def _open_settings(self):
        if self.selected_server:
            ServerSettingsDialog(self, self.manager, self.selected_server)

    def _copy_ip_port(self):
        if not self.selected_server:
            return
        ip = self.manager.get_local_ip()
        port = self.manager.get_port(self.selected_server)
        text = f"{ip}:{port}"
        self.clipboard_clear()
        self.clipboard_append(text)
        self.card_ip.set("¡Copiado! ✓")
        self.after(1500, lambda: self.card_ip.set(ip))

    def _edit_port(self):
        if not self.selected_server:
            return
        current = str(self.manager.get_port(self.selected_server))
        dialog = ctk.CTkInputDialog(text=f"Puerto actual: {current}\nIntroduce el nuevo puerto (1024–65535):",
                                     title="Cambiar puerto")
        value = dialog.get_input()
        if value is None:
            return
        try:
            port = int(value.strip())
            if not (1024 <= port <= 65535):
                raise ValueError
        except ValueError:
            mb.showerror("Error", "Puerto inválido. Usa un número entre 1024 y 65535.")
            return
        self.manager.update_port(self.selected_server, port)
        self.card_port.set(str(port))
        self._log(f"[MC Create] Puerto cambiado a {port}. Reinicia el servidor para aplicarlo.\n")

    def _open_backup(self):
        if self.selected_server:
            BackupDialog(self, self.manager, self.selected_server,
                         on_interval_change=self._restart_auto_backup)

    def _restart_auto_backup(self, name: str):
        self._cancel_auto_backup(name)
        hours = self.manager.get_auto_backup_hours(name)
        if hours > 0:
            t = threading.Timer(hours * 3600, lambda: self._do_auto_backup(name))
            t.daemon = True
            t.start()
            self._auto_backup_timers[name] = t

    def _cancel_auto_backup(self, name: str = None):
        if name:
            t = self._auto_backup_timers.pop(name, None)
            if t:
                t.cancel()
        else:
            for t in self._auto_backup_timers.values():
                t.cancel()
            self._auto_backup_timers.clear()

    def _do_auto_backup(self, name: str):
        was_running = self.manager.is_running(name)
        self._log("[MC Create] Creando backup automático...\n")
        def _worker():
            try:
                self.manager.create_backup(name, auto=True)
                self.after(0, lambda: self._log("[MC Create] Backup automático guardado.\n"))
            except Exception as e:
                self.after(0, lambda err=e: self._log(f"[MC Create] Error en backup automático: {err}\n"))

            if was_running and not self.manager.is_running(name):
                # Avisos previos al reinicio
                try:
                    self.manager.send_command(name, "say [MC Create] ⚠ El servidor se reiniciará en 5 minutos")
                    self.after(0, lambda: self._log("[MC Create] Aviso 1: Reinicio en 5 minutos\n"))
                except Exception:
                    pass

                time.sleep(180)  # Esperar 3 minutos

                try:
                    self.manager.send_command(name, "say [MC Create] ⚠ El servidor se reiniciará en 2 minutos")
                    self.after(0, lambda: self._log("[MC Create] Aviso 2: Reinicio en 2 minutos\n"))
                except Exception:
                    pass

                time.sleep(60)  # Esperar 1 minuto

                try:
                    self.manager.send_command(name, "say [MC Create] ¡El servidor se reinicia ahora!")
                    self.after(0, lambda: self._log("[MC Create] Aviso 3: Reiniciando ahora\n"))
                except Exception:
                    pass

                time.sleep(1)

                # Parar y reiniciar
                try:
                    self.manager.stop_server(name)
                    time.sleep(5)
                    self.manager.start_server(name, output_cb=self._log)
                    self.after(0, lambda: self._log("[MC Create] Servidor reiniciado después del backup.\n"))
                except Exception as e:
                    self.after(0, lambda err=e: self._log(f"[MC Create] Error reiniciando servidor: {err}\n"))

            self.after(0, lambda: self._restart_auto_backup(name))
        threading.Thread(target=_worker, daemon=True).start()

    def _edit_ram(self):
        if not self.selected_server:
            return
        current_mb = self.manager.servers[self.selected_server]["ram"]
        RamDialog(self, self.manager, self.selected_server, current_mb,
                  on_done=lambda mb_val: (
                      self.card_ram.set(mb_to_label(mb_val)),
                      self._log(f"[MC Create] RAM cambiada a {mb_to_label(mb_val)}. Reinicia para aplicarlo.\n"),
                  ))

    def _edit_cores(self):
        if not self.selected_server:
            return
        current = self.manager.servers[self.selected_server].get("cores")
        CoresDialog(self, self.manager, self.selected_server, current,
                    on_done=lambda cores: (
                        self.card_cores.set("Todos" if not cores else f"{cores} núcl."),
                        self._log(f"[MC Create] Núcleos cambiados a {'todos' if not cores else cores}. Reinicia para aplicarlo.\n"),
                    ))

    def _open_mods(self):
        if self.selected_server:
            ModsDialog(self, self.manager, self.selected_server)

    def _open_players(self):
        if self.selected_server:
            PlayersDialog(self, self.manager, self.selected_server)

    # ── Console + log parsing ─────────────────────────────────────────────────

    def _on_server_line(self, name: str, text: str):
        # Acumular en buffer aunque no sea el servidor seleccionado
        self._console_buffers[name] = self._console_buffers.get(name, "") + text

        if re.search(r"joined the game", text):
            self._player_counts[name] = self._player_counts.get(name, 0) + 1
        elif re.search(r"left the game", text):
            self._player_counts[name] = max(0, self._player_counts.get(name, 0) - 1)

        if "El proceso del servidor ha terminado" in text:
            self.after(0, lambda n=name: self._on_server_stopped(n))

        # Solo actualizar UI si es el servidor actualmente visible
        if name == self.selected_server:
            count = self._player_counts.get(name, 0)
            self.after(0, lambda c=count: self.card_players.set(str(c)))
            self._log(text)

    def _on_server_stopped(self, name: str):
        self._start_times.pop(name, None)
        if name == self.selected_server:
            self._set_running(False)
        self._refresh_list()
        # Si la app está en el tray y ya no queda ningún servidor, salir
        if self._tray_icon and not self.manager.get_running_servers():
            self._tray_icon.stop()
            self._tray_icon = None
            self._quit_app()

    def _log(self, text: str):
        def _update():
            self.console.configure(state="normal")
            self.console.insert("end", text)
            self.console.see("end")
            self.console.configure(state="disabled")
            if "UnsupportedClassVersionError" in text and not self._java_upgrade_offered.get(self.selected_server):
                self._java_upgrade_offered[self.selected_server] = True
                self.after(300, self._auto_upgrade_java)
        self.after(0, _update)

    def _auto_upgrade_java(self):
        self._log("[MC Create] Versión de Java insuficiente. Descargando la versión correcta...\n")
        self._download_java_then_start()

    # ── Close / tray ──────────────────────────────────────────────────────────

    def _on_close(self):
        if self.manager.get_running_servers():
            self._minimize_to_tray()
        else:
            self._quit_app()

    def _minimize_to_tray(self):
        self.withdraw()
        if self._tray_icon:
            return

        try:
            icon_path = os.path.join(
                getattr(__import__("sys"), "_MEIPASS", os.path.dirname(os.path.abspath(__file__))),
                "icon.ico",
            )
            img = Image.open(icon_path)
        except Exception:
            img = Image.new("RGB", (64, 64), color=(26, 107, 46))

        running = self.manager.get_running_servers()
        active = ", ".join(running) if running else "servidor"
        menu = pystray.Menu(
            pystray.MenuItem("MC Create — " + active, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Abrir", self._restore_from_tray, default=True),
            pystray.MenuItem("Detener servidor y salir", self._stop_and_quit),
        )
        self._tray_icon = pystray.Icon("MC Create", img, "MC Create", menu)
        threading.Thread(target=self._tray_icon.run, daemon=True).start()

    def _restore_from_tray(self, icon=None, item=None):
        if self._tray_icon:
            self._tray_icon.stop()
            self._tray_icon = None
        self.after(0, self.deiconify)

    def _stop_and_quit(self, icon=None, item=None):
        if self._tray_icon:
            self._tray_icon.stop()
            self._tray_icon = None
        for name in self.manager.get_running_servers():
            self.manager.stop_server(name)
        self.after(0, self._quit_app)

    def _quit_app(self):
        self._cancel_auto_backup()
        self.destroy()

    def _open_create(self):
        CreateDialog(self, self.manager, on_done=self._on_created)

    def _on_created(self, name):
        self._refresh_list()
        self._select(name)


# ── Players dialog ────────────────────────────────────────────────────────────

class PlayersDialog(ctk.CTkToplevel):
    def __init__(self, parent, manager: ServerManager, server_name: str):
        super().__init__(parent)
        self.manager     = manager
        self.server_name = server_name

        self.title(f"Jugadores — {server_name}")
        self.geometry("740x520")
        self.resizable(True, True)
        self.minsize(600, 380)
        self.grab_set()
        self.lift()

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 6))
        hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(hdr, text="Gestión de jugadores",
                     font=ctk.CTkFont(size=15, weight="bold")).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(hdr, text="↻  Actualizar", width=110, height=32,
                      command=self._refresh).grid(row=0, column=1)

        # Column labels
        col_hdr = ctk.CTkFrame(self, fg_color="transparent")
        col_hdr.grid(row=0, column=0, sticky="ew", padx=20, pady=(0, 0))
        col_hdr.grid_columnconfigure(0, weight=1)

        # Scrollable list
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 6))
        self.scroll.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(self, text="Cerrar", width=100, height=34,
                      command=self.destroy).grid(row=2, column=0,
                      sticky="e", padx=16, pady=(0, 14))

        self._refresh()

    # ── Build list ────────────────────────────────────────────────────────────

    def _refresh(self):
        for w in self.scroll.winfo_children():
            w.destroy()

        players = self.manager.get_players(self.server_name)

        if not players:
            ctk.CTkLabel(
                self.scroll,
                text="No hay jugadores registrados.\n"
                     "Aparecerán aquí cuando se unan al servidor.",
                text_color="gray55", font=ctk.CTkFont(size=12),
            ).pack(pady=40)
            return

        # Header row
        h = ctk.CTkFrame(self.scroll, fg_color="transparent")
        h.pack(fill="x", padx=6, pady=(2, 4))
        h.grid_columnconfigure(0, weight=1)
        for text, col, w in [
            ("Jugador",   0, 0), ("Horas", 1, 70),
            ("Whitelist", 2, 80), ("Admin", 3, 72), ("Ban", 4, 88),
        ]:
            anchor = "w" if col == 0 else "center"
            lbl = ctk.CTkLabel(h, text=text, font=ctk.CTkFont(size=10, weight="bold"),
                                text_color="gray50", anchor=anchor,
                                width=0 if col == 0 else w)
            if col == 0:
                lbl.grid(row=0, column=0, sticky="w", padx=(10, 0))
            else:
                lbl.grid(row=0, column=col, padx=2)

        for p in players:
            self._player_row(p)

    def _player_row(self, p: dict):
        row = ctk.CTkFrame(self.scroll, corner_radius=8)
        row.pack(fill="x", pady=3, padx=2)
        row.grid_columnconfigure(0, weight=1)

        # Name
        name_col = ctk.CTkFrame(row, fg_color="transparent")
        name_col.grid(row=0, column=0, sticky="w", padx=(12, 4), pady=10)
        ctk.CTkLabel(name_col, text=f"👤  {p['name']}",
                     font=ctk.CTkFont(size=13, weight="bold"), anchor="w").pack(anchor="w")
        if p["banned"]:
            ctk.CTkLabel(name_col, text="🚫 Baneado",
                         font=ctk.CTkFont(size=10), text_color="#e74c3c").pack(anchor="w")
        elif p["op"]:
            ctk.CTkLabel(name_col, text="⭐ Admin",
                         font=ctk.CTkFont(size=10), text_color="#e67e22").pack(anchor="w")

        # Hours
        h = p["hours"]
        if h >= 1:
            h_str = f"{h:.1f}h"
        else:
            m = h * 60
            h_str = f"{m:.0f}m" if m >= 1 else "<1m"
        ctk.CTkLabel(row, text=h_str, width=70, anchor="center",
                     font=ctk.CTkFont(size=12), text_color="gray60").grid(
            row=0, column=1, padx=2)

        # Whitelist toggle
        wl_on = p["whitelisted"]
        ctk.CTkButton(
            row, text="✓" if wl_on else "✗", width=72, height=30,
            font=ctk.CTkFont(size=15),
            fg_color=("#27ae60","#1e8449") if wl_on else ("#e74c3c","#c0392b"),
            hover_color="#1e8449" if wl_on else "#c0392b",
            command=lambda p=p: self._toggle_whitelist(p),
        ).grid(row=0, column=2, padx=2)

        # Op toggle
        op_on = p["op"]
        ctk.CTkButton(
            row, text="⭐" if op_on else "☆", width=64, height=30,
            font=ctk.CTkFont(size=14),
            fg_color=("#e67e22","#d35400") if op_on else "gray30",
            hover_color="#d35400" if op_on else "gray20",
            command=lambda p=p: self._toggle_op(p),
        ).grid(row=0, column=3, padx=2)

        # Ban toggle
        ban_on = p["banned"]
        ctk.CTkButton(
            row, text="Desbanear" if ban_on else "Banear", width=82, height=30,
            font=ctk.CTkFont(size=11),
            fg_color=("#27ae60","#1e8449") if ban_on else ("#7d3c98","#5b2c6f"),
            hover_color="#1e8449" if ban_on else "#5b2c6f",
            command=lambda p=p: self._toggle_ban(p),
        ).grid(row=0, column=4, padx=(2, 10))

    # ── Actions ───────────────────────────────────────────────────────────────

    def _toggle_whitelist(self, p):
        if p["whitelisted"]:
            self.manager.whitelist_remove(self.server_name, p["uuid"])
        else:
            self.manager.whitelist_add(self.server_name, p["uuid"], p["name"])
        self._refresh()

    def _toggle_op(self, p):
        if p["op"]:
            self.manager.op_remove(self.server_name, p["uuid"], p["name"])
        else:
            self.manager.op_add(self.server_name, p["uuid"], p["name"])
        self._refresh()

    def _toggle_ban(self, p):
        if p["banned"]:
            self.manager.unban_player(self.server_name, p["uuid"], p["name"])
            self._refresh()
        else:
            if mb.askyesno("Confirmar", f"¿Banear a {p['name']}?", parent=self):
                self.manager.ban_player(self.server_name, p["uuid"], p["name"])
                self._refresh()


# ── Mods dialog ───────────────────────────────────────────────────────────────

class ModsDialog(ctk.CTkToplevel):
    def __init__(self, parent, manager: ServerManager, server_name: str):
        super().__init__(parent)
        self.manager = manager
        self.server_name = server_name

        self.title(f"Mods — {server_name}")
        self.geometry("520x480")
        self.resizable(False, False)
        self.grab_set()
        self.lift()

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Top bar
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        top.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(top, text="Mods instalados",
                     font=ctk.CTkFont(size=15, weight="bold")).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(top, text="＋  Añadir mod (.jar)", width=160, height=34,
                      command=self._add_mod).grid(row=0, column=1, padx=(8, 0))

        # Info note
        ctk.CTkLabel(self, text="ℹ  Los mods requieren Fabric, Forge o Paper como servidor base.",
                     font=ctk.CTkFont(size=11), text_color="gray55").grid(
            row=1, column=0, padx=16, sticky="nw")

        # Mod list
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.grid(row=2, column=0, sticky="nsew", padx=16, pady=(4, 4))
        self.scroll.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        ctk.CTkButton(self, text="Cerrar", height=34,
                      command=self.destroy).grid(row=3, column=0, padx=16, pady=(4, 16), sticky="e")

        self._refresh()

    def _refresh(self):
        for w in self.scroll.winfo_children():
            w.destroy()

        mods = self.manager.list_mods(self.server_name)
        if not mods:
            ctk.CTkLabel(self.scroll, text="No hay mods instalados.",
                         text_color="gray55").pack(pady=20)
            return

        for mod in mods:
            row = ctk.CTkFrame(self.scroll, corner_radius=8)
            row.pack(fill="x", pady=3)
            row.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(row, text=f"🧩  {mod}",
                         font=ctk.CTkFont(size=12), anchor="w").grid(
                row=0, column=0, padx=12, pady=10, sticky="w")

            ctk.CTkButton(row, text="Eliminar", width=80, height=28,
                          fg_color="#5a1a1a", hover_color="#3a0a0a",
                          font=ctk.CTkFont(size=11),
                          command=lambda m=mod: self._remove(m)).grid(
                row=0, column=1, padx=8)

    def _add_mod(self):
        paths = fd.askopenfilenames(
            parent=self,
            title="Selecciona mods (.jar)",
            filetypes=[("JAR files", "*.jar"), ("All files", "*.*")]
        )
        for p in paths:
            self.manager.install_mod(self.server_name, p)
        if paths:
            self._refresh()

    def _remove(self, mod_name):
        if mb.askyesno("Confirmar", f"¿Eliminar «{mod_name}»?", parent=self):
            self.manager.remove_mod(self.server_name, mod_name)
            self._refresh()


# ── Helper widgets ────────────────────────────────────────────────────────────

class _ToggleBtn(ctk.CTkButton):
    _ON  = ("#27ae60", "#1e8449")
    _OFF = ("#e74c3c", "#c0392b")

    def __init__(self, parent, value=False, **kw):
        self._bv = ctk.BooleanVar(value=value)
        super().__init__(parent, text=self._lbl(), width=56, height=36,
                         font=ctk.CTkFont(size=16),
                         fg_color=self._col(), hover_color=self._hov(),
                         command=self._flip, **kw)

    def _lbl(self): return "✓" if self._bv.get() else "✗"
    def _col(self): return self._ON  if self._bv.get() else self._OFF
    def _hov(self): return self._ON[1] if self._bv.get() else self._OFF[1]

    def _flip(self):
        self._bv.set(not self._bv.get())
        self.configure(text=self._lbl(), fg_color=self._col(), hover_color=self._hov())

    def get(self): return self._bv.get()


class _Spinner(ctk.CTkFrame):
    def __init__(self, parent, value=0, min_val=0, max_val=9999, **kw):
        super().__init__(parent, fg_color="transparent", **kw)
        self._min = min_val
        self._max = max_val
        self._sv  = ctk.StringVar(value=str(value))
        btn_kw = dict(width=28, height=32, fg_color="gray30", hover_color="gray20",
                      font=ctk.CTkFont(size=14))
        ctk.CTkButton(self, text="−", command=self._dec, **btn_kw).pack(side="left")
        ctk.CTkEntry(self, textvariable=self._sv, width=56,
                     height=32, justify="center").pack(side="left", padx=2)
        ctk.CTkButton(self, text="+", command=self._inc, **btn_kw).pack(side="left")

    def _dec(self):
        try: self._sv.set(str(max(self._min, int(self._sv.get()) - 1)))
        except ValueError: pass

    def _inc(self):
        try: self._sv.set(str(min(self._max, int(self._sv.get()) + 1)))
        except ValueError: pass

    def get(self): return self._sv.get()


# ── Server settings dialog ────────────────────────────────────────────────────

class ServerSettingsDialog(ctk.CTkToplevel):
    def __init__(self, parent, manager: ServerManager, server_name: str):
        super().__init__(parent)
        self.manager     = manager
        self.server_name = server_name
        self._widgets: dict = {}

        self.title(f"Ajustes — {server_name}")
        self.geometry("760x600")
        self.resizable(True, True)
        self.minsize(600, 480)
        self.grab_set()
        self.lift()

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        props_path = os.path.join(manager.servers[server_name]["path"], "server.properties")
        if not os.path.exists(props_path):
            ctk.CTkLabel(
                self,
                text="server.properties aún no existe.\nInicia el servidor una vez para generarlo.",
                font=ctk.CTkFont(size=13),
            ).pack(expand=True)
            ctk.CTkButton(self, text="Cerrar", command=self.destroy).pack(pady=16)
            return

        self._props = manager.read_properties(server_name)

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew", padx=12, pady=(12, 6))
        for c in range(3):
            scroll.grid_columnconfigure(c, weight=1, uniform="col")

        # Row 0 — core gameplay
        self._combo_card(scroll, 0, 0, "Modo de juego", "gamemode",
                         ["survival", "creative", "adventure", "spectator"],
                         ["Supervivencia", "Creativo", "Aventura", "Espectador"])
        self._combo_card(scroll, 0, 1, "Dificultad", "difficulty",
                         ["peaceful", "easy", "normal", "hard"],
                         ["Pacífica", "Fácil", "Normal", "Difícil"])
        self._spinner_card(scroll, 0, 2, "Espacios", "max-players", 1, 200)

        # Row 1 — access
        self._bool_card(scroll, 1, 0, "Lista blanca", "white-list")
        self._bool_card(scroll, 1, 1, "Modo online (premium)", "online-mode", default=True)
        self._bool_card(scroll, 1, 2, "Volar", "allow-flight")

        # Row 2 — world rules
        self._bool_card(scroll, 2, 0, "PvP", "pvp", default=True)
        self._bool_card(scroll, 2, 1, "Forzar modo de juego", "force-gamemode")
        self._spinner_card(scroll, 2, 2, "Protección de spawn", "spawn-protection", 0, 100)

        # Row 3 — spawning
        self._bool_card(scroll, 3, 0, "Mobs hostiles", "spawn-monsters", default=True)
        self._bool_card(scroll, 3, 1, "Animales", "spawn-animals", default=True)
        self._bool_card(scroll, 3, 2, "NPCs (aldeanos)", "spawn-npcs", default=True)

        # Row 4 — performance & advanced
        self._bool_card(scroll, 4, 0, "Bloques de comandos", "enable-command-block")
        self._spinner_card(scroll, 4, 1, "Distancia de visión", "view-distance", 2, 32)
        self._spinner_card(scroll, 4, 2, "Dist. simulación", "simulation-distance", 2, 32)

        # Row 5 — text fields (full width)
        self._entry_card(scroll, 5, "Descripción (MOTD)", "motd",
                         placeholder="Un servidor de Minecraft")
        self._entry_card(scroll, 6, "Puerto", "server-port")

        # Bottom bar
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))
        ctk.CTkButton(bar, text="Abrir archivo raw", width=150, height=34,
                      fg_color="gray25", hover_color="gray18",
                      command=self._open_raw).pack(side="left")
        ctk.CTkButton(bar, text="Cancelar", width=100, height=34,
                      fg_color="gray25", hover_color="gray18",
                      command=self.destroy).pack(side="right", padx=(6, 0))
        ctk.CTkButton(bar, text="Aplicar", width=100, height=34,
                      command=self._apply).pack(side="right")

    # ── Card builders ─────────────────────────────────────────────────────────

    def _base_card(self, parent, row, col, label, key, colspan=1):
        card = ctk.CTkFrame(parent, corner_radius=8)
        card.grid(row=row, column=col, columnspan=colspan,
                  padx=4, pady=4, sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(12, 4))
        top.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(top, text=label,
                     font=ctk.CTkFont(size=13, weight="bold"),
                     anchor="w").grid(row=0, column=0, sticky="w")

        raw = self._props.get(key, "")
        ctk.CTkLabel(card, text=f"{key}={raw}",
                     font=ctk.CTkFont(size=10), text_color="gray50",
                     anchor="w").pack(padx=12, pady=(0, 10), fill="x")
        return top

    def _bool_card(self, parent, row, col, label, key, *, default=False):
        val = self._props.get(key, "true" if default else "false").lower() == "true"
        top = self._base_card(parent, row, col, label, key)
        w = _ToggleBtn(top, value=val)
        w.grid(row=0, column=1, padx=(8, 0))
        self._widgets[key] = w

    def _spinner_card(self, parent, row, col, label, key, min_val=0, max_val=999):
        try:   val = int(self._props.get(key, str(min_val)))
        except ValueError: val = min_val
        top = self._base_card(parent, row, col, label, key)
        w = _Spinner(top, value=val, min_val=min_val, max_val=max_val)
        w.grid(row=0, column=1, padx=(8, 0))
        self._widgets[key] = w

    def _combo_card(self, parent, row, col, label, key, options, display=None):
        disp  = display or options
        raw   = self._props.get(key, options[0])
        val   = raw if raw in options else options[0]
        dval  = disp[options.index(val)]
        sv    = ctk.StringVar(value=dval)
        d2i   = dict(zip(disp, options))

        top = self._base_card(parent, row, col, label, key)
        ctk.CTkComboBox(top, variable=sv, values=disp,
                        width=160, height=34, state="readonly").grid(
            row=0, column=1, padx=(8, 0))

        class _W:
            def get(self_w): return d2i.get(sv.get(), options[0])
        self._widgets[key] = _W()

    def _entry_card(self, parent, row, label, key, *, placeholder=""):
        sv  = ctk.StringVar(value=self._props.get(key, ""))
        top = self._base_card(parent, row, 0, label, key, colspan=3)
        ctk.CTkEntry(top, textvariable=sv, height=34,
                     placeholder_text=placeholder).grid(
            row=0, column=1, padx=(8, 0), sticky="ew")
        top.grid_columnconfigure(1, weight=1)

        class _W:
            def get(self_w): return sv.get().strip()
        self._widgets[key] = _W()

    # ── Apply / raw ───────────────────────────────────────────────────────────

    def _apply(self):
        updates = {}
        for key, w in self._widgets.items():
            val = w.get()
            updates[key] = ("true" if val else "false") if isinstance(val, bool) else str(val).strip()

        if "server-port" in updates:
            try:
                port = int(updates["server-port"])
                if 1024 <= port <= 65535:
                    self.manager.update_port(self.server_name, port)
            except ValueError:
                pass

        self.manager.write_properties(self.server_name, updates)

        if self.manager.is_running() and self.manager.get_active_server() == self.server_name:
            mb.showinfo("Ajustes guardados",
                        "Los cambios se aplicarán al reiniciar el servidor.", parent=self)
        self.destroy()

    def _open_raw(self):
        path = os.path.join(self.manager.servers[self.server_name]["path"], "server.properties")
        if os.path.exists(path):
            os.startfile(path)


# ── Backup dialog ─────────────────────────────────────────────────────────────

_AUTO_HOURS = {
    "Desactivado": 0,
    "Cada hora":   1,
    "Cada 2 horas": 2,
    "Cada 4 horas": 4,
    "Cada 6 horas": 6,
    "Cada 12 horas": 12,
    "Cada 24 horas": 24,
}
_AUTO_LABELS = list(_AUTO_HOURS.keys())


def _fmt_size(b: int) -> str:
    if b >= 1_073_741_824:
        return f"{b/1_073_741_824:.1f} GB"
    if b >= 1_048_576:
        return f"{b/1_048_576:.1f} MB"
    return f"{b/1024:.0f} KB"


def _fmt_mtime(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M")


class BackupDialog(ctk.CTkToplevel):
    def __init__(self, parent, manager: ServerManager, server_name: str,
                 on_interval_change=None):
        super().__init__(parent)
        self._manager    = manager
        self._server_name = server_name
        self._on_interval_change = on_interval_change

        self.title(f"Backups — {server_name}")
        self.geometry("620x560")
        self.resizable(True, True)
        self.minsize(500, 420)
        self.grab_set()
        self.lift()

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── Auto-backup section ──
        auto_frame = ctk.CTkFrame(self, corner_radius=8)
        auto_frame.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 6))
        auto_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(auto_frame, text="Backup automático",
                     font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=0, column=0, columnspan=3, padx=14, pady=(12, 6), sticky="w")

        ctk.CTkLabel(auto_frame, text="Intervalo:",
                     font=ctk.CTkFont(size=12), text_color="gray60").grid(
            row=1, column=0, padx=(14, 6), pady=(0, 12), sticky="w")

        current_h = manager.get_auto_backup_hours(server_name)
        current_label = next(
            (k for k, v in _AUTO_HOURS.items() if v == current_h), "Desactivado"
        )
        self._interval_var = ctk.StringVar(value=current_label)
        ctk.CTkComboBox(auto_frame, variable=self._interval_var,
                        values=_AUTO_LABELS, width=180, height=34,
                        state="readonly").grid(row=1, column=1, padx=4, pady=(0, 12), sticky="w")

        ctk.CTkButton(auto_frame, text="Guardar", width=90, height=34,
                      command=self._save_interval).grid(
            row=1, column=2, padx=(6, 14), pady=(0, 12))

        self._interval_status = ctk.CTkLabel(
            auto_frame,
            text=self._interval_hint(current_h),
            font=ctk.CTkFont(size=10), text_color="gray55"
        )
        self._interval_status.grid(row=2, column=0, columnspan=3,
                                   padx=14, pady=(0, 10), sticky="w")

        # ── Manual backup button + status ──
        manual_frame = ctk.CTkFrame(self, fg_color="transparent")
        manual_frame.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 6))
        manual_frame.grid_columnconfigure(1, weight=1)

        self._backup_btn = ctk.CTkButton(
            manual_frame, text="💾  Crear backup ahora",
            width=180, height=36, font=ctk.CTkFont(size=13),
            fg_color="#1e7a3a", hover_color="#155728",
            command=self._manual_backup,
        )
        self._backup_btn.grid(row=0, column=0, padx=(0, 10))

        self._status_lbl = ctk.CTkLabel(
            manual_frame, text="", font=ctk.CTkFont(size=11),
            text_color="gray55", anchor="w"
        )
        self._status_lbl.grid(row=0, column=1, sticky="w")

        self._progress = ctk.CTkProgressBar(manual_frame, width=180, height=8)

        # ── Backup list ──
        ctk.CTkLabel(self, text="BACKUPS DISPONIBLES",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="gray50").grid(
            row=1, column=0, sticky="sw", padx=18, pady=(42, 0))

        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.grid(row=2, column=0, sticky="nsew", padx=12, pady=(2, 6))
        self._scroll.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(self, text="Cerrar", width=100, height=34,
                      command=self.destroy).grid(
            row=3, column=0, sticky="e", padx=16, pady=(0, 14))

        self.after(100, self._refresh_list)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _interval_hint(self, hours: int) -> str:
        if hours == 0:
            return "El backup automático está desactivado."
        return (f"Se creará/actualizará «auto_backup.zip» cada {hours} hora{'s' if hours>1 else ''}."
                " El archivo anterior se sobreescribe.")

    def _save_interval(self):
        hours = _AUTO_HOURS[self._interval_var.get()]
        self._manager.set_auto_backup_hours(self._server_name, hours)
        self._interval_status.configure(text=self._interval_hint(hours))
        if self._on_interval_change:
            self._on_interval_change(self._server_name)

    def _manual_backup(self):
        self._backup_btn.configure(state="disabled", text="Creando...")
        self._status_lbl.configure(text="Comprimiendo archivos...", text_color="gray55")
        self._progress.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        self._progress.set(0)

        def _worker():
            try:
                def _prog(pct: int):
                    self.after(0, lambda p=pct/100: self._progress.set(p))

                name = self._manager.create_backup(self._server_name, auto=False,
                                                   progress_cb=_prog)
                self.after(0, lambda n=name: self._on_backup_done(n))
            except Exception as e:
                self.after(0, lambda err=e: self._on_backup_error(str(err)))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_backup_done(self, filename: str):
        self._progress.grid_remove()
        self._backup_btn.configure(state="normal", text="💾  Crear backup ahora")
        self._status_lbl.configure(text=f"✓ Guardado: {filename}", text_color="#52e07a")
        self._refresh_list()

    def _on_backup_error(self, err: str):
        self._progress.grid_remove()
        self._backup_btn.configure(state="normal", text="💾  Crear backup ahora")
        self._status_lbl.configure(text=f"✗ Error: {err}", text_color="#e05252")

    # ── List ──────────────────────────────────────────────────────────────────

    def _refresh_list(self):
        for w in self._scroll.winfo_children():
            w.destroy()

        backups = self._manager.list_backups(self._server_name)
        if not backups:
            ctk.CTkLabel(
                self._scroll,
                text="No hay backups todavía.\nPulsa «Crear backup ahora» para empezar.",
                text_color="gray55", font=ctk.CTkFont(size=12),
            ).pack(pady=30)
            return

        for b in backups:
            self._backup_row(b)

    def _backup_row(self, b: dict):
        row = ctk.CTkFrame(self._scroll, corner_radius=8)
        row.pack(fill="x", pady=3, padx=2)
        row.grid_columnconfigure(0, weight=1)

        icon = "🔄" if b["auto"] else "📦"
        label = "Auto-backup" if b["auto"] else b["name"].replace("backup_", "").replace(".zip", "").replace("_", " ")

        info = ctk.CTkFrame(row, fg_color="transparent")
        info.grid(row=0, column=0, sticky="w", padx=12, pady=8)
        ctk.CTkLabel(info, text=f"{icon}  {label}",
                     font=ctk.CTkFont(size=12, weight="bold"), anchor="w").pack(anchor="w")
        ctk.CTkLabel(info,
                     text=f"{_fmt_mtime(b['mtime'])}  •  {_fmt_size(b['size'])}",
                     font=ctk.CTkFont(size=10), text_color="gray55").pack(anchor="w")

        btn_frame = ctk.CTkFrame(row, fg_color="transparent")
        btn_frame.grid(row=0, column=1, padx=(4, 10), sticky="e")

        ctk.CTkButton(
            btn_frame, text="Restaurar", width=90, height=30,
            font=ctk.CTkFont(size=11),
            fg_color="#1a5276", hover_color="#154360",
            command=lambda n=b["name"]: self._restore(n),
        ).pack(side="left", padx=(0, 4))

        ctk.CTkButton(
            btn_frame, text="Eliminar", width=80, height=30,
            font=ctk.CTkFont(size=11),
            fg_color="#5a1a1a", hover_color="#3a0a0a",
            command=lambda n=b["name"]: self._delete(n),
        ).pack(side="left")

    def _restore(self, backup_name: str):
        if not mb.askyesno(
            "Restaurar backup",
            f"¿Restaurar «{backup_name}»?\n\n"
            "La carpeta 'world' actual se reemplazará.\n"
            "Asegúrate de que el servidor está detenido.",
            parent=self,
        ):
            return
        try:
            self._manager.restore_backup(self._server_name, backup_name)
            mb.showinfo("Restaurado", "Backup restaurado correctamente.", parent=self)
        except Exception as e:
            mb.showerror("Error", str(e), parent=self)

    def _delete(self, backup_name: str):
        if mb.askyesno("Eliminar backup", f"¿Eliminar «{backup_name}»?", parent=self):
            self._manager.delete_backup(self._server_name, backup_name)
            self._refresh_list()


# ── RAM edit dialog ───────────────────────────────────────────────────────────

class RamDialog(ctk.CTkToplevel):
    def __init__(self, parent, manager: ServerManager, server_name: str,
                 current_mb: int, on_done):
        super().__init__(parent)
        self._manager     = manager
        self._server_name = server_name
        self._on_done     = on_done

        self.title("Cambiar RAM")
        self.geometry("360x280")
        self.resizable(False, False)
        self.grab_set()
        self.lift()

        ctk.CTkLabel(self, text="Memoria RAM del servidor",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(20, 4))
        ctk.CTkLabel(self, text=f"Actual: {mb_to_label(current_mb)}",
                     text_color="gray55", font=ctk.CTkFont(size=11)).pack()

        # Preset combo
        ctk.CTkLabel(self, text="Selecciona un preset:", anchor="w",
                     font=ctk.CTkFont(size=12)).pack(padx=28, fill="x", pady=(16, 2))

        current_label = next(
            (k for k, v in RAM_OPTIONS.items() if v == current_mb),
            "Personalizado"
        )
        self._ram_var = ctk.StringVar(value=current_label)
        self._combo = ctk.CTkComboBox(
            self, variable=self._ram_var, values=RAM_LABELS,
            height=36, command=self._on_preset_change,
        )
        self._combo.pack(padx=28, fill="x")

        # Custom MB entry (shown only for Personalizado)
        self._custom_frame = ctk.CTkFrame(self, fg_color="transparent")
        ctk.CTkLabel(self._custom_frame, text="MB personalizados:",
                     font=ctk.CTkFont(size=11), text_color="gray60").pack(side="left", padx=(0, 8))
        self._custom_entry = ctk.CTkEntry(self._custom_frame,
                                           placeholder_text="ej. 6144", width=110, height=32)
        if current_label == "Personalizado":
            self._custom_entry.insert(0, str(current_mb))
        self._custom_entry.pack(side="left")
        if current_label == "Personalizado":
            self._custom_frame.pack(padx=28, pady=(6, 0), anchor="w")

        # Buttons
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(side="bottom", fill="x", padx=28, pady=18)
        ctk.CTkButton(btn_row, text="Cancelar", width=100, height=34,
                      fg_color="gray25", hover_color="gray18",
                      command=self.destroy).pack(side="right", padx=(6, 0))
        ctk.CTkButton(btn_row, text="Aplicar", width=100, height=34,
                      command=self._apply).pack(side="right")

    def _on_preset_change(self, choice):
        if RAM_OPTIONS.get(choice, 0) == -1:
            self._custom_frame.pack(padx=28, pady=(6, 0), anchor="w")
        else:
            self._custom_frame.pack_forget()

    def _apply(self):
        label = self._ram_var.get()
        mb_val = RAM_OPTIONS.get(label, -1)
        if mb_val == -1:
            raw = self._custom_entry.get().strip()
            if not raw.isdigit() or int(raw) < 256:
                mb.showerror("Error", "Introduce un valor en MB válido (mínimo 256).", parent=self)
                return
            mb_val = int(raw)
        self._manager.update_ram(self._server_name, mb_val)
        self._on_done(mb_val)
        self.destroy()


# ── Cores edit dialog ─────────────────────────────────────────────────────────

class CoresDialog(ctk.CTkToplevel):
    def __init__(self, parent, manager: ServerManager, server_name: str,
                 current_cores, on_done):
        super().__init__(parent)
        self._manager     = manager
        self._server_name = server_name
        self._on_done     = on_done

        cpu_total = os.cpu_count() or 1

        self.title("Cambiar núcleos de CPU")
        self.geometry("340x220")
        self.resizable(False, False)
        self.grab_set()
        self.lift()

        ctk.CTkLabel(self, text="Núcleos de CPU asignados",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(20, 4))
        current_label = "Todos (auto)" if not current_cores else str(current_cores)
        ctk.CTkLabel(self, text=f"Actual: {current_label}  •  Disponibles: {cpu_total}",
                     text_color="gray55", font=ctk.CTkFont(size=11)).pack()

        ctk.CTkLabel(self, text="Núcleos a usar:", anchor="w",
                     font=ctk.CTkFont(size=12)).pack(padx=28, fill="x", pady=(16, 2))

        core_values = ["Todos (auto)"] + [str(i) for i in range(1, cpu_total + 1)]
        self._cores_var = ctk.StringVar(value=current_label)
        ctk.CTkComboBox(self, variable=self._cores_var,
                        values=core_values, height=36).pack(padx=28, fill="x")

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(side="bottom", fill="x", padx=28, pady=18)
        ctk.CTkButton(btn_row, text="Cancelar", width=100, height=34,
                      fg_color="gray25", hover_color="gray18",
                      command=self.destroy).pack(side="right", padx=(6, 0))
        ctk.CTkButton(btn_row, text="Aplicar", width=100, height=34,
                      command=self._apply).pack(side="right")

    def _apply(self):
        val = self._cores_var.get()
        cores = None if val == "Todos (auto)" else int(val)
        self._manager.update_cores(self._server_name, cores)
        self._on_done(cores)
        self.destroy()


# ── Create server dialog ──────────────────────────────────────────────────────

TYPE_ICONS = {
    "Vanilla": "🟩",
    "Paper":   "📄",
    "Fabric":  "🧵",
    "Forge":   "🔨",
}

class CreateDialog(ctk.CTkToplevel):
    def __init__(self, parent, manager: ServerManager, on_done):
        super().__init__(parent)
        self.manager = manager
        self.on_done = on_done
        self.versions = []
        self._load_id = 0

        self.title("Nuevo servidor")
        self.geometry("480x680")
        self.resizable(False, False)
        self.grab_set()
        self.lift()

        pad = {"padx": 28, "fill": "x"}

        # Nombre
        ctk.CTkLabel(self, text="Nombre del servidor", anchor="w",
                     font=ctk.CTkFont(size=12)).pack(**pad, pady=(22, 2))
        self.name_entry = ctk.CTkEntry(self, placeholder_text="mi-servidor", height=36)
        self.name_entry.pack(**pad)

        # Tipo de servidor
        ctk.CTkLabel(self, text="Tipo de servidor", anchor="w",
                     font=ctk.CTkFont(size=12)).pack(**pad, pady=(14, 2))
        self.type_var = ctk.StringVar(value="Vanilla")
        self.type_combo = ctk.CTkComboBox(
            self, variable=self.type_var, values=SERVER_TYPES,
            height=36, command=self._on_type_change,
        )
        self.type_combo.pack(**pad)

        # Descripción del tipo
        self.type_desc = ctk.CTkLabel(
            self, text="Servidor oficial de Mojang, sin mods",
            font=ctk.CTkFont(size=11), text_color="gray55", anchor="w",
        )
        self.type_desc.pack(padx=28, fill="x", pady=(2, 0))

        # Versión
        ctk.CTkLabel(self, text="Versión de Minecraft", anchor="w",
                     font=ctk.CTkFont(size=12)).pack(**pad, pady=(14, 2))
        self.ver_var = ctk.StringVar(value="Cargando versiones...")
        self.ver_combo = ctk.CTkComboBox(self, variable=self.ver_var,
                                          state="disabled", height=36)
        self.ver_combo.pack(**pad)

        # RAM
        ctk.CTkLabel(self, text="Memoria RAM", anchor="w",
                     font=ctk.CTkFont(size=12)).pack(**pad, pady=(14, 2))
        self.ram_label_var = ctk.StringVar(value=RAM_LABELS[4])
        self.ram_combo = ctk.CTkComboBox(self, variable=self.ram_label_var,
                                          values=RAM_LABELS, height=36,
                                          command=self._on_ram_change)
        self.ram_combo.pack(**pad)

        # RAM personalizada (oculta por defecto)
        self.ram_custom_frame = ctk.CTkFrame(self, fg_color="transparent")
        ctk.CTkLabel(self.ram_custom_frame, text="MB personalizados:",
                     font=ctk.CTkFont(size=11), text_color="gray60").pack(side="left", padx=(0, 8))
        self.ram_custom_entry = ctk.CTkEntry(self.ram_custom_frame,
                                              placeholder_text="ej. 6144", width=120, height=32)
        self.ram_custom_entry.pack(side="left")

        # Núcleos CPU
        cpu_total = os.cpu_count() or 1
        ctk.CTkLabel(self, text=f"Núcleos de CPU  (disponibles: {cpu_total})", anchor="w",
                     font=ctk.CTkFont(size=12)).pack(**pad, pady=(14, 2))
        core_values = ["Todos (auto)"] + [str(i) for i in range(1, cpu_total + 1)]
        self.cores_var = ctk.StringVar(value="Todos (auto)")
        ctk.CTkComboBox(self, variable=self.cores_var,
                        values=core_values, height=36).pack(**pad)

        # Progreso y botón
        self.progress_lbl = ctk.CTkLabel(self, text="", text_color="gray60",
                                          font=ctk.CTkFont(size=11))
        self.progress_lbl.pack(pady=(18, 4))

        self.create_btn = ctk.CTkButton(self, text="Crear servidor", height=38,
                                         font=ctk.CTkFont(size=13), command=self._create)
        self.create_btn.pack(**pad, pady=(4, 22))

        threading.Thread(target=self._load_versions, daemon=True).start()

    _TYPE_DESCS = {
        "Vanilla": "Servidor oficial de Mojang, sin mods",
        "Paper":   "Alto rendimiento, compatible con plugins Bukkit/Spigot",
        "Fabric":  "Ligero y modular, ideal para mods de Fabric",
        "Forge":   "El más popular para mods, requiere instalación extra",
    }

    def _on_type_change(self, choice):
        self.type_desc.configure(text=self._TYPE_DESCS.get(choice, ""))
        self.ver_combo.configure(state="disabled")
        self.ver_var.set("Cargando versiones...")
        self.versions = []
        threading.Thread(target=self._load_versions, daemon=True).start()

    def _on_ram_change(self, choice):
        if RAM_OPTIONS.get(choice, 0) == -1:
            self.ram_custom_frame.pack(padx=28, pady=(4, 0), anchor="w")
        else:
            self.ram_custom_frame.pack_forget()

    def _get_ram_mb(self):
        label = self.ram_label_var.get()
        mb_val = RAM_OPTIONS.get(label, -1)
        if mb_val == -1:
            raw = self.ram_custom_entry.get().strip()
            if not raw.isdigit() or int(raw) < 256:
                raise ValueError("Introduce un valor en MB válido (mínimo 256).")
            return int(raw)
        return mb_val

    def _get_cores(self):
        val = self.cores_var.get()
        return None if val == "Todos (auto)" else int(val)

    def _load_versions(self):
        self._load_id += 1
        my_id = self._load_id
        server_type = self.type_var.get().lower()
        try:
            versions = self.manager.get_versions(server_type)
            if self._load_id != my_id:
                return
            self.versions = versions
            ids = [v["id"] for v in versions]
            self.after(0, lambda: (
                self.ver_combo.configure(values=ids, state="normal"),
                self.ver_var.set(ids[0] if ids else ""),
            ))
        except Exception as e:
            if self._load_id == my_id:
                self.after(0, lambda: self.progress_lbl.configure(
                    text=f"Error cargando versiones: {e}", text_color="#e05252"))

    def _create(self):
        name = self.name_entry.get().strip()
        ver_id = self.ver_var.get()
        server_type = self.type_var.get().lower()

        if not name:
            mb.showerror("Error", "El nombre no puede estar vacío.", parent=self)
            return
        if name in self.manager.servers:
            mb.showerror("Error", f"Ya existe un servidor llamado «{name}».", parent=self)
            return
        if not ver_id or ver_id == "Cargando versiones...":
            mb.showerror("Error", "Selecciona una versión válida.", parent=self)
            return

        ver_url = next((v["url"] for v in self.versions if v["id"] == ver_id), None)

        try:
            ram = self._get_ram_mb()
        except ValueError as e:
            mb.showerror("Error", str(e), parent=self)
            return

        cores = self._get_cores()
        self.create_btn.configure(state="disabled")

        def _do():
            try:
                self.manager.create_server(
                    name, ver_id,
                    server_type=server_type,
                    version_url=ver_url,
                    ram_mb=ram, cores=cores,
                    progress_cb=lambda msg: self.after(0, lambda m=msg:
                        self.progress_lbl.configure(text=m, text_color="gray70")),
                )
                self.after(0, lambda: (self.destroy(), self.on_done(name)))
            except Exception as e:
                self.after(0, lambda: (
                    self.progress_lbl.configure(text=f"Error: {e}", text_color="#e05252"),
                    self.create_btn.configure(state="normal"),
                ))

        threading.Thread(target=_do, daemon=True).start()
