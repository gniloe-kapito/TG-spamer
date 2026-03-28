import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import requests
import threading
import time
import os

# ──────────────────────────────────────────────────────────────────────────────
# CLIPBOARD MANAGER
# ──────────────────────────────────────────────────────────────────────────────
class ClipboardManager:
    def __init__(self, root):
        self.root = root

    def bind_widget(self, widget):
        """Привязать горячие клавиши к конкретному виджету."""
        widget.bind("<Control-v>",      self._paste, add=False)
        widget.bind("<Control-V>",      self._paste, add=False)
        widget.bind("<Control-c>",      self._copy,  add=False)
        widget.bind("<Control-C>",      self._copy,  add=False)
        widget.bind("<Control-x>",      self._cut,   add=False)
        widget.bind("<Control-X>",      self._cut,   add=False)
        widget.bind("<Shift-Insert>",   self._paste, add=False)
        widget.bind("<Control-Insert>", self._copy,  add=False)

    def _is_text(self, w):
        return isinstance(w, (tk.Text, scrolledtext.ScrolledText))

    def _paste(self, event):
        w = event.widget
        try:
            text = self.root.clipboard_get()
        except Exception:
            return "break"
        try:
            if self._is_text(w):
                try:
                    w.delete("sel.first", "sel.last")
                except Exception:
                    pass
                w.insert("insert", text)
            else:
                try:
                    w.delete(w.index("sel.first"), w.index("sel.last"))
                except Exception:
                    pass
                w.insert("insert", text)
        except Exception:
            pass
        return "break"

    def _copy(self, event):
        w = event.widget
        try:
            text = w.selection_get()
        except Exception:
            try:
                text = w.get("1.0", "end-1c") if self._is_text(w) else w.get()
            except Exception:
                return "break"
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        return "break"

    def _cut(self, event):
        w = event.widget
        try:
            text = w.selection_get()
        except Exception:
            return "break"
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        try:
            if self._is_text(w):
                w.delete("sel.first", "sel.last")
            else:
                w.delete(w.index("sel.first"), w.index("sel.last"))
        except Exception:
            pass
        return "break"

# ──────────────────────────────────────────────────────────────────────────────
# CHAT WINDOW
# ──────────────────────────────────────────────────────────────────────────────
class ChatWindow:
    def __init__(self, parent_app):
        self.app            = parent_app
        self.window         = None
        self.polling_thread = None
        self.is_polling     = False
        self.last_update_id = 0
        self.colors         = None

    def open(self):
        self.colors = self.app.colors
        token   = self.app.token_entry.get().strip()
        chat_id = self.app.chat_id_entry.get().strip()

        if not token or not chat_id:
            messagebox.showerror("❌", "Сначала введите Token и Chat ID!")
            return

        if self.window and self.window.winfo_exists():
            self.window.lift()
            return

        self.window = tk.Toplevel(self.app.root)
        self.window.title(f"💬 Чат | {chat_id}")
        self.window.geometry("700x620")
        self.window.minsize(500, 420)
        self.window.configure(bg=self.colors['bg'])

        self._build_ui(token, chat_id)
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)

        self.is_polling     = True
        self.last_update_id = 0
        self.polling_thread = threading.Thread(
            target=self._poll_loop, args=(token, chat_id), daemon=True
        )
        self.polling_thread.start()

    def _build_ui(self, token, chat_id):
        c = self.colors

        header = tk.Frame(self.window, bg=c['frame_bg'], pady=6)
        header.pack(fill="x")
        tk.Label(header, text=f"💬 Чат с {chat_id}",
                 bg=c['frame_bg'], fg=c['fg'],
                 font=("Segoe UI", 11, "bold")).pack(side="left", padx=10)
        self.status_dot = tk.Label(header, text="⬤ подключение...",
                                   bg=c['frame_bg'], fg=c['warning'],
                                   font=("Segoe UI", 9))
        self.status_dot.pack(side="right", padx=10)

        msg_frame = tk.Frame(self.window, bg=c['bg'])
        msg_frame.pack(fill="both", expand=True, padx=8, pady=6)

        self.chat_text = scrolledtext.ScrolledText(
            msg_frame, font=("Segoe UI", 10), wrap=tk.WORD,
            state='disabled', bg=c['text_bg'], fg=c['fg'],
            insertbackground=c['fg'], relief='flat', borderwidth=0
        )
        self.chat_text.pack(fill="both", expand=True)
        self.app.clipboard.bind_widget(self.chat_text)

        self.chat_text.tag_config("user_name", foreground=c['info'],    font=("Segoe UI", 9, "bold"))
        self.chat_text.tag_config("user_msg",  foreground=c['fg'],      font=("Segoe UI", 10))
        self.chat_text.tag_config("bot_name",  foreground=c['accent'],  font=("Segoe UI", 9, "bold"))
        self.chat_text.tag_config("bot_msg",   foreground="#d0d0d0",    font=("Segoe UI", 10))
        self.chat_text.tag_config("spam_name", foreground="#ff9f43",    font=("Segoe UI", 9, "bold"))
        self.chat_text.tag_config("spam_msg",  foreground="#ffeaa7",    font=("Segoe UI", 10))
        self.chat_text.tag_config("time_tag",  foreground=c['fg_dim'],  font=("Segoe UI", 8))
        self.chat_text.tag_config("system",    foreground=c['warning'], font=("Segoe UI", 9, "italic"))
        self.chat_text.tag_config("media",     foreground=c['success'], font=("Segoe UI", 9, "italic"))

        send_frame = tk.Frame(self.window, bg=c['frame_bg'], pady=6)
        send_frame.pack(fill="x", padx=8, pady=(0, 8))

        self.input_entry = tk.Entry(
            send_frame, font=("Segoe UI", 10),
            bg=c['entry_bg'], fg=c['entry_fg'],
            insertbackground=c['fg'], relief='flat'
        )
        self.input_entry.pack(side="left", fill="x", expand=True, padx=(6, 4), ipady=6)
        self.input_entry.bind("<Return>", lambda e: self._send_reply(token, chat_id))
        self.app.clipboard.bind_widget(self.input_entry)

        tk.Button(send_frame, text="➤ Отправить",
                  font=("Segoe UI", 9, "bold"),
                  bg=c['accent'], fg="#ffffff", relief='flat', padx=12, pady=4,
                  activebackground=c['accent_hover'], cursor="hand2",
                  command=lambda: self._send_reply(token, chat_id)
                  ).pack(side="right", padx=6)

        tk.Button(send_frame, text="🗑",
                  font=("Segoe UI", 9),
                  bg=c['button_bg'], fg=c['fg'], relief='flat', padx=8, pady=4,
                  command=self._clear_chat
                  ).pack(side="right", padx=2)

    def _append_message(self, sender_name, text,
                        is_bot=False, is_spam=False,
                        timestamp=None, media_type=None):
        if not self.window or not self.window.winfo_exists():
            return
        self.chat_text.config(state='normal')

        ts = timestamp or time.strftime('%H:%M:%S')

        if is_spam:
            name_tag, msg_tag, prefix = "spam_name", "spam_msg", "📤  "
        elif is_bot:
            name_tag, msg_tag, prefix = "bot_name",  "bot_msg",  "🤖  "
        else:
            name_tag, msg_tag, prefix = "user_name", "user_msg", "👤  "

        self.chat_text.insert(tk.END, f"\n{prefix}", name_tag)
        self.chat_text.insert(tk.END, sender_name,   name_tag)
        self.chat_text.insert(tk.END, f"  [{ts}]\n",  "time_tag")
        if media_type:
            self.chat_text.insert(tk.END, f"  {media_type}\n",  "media")
        if text:
            self.chat_text.insert(tk.END, f"  {text}\n", msg_tag)

        self.chat_text.see(tk.END)
        self.chat_text.config(state='disabled')

    def _append_system(self, text):
        if not self.window or not self.window.winfo_exists():
            return
        self.chat_text.config(state='normal')
        self.chat_text.insert(tk.END, f"\n  ⚙️ {text}\n", "system")
        self.chat_text.see(tk.END)
        self.chat_text.config(state='disabled')

    def _clear_chat(self):
        self.chat_text.config(state='normal')
        self.chat_text.delete("1.0", tk.END)
        self.chat_text.config(state='disabled')

    def notify_sent(self, text, media_label=None, count=None):
        """Вызывается из process_sending после каждой успешной отправки."""
        if not self.window or not self.window.winfo_exists():
            return
        label = f"Бот (спам #{count})" if count else "Бот (спам)"
        self.window.after(0, lambda l=label, t=text, m=media_label:
                          self._append_message(l, t, is_spam=True, media_type=m))

    def _send_reply(self, token, chat_id):
        text = self.input_entry.get().strip()
        if not text:
            return
        self.input_entry.delete(0, tk.END)

        def do_send():
            try:
                r = requests.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    data={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
                    timeout=10
                )
                if r.status_code == 200:
                    self.window.after(0, lambda: self._append_message(
                        "Вы (бот)", text, is_bot=True))
                else:
                    err = r.json().get('description', 'Ошибка')
                    self.window.after(0, lambda: self._append_system(f"Ошибка отправки: {err}"))
            except Exception as e:
                self.window.after(0, lambda: self._append_system(f"Ошибка: {e}"))

        threading.Thread(target=do_send, daemon=True).start()

    def _poll_loop(self, token, chat_id):
        # 1. Сбросить webhook
        self.window.after(0, lambda: self._append_system("Сброс webhook..."))
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{token}/deleteWebhook",
                params={"drop_pending_updates": "false"},
                timeout=10
            )
            if not r.json().get("ok"):
                desc = r.json().get("description", "?")
                self.window.after(0, lambda: self._append_system(f"deleteWebhook: {desc}"))
        except Exception as e:
            self.window.after(0, lambda: self._append_system(f"deleteWebhook ошибка: {e}"))

        # 2. Первый запрос без offset
        self.window.after(0, lambda: self._append_system("Загрузка истории..."))
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{token}/getUpdates",
                params={"limit": 100, "timeout": 0,
                        "allowed_updates": ["message", "edited_message"]},
                timeout=15
            )
            data = r.json()
        except Exception as e:
            self.window.after(0, lambda: self._append_system(f"Ошибка соединения: {e}"))
            self.window.after(0, lambda: self._set_status("error"))
            return

        if not data.get("ok"):
            error_code = data.get("error_code", 0)
            desc       = data.get("description", "Неизвестная ошибка")
            if error_code == 409:
                self.window.after(0, lambda: self._append_system(
                    "409 Conflict: активен webhook или другой polling.  "
                    "Подождите 10 сек и откройте чат снова, либо сбросьте webhook:  "
                    f"https://api.telegram.org/bot{token}/deleteWebhook"
                ))
            else:
                self.window.after(0, lambda: self._append_system(f"Ошибка {error_code}: {desc}"))
            self.window.after(0, lambda: self._set_status("error"))
            return

        updates = data.get("result", [])
        for upd in updates:
            self._process_update(upd, chat_id)
        self.last_update_id = updates[-1]["update_id"] if updates else 0
        self.window.after(0, lambda n=len(updates):
                          self._append_system(f"История загружена ({n} сообщ.)"))
        self.window.after(0, lambda: self._set_status("online"))

        # 3. Long polling
        while self.is_polling:
            try:
                r = requests.get(
                    f"https://api.telegram.org/bot{token}/getUpdates",
                    params={
                        "offset": self.last_update_id + 1,
                        "limit":  100,
                        "timeout": 10,
                        "allowed_updates": ["message", "edited_message"],
                    },
                    timeout=20
                )
                data = r.json()
                if data.get("ok"):
                    for upd in data["result"]:
                        self._process_update(upd, chat_id)
                        self.last_update_id = upd["update_id"]
                else:
                    error_code = data.get("error_code", 0)
                    desc = data.get("description", "?")
                    if error_code == 409:
                        self.window.after(0, lambda: self._append_system(
                            "409: другой клиент перехватил polling. Ждём 5 сек..."))
                        self.window.after(0, lambda: self._set_status("error"))
                        time.sleep(5)
                        self.window.after(0, lambda: self._set_status("online"))
                    else:
                        self.window.after(0, lambda d=desc: self._append_system(f"Ошибка: {d}"))

            except requests.exceptions.Timeout:
                pass
            except requests.exceptions.ConnectionError:
                if self.is_polling:
                    self.window.after(0, lambda: self._set_status("error"))
                    time.sleep(3)
                    self.window.after(0, lambda: self._set_status("online"))
            except Exception as e:
                if self.is_polling:
                    self.window.after(0, lambda err=e: self._append_system(f"Polling ошибка: {err}"))
                    time.sleep(3)

    def _process_update(self, upd, filter_chat_id):
        msg = upd.get("message") or upd.get("edited_message")
        if not msg:
            return
        if str(msg.get("chat", {}).get("id", "")) != str(filter_chat_id):
            return

        ts        = time.strftime('%H:%M:%S', time.localtime(msg.get("date", time.time())))
        from_user = msg.get("from", {})
        is_bot    = from_user.get("is_bot", False)

        if is_bot:
            sender = from_user.get("first_name", "Бот")
        else:
            fname    = from_user.get("first_name", "")
            lname    = from_user.get("last_name", "")
            username = from_user.get("username", "")
            sender   = f"{fname} {lname}".strip() or username or "Пользователь"

        text       = msg.get("text") or msg.get("caption") or ""
        media_type = None
        if    "photo"    in msg: media_type = "📷 Фото"
        elif  "video"    in msg: media_type = "🎬 Видео"
        elif  "document" in msg:
            fn  = msg["document"].get("file_name", "")
            fsz = msg["document"].get("file_size", 0)
            sz  = f"{fsz/1024/1024:.1f} МБ" if fsz else ""
            media_type = f"📎 Файл: {fn} {sz}".strip()
        elif  "sticker"  in msg: media_type = f"🎭 Стикер: {msg['sticker'].get('emoji','')}"
        elif  "voice"    in msg: media_type = "🎤 Голосовое"
        elif  "audio"    in msg: media_type = "🎵 Аудио"

        if "edited_message" in upd:
            text = f"[ред.] {text}"

        self.window.after(0, lambda s=sender, t=text, b=is_bot, ts=ts, m=media_type:
                          self._append_message(s, t, is_bot=b, timestamp=ts, media_type=m))

    def _set_status(self, state):
        if not self.window or not self.window.winfo_exists():
            return
        if state == "online":
            self.status_dot.config(text="⬤ онлайн", fg=self.colors['success'])
        elif state == "error":
            self.status_dot.config(text="⬤ ошибка",  fg=self.colors['error'])
        else:
            self.status_dot.config(text="⬤ подключение...", fg=self.colors['warning'])

    def _on_close(self):
        self.is_polling = False
        self.window.destroy()
        self.window = None

# ──────────────────────────────────────────────────────────────────────────────
# MAIN APP
# ──────────────────────────────────────────────────────────────────────────────
class TelegramSenderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Telegram Spammer v1.1")  # ← ИЗМЕНЕНО
        self.root.geometry("1200x930")
        self.root.minsize(1000, 700)
        self.setup_modern_theme()
        self.clipboard = ClipboardManager(root)

        self.selected_file_path   = None
        self.is_paused            = False
        self.is_stopped           = False
        self.pause_until          = 0
        self._send_thread_running = False

        self.chat_window = ChatWindow(self)

        main_container = ttk.Frame(root)
        main_container.pack(fill="both", expand=True, padx=10, pady=10)

        left_panel = ttk.Frame(main_container, width=320)
        left_panel.pack(side="left", fill="y", padx=(0, 10))
        left_panel.pack_propagate(False)

        right_panel = ttk.Frame(main_container)
        right_panel.pack(side="left", fill="both", expand=True)

        self.create_left_panel(left_panel)
        self.create_right_panel(right_panel)

    def create_left_panel(self, parent):
        header = ttk.Frame(parent)
        header.pack(fill="x", pady=(0, 10))
        ttk.Label(header, text="📤 Telegram\nSpammer",  # ← ИЗМЕНЕНО
                  font=("Segoe UI", 14, "bold")).pack(side="left")
        ttk.Label(header, text="v1.1",  # ← ИЗМЕНЕНО
                  font=("Segoe UI", 8), foreground="#6c757d").pack(side="right", pady=8)

        # Подключение
        conn_frame = ttk.LabelFrame(parent, text=" 🔑 Подключение  ", padding=8)
        conn_frame.pack(fill="x", pady=5)

        ttk.Label(conn_frame, text="Bot Token", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.token_entry = ttk.Entry(conn_frame, font=("Consolas", 9))
        self.token_entry.pack(fill="x", pady=2)
        self.clipboard.bind_widget(self.token_entry)

        ttk.Button(conn_frame, text="📋 Вставить",
                   command=self.paste_token).pack(fill="x", pady=2)

        ttk.Label(conn_frame, text="Chat ID",
                  font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(5, 0))
        self.chat_id_entry = ttk.Entry(conn_frame, font=("Consolas", 9))
        self.chat_id_entry.pack(fill="x", pady=2)
        self.clipboard.bind_widget(self.chat_id_entry)

        # Кнопка вставить для Chat ID
        ttk.Button(conn_frame, text="📋 Вставить",
                   command=self.paste_chat_id).pack(fill="x", pady=2)

        btn_row = ttk.Frame(conn_frame)
        btn_row.pack(fill="x", pady=2)
        ttk.Button(btn_row, text="ℹ️ Помощь",
                   command=self.show_id_help).pack(side="left", fill="x", expand=True, padx=(0, 2))
        ttk.Button(btn_row, text="💬 Чат",
                   command=self.chat_window.open).pack(side="left", fill="x", expand=True, padx=(2, 0))

        # Тип
        type_frame = ttk.LabelFrame(parent, text=" 📎 Тип  ", padding=8)
        type_frame.pack(fill="x", pady=5)

        self.content_type = tk.StringVar(value="text")
        for val, lbl in [("text",      "📝 Текст"),
                         ("photo",     "🖼️ Фото"),
                         ("video",     "🎬 Видео"),
                         ("document",  "📎 Файл")]:
            ttk.Radiobutton(type_frame, text=lbl, variable=self.content_type,
                            value=val, command=self.toggle_file_selection).pack(anchor="w", pady=1)

        # Файл
        file_frame = ttk.LabelFrame(parent, text=" 📁 Файл  ", padding=8)
        file_frame.pack(fill="x", pady=5)

        self.file_icon = ttk.Label(file_frame, text="📄", font=("Segoe UI", 18))
        self.file_icon.pack(pady=3)
        self.file_label = ttk.Label(file_frame, text="Не выбран",
                                    font=("Segoe UI", 8), foreground="#6c757d", wraplength=280)
        self.file_label.pack(pady=2)

        file_btns = ttk.Frame(file_frame)
        file_btns.pack(fill="x", pady=3)
        self.select_file_btn = ttk.Button(file_btns, text="Выбрать",
                                          command=self.select_file, state='disabled')
        self.select_file_btn.pack(side="left", padx=2, fill="x", expand=True)
        self.clear_file_btn = ttk.Button(file_btns, text="🗑",
                                         command=self.clear_file, state='disabled', width=3)
        self.clear_file_btn.pack(side="left", padx=2)

        # Настройки
        settings_frame = ttk.LabelFrame(parent, text=" ⚙️ Настройки  ", padding=8)
        settings_frame.pack(fill="x", pady=5, side="bottom")

        ttk.Label(settings_frame, text="Повторов: ", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.count_entry = ttk.Entry(settings_frame, font=("Consolas", 11))
        self.count_entry.insert(0, "1")
        self.count_entry.pack(fill="x", pady=2)
        self.clipboard.bind_widget(self.count_entry)

        self.delay_label = ttk.Label(settings_frame, text="⏱ 1 сек",
                                     font=("Segoe UI", 9), foreground="#00d26a")
        self.delay_label.pack(anchor="w", pady=3)

    def create_right_panel(self, parent):
        msg_frame = ttk.LabelFrame(parent, text=" 💬 Сообщение  ", padding=8)
        msg_frame.pack(fill="both", expand=True, pady=(0, 8))

        toolbar = ttk.Frame(msg_frame)
        toolbar.pack(fill="x", pady=(0, 5))
        ttk.Button(toolbar, text="📋 Вставить",
                   command=self.paste_to_message).pack(side="left", padx=2)
        ttk.Button(toolbar, text="🗑 Очистить",
                   command=self.clear_message).pack(side="left", padx=2)
        self.char_label = ttk.Label(toolbar, text="0 симв.",
                                    font=("Segoe UI", 8), foreground="#6c757d")
        self.char_label.pack(side="right", padx=5)

        self.message_text = scrolledtext.ScrolledText(
            msg_frame, font=("Consolas", 10), wrap=tk.WORD)
        self.message_text.pack(fill="both", expand=True)
        self.message_text.bind("<KeyRelease>", lambda e: self.update_char_count())
        self.clipboard.bind_widget(self.message_text)

        bottom = ttk.Frame(parent)
        bottom.pack(fill="x")

        ctrl_frame = ttk.LabelFrame(bottom, text=" 🎮 Управление  ", padding=8)
        ctrl_frame.pack(fill="x", pady=(0, 8))

        btns = ttk.Frame(ctrl_frame)
        btns.pack(fill="x", pady=5)
        self.send_btn  = ttk.Button(btns, text="▶ Старт",  command=self.start_single_send)
        self.send_btn.pack(side="left", padx=2, fill="x", expand=True)
        self.spam_btn  = ttk.Button(btns, text="🚀 100x",  command=self.start_mass_send)
        self.spam_btn.pack(side="left", padx=2, fill="x", expand=True)
        self.pause_btn = ttk.Button(btns, text="⏸ Пауза", command=self.toggle_pause, state='disabled')
        self.pause_btn.pack(side="left", padx=2, fill="x", expand=True)
        self.stop_btn  = ttk.Button(btns, text="⏹ Стоп",  command=self.stop_sending,  state='disabled')
        self.stop_btn.pack(side="left", padx=2, fill="x", expand=True)

        prog_frame = ttk.Frame(ctrl_frame)
        prog_frame.pack(fill="x", pady=3)
        self.progress_var = tk.StringVar(value="Готов")
        ttk.Label(prog_frame, textvariable=self.progress_var,
                  font=("Segoe UI", 9, "bold")).pack(side="left")
        self.progress_bar = ttk.Progressbar(prog_frame, mode='determinate')
        self.progress_bar.pack(side="right", fill="x", expand=True, padx=10)

        log_frame = ttk.LabelFrame(bottom, text=" 📋 Лог  ", padding=8)
        log_frame.pack(fill="both", expand=True)

        log_toolbar = ttk.Frame(log_frame)
        log_toolbar.pack(fill="x", pady=(0, 3))
        ttk.Button(log_toolbar, text="🗑 Очистить",
                   command=self.clear_log).pack(side="left", padx=2)
        ttk.Button(log_toolbar, text="📋 Копировать",
                   command=self.copy_log).pack(side="left", padx=2)

        self.log_text = scrolledtext.ScrolledText(
            log_frame, font=("Consolas", 8), height=8, state='disabled')
        self.log_text.pack(fill="both", expand=True)
        self.clipboard.bind_widget(self.log_text)

        # ← ИЗМЕНЕНО: убрана подпись про Ctrl+V/C/X
        self.status_var = tk.StringVar(value="🟢 Готов")
        ttk.Label(self.root, textvariable=self.status_var,
                  font=("Segoe UI", 8), padding=4).pack(fill="x", side="bottom")

    def setup_modern_theme(self):
        self.colors = {
            'bg':              '#1a1a2e', 'fg':          '#eaeaea',
            'fg_dim':          '#a0a0a0', 'accent':     '#e94560',
            'accent_hover':    '#ff6b6b', 'success':    '#00d26a',
            'warning':         '#ffc107', 'error':      '#ff6b6b',
            'info':            '#4dabf7', 'entry_bg':   '#0f3460',
            'entry_fg':        '#ffffff', 'button_bg':  '#0f3460',
            'button_fg':       '#ffffff', 'frame_bg':   '#16213e',
            'labelframe_fg':   '#e94560', 'text_bg':    '#0f3460',
            'text_fg':         '#ffffff', 'select_bg':  '#e94560',
            'select_fg':       '#ffffff', 'progress':   '#e94560',
            'progress_trough': '#0f3460',
        }
        c = self.colors
        self.root.configure(bg=c['bg'])

        style = ttk.Style()
        style.theme_use('clam')
        style.configure('.', background=c['bg'], foreground=c['fg'],
                        fieldbackground=c['entry_bg'], font=("Segoe UI", 9))
        style.configure('TLabel',     background=c['bg'],        foreground=c['fg'],            font=("Segoe UI", 9))
        style.configure('TButton',    background=c['button_bg'], foreground=c['button_fg'],     font=("Segoe UI", 9, "bold"), padding=5)
        style.map('TButton', background=[('active', c['accent']), ('pressed', c['accent_hover'])])
        style.configure('TEntry',     fieldbackground=c['entry_bg'], foreground=c['entry_fg'],  insertcolor=c['fg'], font=("Consolas", 9), padding=4)
        style.configure('TLabelframe',       background=c['frame_bg'], foreground=c['labelframe_fg'], font=("Segoe UI", 9, "bold"))
        style.configure('TLabelframe.Label', background=c['frame_bg'], foreground=c['labelframe_fg'], font=("Segoe UI", 9, "bold"))
        style.configure('TRadiobutton', background=c['bg'], foreground=c['fg'],                 font=("Segoe UI", 8), indicatorcolor=c['accent'])
        style.configure('TProgressbar', background=c['progress'], troughcolor=c['progress_trough'], borderwidth=0)

        self.root.option_add('*Text.Background',        c['text_bg'])
        self.root.option_add('*Text.Foreground',        c['text_fg'])
        self.root.option_add('*Text.InsertBackground',  c['fg'])
        self.root.option_add('*Text.SelectBackground',  c['select_bg'])
        self.root.option_add('*Text.SelectForeground',  c['select_fg'])
        self.root.option_add('*Text.Font',              'Consolas 9')
        self.root.option_add('*Entry.Background',       c['entry_bg'])
        self.root.option_add('*Entry.Foreground',       c['entry_fg'])
        self.root.option_add('*Entry.InsertBackground', c['fg'])
        self.root.option_add('*Entry.SelectBackground', c['select_bg'])
        self.root.option_add('*Entry.SelectForeground', c['select_fg'])
        self.root.option_add('*Entry.Font',             'Consolas 9')

    def paste_token(self):
        try:
            text = self.root.clipboard_get().strip()
            self.token_entry.delete(0, tk.END)
            self.token_entry.insert(0, text)
            self.log("📋 Токен вставлен", "#4dabf7")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def paste_chat_id(self):
        try:
            text = self.root.clipboard_get().strip()
            self.chat_id_entry.delete(0, tk.END)
            self.chat_id_entry.insert(0, text)
            self.log("📋 Chat ID вставлен", "#4dabf7")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def paste_to_message(self):
        try:
            self.message_text.insert("insert", self.root.clipboard_get())
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def clear_message(self):
        self.message_text.delete("1.0", tk.END)

    def update_char_count(self):
        self.char_label.config(text=f"{len(self.message_text.get('1.0','end-1c'))} симв.")

    def toggle_file_selection(self):
        ct = self.content_type.get()
        if ct == "text":
            self.select_file_btn.config(state='disabled')
            self.clear_file_btn.config(state='disabled')
            self.file_label.config(text="Не выбран", foreground="#6c757d")
            self.file_icon.config(text="📄")
        else:
            self.select_file_btn.config(state='normal')
            self.clear_file_btn.config(state='normal')
            self.file_icon.config(text={"photo": "🖼️", "video": "🎬", "document": "📎"}.get(ct, "📄"))

    def select_file(self):
        ct = self.content_type.get()
        ft = {
            "photo":    [("Изображения", "*.jpg *.jpeg *.png *.gif *.bmp *.webp")],
            "video":    [("Видео",        "*.mp4 *.avi *.mov *.mkv *.wmv")],
            "document": [("Все файлы",    "*.*")],
        }.get(ct, [("Все файлы", "*.*")])
        path = filedialog.askopenfilename(title="Выберите файл", filetypes=ft)
        if path:
            self.selected_file_path = path
            name = os.path.basename(path)
            size = os.path.getsize(path) / (1024 * 1024)
            self.file_label.config(text=f"{name} ({size:.1f} MB)", foreground="#00d26a")
            if size > 50:
                messagebox.showwarning("⚠️", "Файл > 50 МБ!")

    def clear_file(self):
        self.selected_file_path = None
        self.file_label.config(text="Не выбран", foreground="#6c757d")
        self.file_icon.config(text="📄")

    def show_id_help(self):
        messagebox.showinfo("ℹ️",
            "1. Напишите боту\n"
            "2. Откройте: https://api.telegram.org/bot<ТОКЕН>/getUpdates\n"
            "3. Найдите 'id'")

    def log(self, message, color="#eaeaea"):
        self.log_text.config(state='normal')
        tag = f"t{int(time.time()*1000)}{id(message)}"
        self.log_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {message}\n", tag)
        self.log_text.tag_config(tag, foreground=color)
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')

    def update_status(self, message):
        self.root.after(0, lambda: self.status_var.set(message))

    def toggle_pause(self):
        self.is_paused = not self.is_paused
        self.pause_btn.config(text="▶️ Продолжить" if self.is_paused else "⏸ Пауза")
        self.update_status("🟡 Пауза" if self.is_paused else "🟢 Возобновлено")
        self.log("⏸️ Пауза" if self.is_paused else "▶️ Возобновлено",
                 "#ffc107" if self.is_paused else "#00d26a")

    def stop_sending(self):
        self.is_stopped = True
        self.is_paused  = False
        self.update_status("🔴 Остановлено")
        self.log("⏹️ Остановлено", "#ff6b6b")
        self.root.after(0, self.reset_buttons)

    def reset_buttons(self):
        self.send_btn.config(state='normal')
        self.spam_btn.config(state='normal')
        self.pause_btn.config(state='disabled', text="⏸ Пауза")
        self.stop_btn.config(state='disabled')
        self.progress_var.set("Готов")
        self.progress_bar['value'] = 0
        self._send_thread_running = False
        if self.content_type.get() != "text":
            self.select_file_btn.config(state='normal')
            self.clear_file_btn.config(state='normal')

    def clear_log(self):
        self.log_text.config(state='normal')
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state='disabled')

    def copy_log(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.log_text.get("1.0", "end-1c"))

    def send_text_message(self, token, chat_id, text):
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                data={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
                timeout=10
            )
            if r.status_code == 200:
                return True, "Успешно", {}
            d = r.json()
            return False, d.get('description', 'Ошибка'), d
        except Exception as e:
            return False, str(e), {}

    def send_media_message(self, token, chat_id, file_path, caption, media_type):
        endpoints = {
            "photo":    f"https://api.telegram.org/bot{token}/sendPhoto",
            "video":    f"https://api.telegram.org/bot{token}/sendVideo",
            "document": f"https://api.telegram.org/bot{token}/sendDocument",
        }
        try:
            with open(file_path, 'rb') as f:
                r = requests.post(
                    endpoints[media_type],
                    files={media_type: f},
                    data={"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"},
                    timeout=120
                )
            if r.status_code == 200:
                return True, "Успешно", {}
            d = r.json()
            return False, d.get('description', 'Ошибка'), d
        except Exception as e:
            return False, str(e), {}

    def process_sending(self, total_count):
        token        = self.token_entry.get().strip()
        chat_id      = self.chat_id_entry.get().strip()
        text         = self.message_text.get("1.0", tk.END).strip()
        content_type = self.content_type.get()

        if not token or not chat_id:
            self.root.after(0, lambda: messagebox.showerror("❌", "Введите Токен и Chat ID!"))
            self.root.after(0, self.reset_buttons)
            return
        if content_type != "text" and not self.selected_file_path:
            self.root.after(0, lambda: messagebox.showerror("❌", "Выберите файл!"))
            self.root.after(0, self.reset_buttons)
            return

        self.root.after(0, lambda: [
            self.send_btn.config(state='disabled'),
            self.spam_btn.config(state='disabled'),
            self.pause_btn.config(state='normal'),
            self.stop_btn.config(state='normal'),
            self.select_file_btn.config(state='disabled'),
        ])
        self.is_paused  = False
        self.is_stopped = False
        self.log(f"🚀 Старт: {total_count}", "#4dabf7")
        self.update_status("🔄 Отправка...")

        media_labels = {"photo": "📷 Фото", "video": "🎬 Видео", "document": "📎 Файл"}
        delay = 1

        success, fail = 0, 0
        for i in range(total_count):
            if self.is_stopped: break

            while self.is_paused and not self.is_stopped:
                self.update_status("🟡 Пауза...")
                time.sleep(0.5)
            if self.is_stopped: break

            now = time.time()
            if now < self.pause_until:
                rem = int(self.pause_until - now)
                self.update_status(f"⏱ Лимит: {rem} сек")
                self.root.after(0, lambda r=rem:
                                self.delay_label.config(text=f"⏱ {r} сек", foreground="#ff6b6b"))
                while time.time() < self.pause_until and not self.is_stopped:
                    time.sleep(1)
                self.root.after(0, lambda:
                                self.delay_label.config(text=f"⏱ {delay} сек", foreground="#00d26a"))
            if self.is_stopped: break

            if content_type == "text":
                ok, msg, err = self.send_text_message(token, chat_id, text)
            else:
                ok, msg, err = self.send_media_message(
                    token, chat_id, self.selected_file_path, text, content_type)

            if ok:
                success += 1
                self.root.after(0, lambda c=i+1: self.log(f"✅ #{c}", "#00d26a"))
                self.chat_window.notify_sent(
                    text,
                    media_label=media_labels.get(content_type),
                    count=i+1
                )
            else:
                fail += 1
                if err and err.get('error_code') == 429:
                    retry = err.get('parameters', {}).get('retry_after', 60)
                    self.pause_until = time.time() + retry
                    self.root.after(0, lambda r=retry: self.log(f"⚠️ FLOOD: {r} сек", "#ff6b6b"))
                else:
                    self.root.after(0, lambda m=msg, c=i+1: self.log(f"❌ #{c}: {m}", "#ff6b6b"))

            self.root.after(0, lambda p=((i+1)/total_count)*100, s=success, f=fail, c=i+1:
                            self.update_progress(p, s, f, c))
            if i < total_count - 1 and not self.is_stopped:
                time.sleep(delay)

        self.root.after(0, lambda: self.log(f"🏁 Готово. ✓{success} ✗{fail}", "#4dabf7"))
        self.root.after(0, lambda: self.update_status("✅ Готов"))
        self.root.after(0, self.reset_buttons)

    def update_progress(self, percent, success, fail, current):
        self.progress_var.set(f"#{current} | ✓{success} | ✗{fail}")
        self.progress_bar['value'] = percent

    def start_single_send(self):
        if self._send_thread_running: return
        self._send_thread_running = True
        try:   count = int(self.count_entry.get())
        except: count = 1
        threading.Thread(target=self.process_sending, args=(count,), daemon=True).start()

    def start_mass_send(self):
        if self._send_thread_running: return
        try:   count = int(self.count_entry.get())
        except: count = 100
        if count < 2: count = 100
        if messagebox.askyesno("⚠️", f"Отправить {count} сообщений?"):
            self._send_thread_running = True
            threading.Thread(target=self.process_sending, args=(count,), daemon=True).start()

if __name__ == "__main__":
    root = tk.Tk()
    app  = TelegramSenderApp(root)
    root.mainloop()