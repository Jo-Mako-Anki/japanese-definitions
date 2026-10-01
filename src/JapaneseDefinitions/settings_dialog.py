from aqt import dialogs, mw
from aqt.qt import (
    QAbstractItemView,
    QAction,
    QCheckBox,
    QComboBox,
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QKeySequence,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    Qt,
)
from aqt.utils import askUser, showWarning, tooltip

from .config_util import get_config, load_overrides, save_config, save_overrides
from .core import dictionary
from .dictionary import Dictionary
from .pos_data import DEFAULT_SHORT_LABELS, POS_DESCRIPTIONS
from .ui_common import (
    CAPITALIZATION_OPTIONS,
    FORMAT_OPTIONS,
    NUMBER_OPTIONS,
    all_field_names,
    ensure_loaded,
    entry_summary,
    make_combo,
    make_description,
    make_section_title,
    make_separator,
    rebuild_cache,
)


SHORTCUTS = [
    ("shortcut_reviewer_choose", "Reviewer — Choose Definition", "reviewer"),
    ("shortcut_browser_choose", "Browser — Choose Definition", "browser"),
    ("shortcut_browser_populate", "Browser — Populate Definitions", "browser"),
    ("shortcut_settings", "Main window — Open settings", "main"),
]


def portable(seq_text):
    if not seq_text:
        return ""
    return QKeySequence(seq_text).toString(QKeySequence.SequenceFormat.PortableText)


# ============================================================
# PREVIEW DATA
# ============================================================

PREVIEW_SENSES = [
    {"definition": "to drink; to gulp; to swallow", "pos": ["v5m", "vt"], "uk": False},
    {"definition": "to smoke (tobacco)", "pos": ["v5m", "vt"], "uk": False},
    {"definition": "to accept (e.g. demands)", "pos": ["v5m", "vt"], "uk": False},
]

_preview_dict = Dictionary()
_preview_dict.furigana = {
    "走り出す\tはしりだす": (("走", "はし"), ("り", ""), ("出", "だ"), ("す", "")),
    "日本語\tにほんご": (("日本", "にほん"), ("語", "ご")),
}
PREVIEW_ENTRIES = [
    {"kanji": [{"word": "走り出す", "pri": 0, "infos": []}],
     "readings": [{"word": "はしりだす", "pri": 0, "infos": [], "restr": [], "nokanji": False}]},
    {"kanji": [{"word": "日本語", "pri": 0, "infos": []}],
     "readings": [{"word": "にほんご", "pri": 0, "infos": [], "restr": [], "nokanji": False}]},
]


# ============================================================
# SETTINGS DIALOG
# ============================================================

class SettingsDialog(QDialog):

    def __init__(self, parent=None, on_saved=None):

        super().__init__(parent or mw)

        self.cfg = get_config()
        self.on_saved = on_saved
        self.pos_labels = dict(self.cfg.get("pos_labels") or {})

        self.setWindowTitle("Japanese Definitions — Settings")
        self.setMinimumWidth(620)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)

        title = QLabel("Japanese Definitions")
        title.setStyleSheet("QLabel { font-size: 20px; font-weight: bold; }")
        layout.addWidget(title)
        layout.addWidget(make_description(
            "Configure how Japanese definitions are added to your Anki cards."
        ))

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self.tabs.addTab(self._fields_tab(), "Fields")
        self.tabs.addTab(self._definitions_tab(), "Definitions")
        self.tabs.addTab(self._pos_tab(), "Part of speech")
        self.tabs.addTab(self._reading_tab(), "Furigana")
        self.tabs.addTab(self._lookup_tab(), "Lookup")
        self.tabs.addTab(self._shortcuts_tab(), "Shortcuts")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._update_definition_preview()
        self._update_reading_preview()
        self._update_pos_widgets()
        self._check_shortcuts()

    # --------------------------------------------------------
    # Helpers
    # --------------------------------------------------------

    def _field_combo(self, value):
        combo = QComboBox()
        combo.setEditable(True)
        names = all_field_names()
        combo.addItems(names)
        combo.setCurrentText(value or "")
        completer = QCompleter(names, combo)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        combo.setCompleter(completer)
        combo.setMinimumHeight(28)
        return combo

    @staticmethod
    def _page():
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(12, 12, 12, 12)
        return w, v

    @staticmethod
    def _preview_label(rich=True):
        label = QLabel()
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.RichText if rich else Qt.TextFormat.PlainText)
        label.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Sunken)
        label.setContentsMargins(10, 8, 10, 8)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return label

    # --------------------------------------------------------
    # Tabs
    # --------------------------------------------------------

    def _fields_tab(self):

        w, v = self._page()
        v.addWidget(make_section_title("INPUT"))

        form_in = QFormLayout()
        self.input_field = self._field_combo(self.cfg["input_field"])
        form_in.addRow("Input field (word):", self.input_field)
        v.addLayout(form_in)
        v.addWidget(make_description(
            "The field containing the Japanese word to look up."
        ))

        v.addWidget(make_separator())

        v.addWidget(make_section_title("OUTPUT"))

        form_out = QFormLayout()
        self.definition_field = self._field_combo(self.cfg["definition_field"])
        self.pos_field = self._field_combo(self.cfg["pos_field"])
        self.reading_field = self._field_combo(self.cfg["reading_field"])
        form_out.addRow("Definition field:", self.definition_field)
        form_out.addRow("Part-of-speech field:", self.pos_field)
        form_out.addRow("Input (Furigana) field:", self.reading_field)
        v.addLayout(form_out)

        v.addWidget(make_description(
            "Input (Furigana) receives the word with its furigana, e.g. 覚[かく]悟[ご]. "
            "It is only filled when enabled in the 'Furigana' tab, and the "
            "part-of-speech field only when 'Separate field' is chosen in the "
            "'Part of speech' tab. Notes without these fields are simply skipped for them."
        ))

        v.addWidget(make_separator())

        v.addWidget(make_section_title("EXISTING CONTENT"))
        self.overwrite = QCheckBox("Overwrite fields that already contain something")
        self.overwrite.setChecked(self.cfg.get("overwrite_existing", False))
        v.addWidget(self.overwrite)
        v.addWidget(make_description(
            "Applies to 'Populate Definitions'. When unchecked, only empty fields are "
            "filled. 'Choose Definition' always overwrites, since you pick explicitly. "
            "Populate Definitions can be undone with Ctrl+Z (Edit → Undo)."
        ))

        v.addStretch()
        return w

    def _definitions_tab(self):

        w, v = self._page()
        v.addWidget(make_section_title("DEFINITIONS"))

        form = QFormLayout()
        self.number = make_combo(NUMBER_OPTIONS, self.cfg.get("number_of_definitions", 1))
        self.fmt = make_combo(FORMAT_OPTIONS, self.cfg.get("definition_format", "plain"))
        self.cap = make_combo(CAPITALIZATION_OPTIONS, self.cfg.get("capitalization", "none"))
        self.semi = QCheckBox("Replace ';' with ','")
        self.semi.setChecked(self.cfg.get("replace_semicolons", False))
        form.addRow("Number of definitions:", self.number)
        form.addRow("Definition format:", self.fmt)
        form.addRow("Capitalization:", self.cap)
        form.addRow("", self.semi)
        v.addLayout(form)

        v.addWidget(make_section_title("PREVIEW"))
        self.def_preview = self._preview_label()
        v.addWidget(self.def_preview)

        for c in (self.number, self.fmt, self.cap):
            c.currentIndexChanged.connect(self._update_definition_preview)
        self.semi.stateChanged.connect(self._update_definition_preview)

        v.addStretch()
        return w

    def _pos_tab(self):

        w, v = self._page()
        v.addWidget(make_section_title("PART OF SPEECH"))

        form = QFormLayout()

        self.pos_placement = make_combo(
            [
                ("Don't add", "none"),
                ("Separate field", "field"),
                ("Inline, before the definitions", "inline"),
            ],
            self.cfg.get("pos_placement", "none"),
        )
        form.addRow("Placement:", self.pos_placement)

        self.pos_style = make_combo(
            [
                ("Short labels (customizable)", "custom"),
                ("Full JMdict description", "full"),
                ("JMdict codes (v1, n, adj-i…)", "code"),
            ],
            self.cfg.get("pos_label_style", "custom"),
        )
        labels_btn = QPushButton("Edit short labels…")
        labels_btn.clicked.connect(self._edit_pos_labels)
        row = QHBoxLayout()
        row.addWidget(self.pos_style, 1)
        row.addWidget(labels_btn)
        self.labels_btn = labels_btn
        form.addRow("Label style:", row)

        self.pos_sep = QLineEdit(self.cfg.get("pos_separator", ", "))
        form.addRow("Separator:", self.pos_sep)

        self.pos_template = QLineEdit(self.cfg.get("pos_inline_template", ""))
        form.addRow("Inline template:", self.pos_template)

        self.pos_every = QCheckBox("Repeat on every definition (otherwise only when it changes)")
        self.pos_every.setChecked(self.cfg.get("pos_inline_every_sense", False))
        form.addRow("", self.pos_every)

        v.addLayout(form)
        v.addWidget(make_description(
            "Inline template: {pos} is replaced by the labels and {definition} by the "
            "definition. HTML is allowed, e.g. <i>({pos})</i> {definition}"
        ))

        v.addWidget(make_section_title("PREVIEW"))
        self.pos_preview = self._preview_label()
        v.addWidget(self.pos_preview)

        self.pos_placement.currentIndexChanged.connect(self._update_pos_widgets)
        self.pos_style.currentIndexChanged.connect(self._update_pos_widgets)
        self.pos_sep.textChanged.connect(self._update_definition_preview)
        self.pos_template.textChanged.connect(self._update_definition_preview)
        self.pos_every.stateChanged.connect(self._update_definition_preview)

        v.addStretch()
        return w

    def _reading_tab(self):

        w, v = self._page()
        v.addWidget(make_section_title("INPUT (FURIGANA)"))

        self.fill_reading = QCheckBox("Fill the Input (Furigana) field")
        self.fill_reading.setChecked(self.cfg.get("fill_reading", False))
        v.addWidget(self.fill_reading)

        form = QFormLayout()
        self.reading_format = make_combo(
            [
                ("Kana only (はしりだす)", "kana"),
                ("Anki furigana (走[はし]り 出[だ]す)", "anki"),
                ("HTML ruby (<ruby>…</ruby>)", "ruby"),
            ],
            self.cfg.get("reading_format", "anki"),
        )
        self.granularity = make_combo(
            [
                ("Per kanji (日本[にほん]語[ご])", "kanji"),
                ("Per word (日本語[にほんご])", "word"),
            ],
            self.cfg.get("furigana_granularity", "kanji"),
        )
        form.addRow("Format:", self.reading_format)
        form.addRow("Furigana:", self.granularity)
        v.addLayout(form)

        v.addWidget(make_description(
            "Uses JmdictFurigana.json to place furigana on each kanji. If a word is "
            "conjugated (食べた), the reading of the dictionary form (食べる) is used."
        ))

        v.addWidget(make_section_title("PREVIEW"))
        self.reading_preview = self._preview_label(rich=False)
        v.addWidget(self.reading_preview)

        for c in (self.reading_format, self.granularity):
            c.currentIndexChanged.connect(self._update_reading_preview)
        self.fill_reading.stateChanged.connect(self._update_reading_preview)

        v.addStretch()
        return w

    def _lookup_tab(self):

        w, v = self._page()
        v.addWidget(make_section_title("LOOKUP"))

        self.ignore_furigana = QCheckBox("Ignore furigana in brackets — 覚悟[かくご] → 覚悟")
        self.ignore_furigana.setChecked(self.cfg.get("ignore_furigana", True))
        v.addWidget(self.ignore_furigana)

        self.deinflect = QCheckBox("Find the dictionary form of conjugated words — 食べた → 食べる")
        self.deinflect.setChecked(self.cfg.get("deinflect", True))
        v.addWidget(self.deinflect)

        self.preload = QCheckBox("Load the dictionary in the background when Anki starts")
        self.preload.setChecked(self.cfg.get("preload_on_startup", True))
        v.addWidget(self.preload)

        v.addWidget(make_section_title("REMEMBERED CHOICES"))

        self.remember = QCheckBox("'Remember this choice' is checked by default in Choose Definition")
        self.remember.setChecked(self.cfg.get("remember_choices", True))
        v.addWidget(self.remember)

        v.addWidget(make_description(
            "When you pick an entry with Choose Definition, it can be remembered for "
            "that word. Populate Definitions will then use it instead of the automatic guess."
        ))

        manage = QPushButton("Manage remembered choices…")
        manage.clicked.connect(lambda: ensure_loaded(self, lambda: OverridesDialog(self).exec()))
        v.addWidget(manage)

        v.addWidget(make_section_title("DICTIONARY CACHE"))
        v.addWidget(make_description(
            "The dictionary is converted once into a fast cache (user_files/). It is "
            "rebuilt automatically when JMdict_e.xml or JmdictFurigana.json change."
        ))
        rebuild = QPushButton("Rebuild cache now")
        rebuild.clicked.connect(lambda: rebuild_cache(self))
        v.addWidget(rebuild)

        v.addStretch()
        return w

    def _shortcuts_tab(self):

        w, v = self._page()
        v.addWidget(make_section_title("KEYBOARD SHORTCUTS"))

        form = QFormLayout()
        self.shortcut_edits = {}

        for key, label, _ctx in SHORTCUTS:

            edit = QKeySequenceEdit(QKeySequence(self.cfg.get(key, "")))
            try:
                edit.setMaximumSequenceLength(1)
            except AttributeError:
                edit.editingFinished.connect(lambda e=edit: self._truncate(e))
            edit.keySequenceChanged.connect(lambda _s: self._check_shortcuts())

            clear = QPushButton("Clear")
            clear.clicked.connect(lambda _c=False, e=edit: e.clear())

            row = QHBoxLayout()
            row.addWidget(edit, 1)
            row.addWidget(clear)
            form.addRow(label + ":", row)

            self.shortcut_edits[key] = edit

        v.addLayout(form)
        v.addWidget(make_description(
            "Click a box and press the key combination. Leave empty to disable. "
            "Changes apply immediately (no restart needed)."
        ))

        self.shortcut_warning = QLabel()
        self.shortcut_warning.setWordWrap(True)
        self.shortcut_warning.setStyleSheet("QLabel { color: #d9822b; }")
        v.addWidget(self.shortcut_warning)

        v.addStretch()
        return w

    # --------------------------------------------------------
    # Shortcuts
    # --------------------------------------------------------

    @staticmethod
    def _truncate(edit):
        seq = edit.keySequence()
        if seq.count() > 1:
            try:
                edit.setKeySequence(QKeySequence(seq[0]))
            except Exception:
                pass

    def _shortcut_value(self, key):
        return self.shortcut_edits[key].keySequence().toString(
            QKeySequence.SequenceFormat.PortableText
        )

    @staticmethod
    def _anki_reviewer_keys():
        keys = {}
        try:
            for k, _fn in mw.reviewer._shortcutKeys():
                if isinstance(k, str):
                    keys[portable(k)] = True
        except Exception:
            pass
        return keys

    @staticmethod
    def _anki_browser_keys():
        from . import registered_actions

        keys = {}
        try:
            browser = dialogs._dialogs.get("Browser", [None, None])[1]
            if browser:
                for action in browser.findChildren(QAction):
                    if action in registered_actions():
                        continue
                    for seq in action.shortcuts():
                        s = seq.toString(QKeySequence.SequenceFormat.PortableText)
                        if s:
                            keys[s] = action.text().replace("&", "")
        except Exception:
            pass
        return keys

    def _shortcut_conflicts(self):

        warnings = []
        values = {k: self._shortcut_value(k) for k, _l, _c in SHORTCUTS}
        labels = {k: l for k, l, _c in SHORTCUTS}
        contexts = {k: c for k, _l, c in SHORTCUTS}

        # Duplicates among our own shortcuts (same context, or global)
        keys = list(values)
        for i, a in enumerate(keys):
            for b in keys[i + 1:]:
                if values[a] and values[a] == values[b] and (
                    contexts[a] == contexts[b] or "main" in (contexts[a], contexts[b])
                ):
                    warnings.append(f"{labels[a]} and {labels[b]} both use {values[a]}.")

        reviewer_keys = self._anki_reviewer_keys()
        rv = values["shortcut_reviewer_choose"]
        if rv and rv in reviewer_keys:
            warnings.append(
                f"{rv} is already used by Anki in the reviewer. "
                "Neither shortcut may work."
            )

        browser_keys = self._anki_browser_keys()
        for k in ("shortcut_browser_choose", "shortcut_browser_populate"):
            if values[k] and values[k] in browser_keys:
                warnings.append(
                    f"{values[k]} is already used in the browser by "
                    f"'{browser_keys[values[k]]}'."
                )

        return warnings

    def _check_shortcuts(self):
        warnings = self._shortcut_conflicts()
        self.shortcut_warning.setText("⚠ " + "\n⚠ ".join(warnings) if warnings else "")

    # --------------------------------------------------------
    # Previews
    # --------------------------------------------------------

    def _current_cfg(self):

        cfg = dict(self.cfg)
        cfg.update({
            "input_field": self.input_field.currentText().strip(),
            "definition_field": self.definition_field.currentText().strip(),
            "reading_field": self.reading_field.currentText().strip(),
            "pos_field": self.pos_field.currentText().strip(),
            "overwrite_existing": self.overwrite.isChecked(),
            "number_of_definitions": self.number.currentData(),
            "definition_format": self.fmt.currentData(),
            "capitalization": self.cap.currentData(),
            "replace_semicolons": self.semi.isChecked(),
            "pos_placement": self.pos_placement.currentData(),
            "pos_label_style": self.pos_style.currentData(),
            "pos_separator": self.pos_sep.text(),
            "pos_inline_template": self.pos_template.text() or "<i>({pos})</i> {definition}",
            "pos_inline_every_sense": self.pos_every.isChecked(),
            "pos_labels": self.pos_labels,
            "fill_reading": self.fill_reading.isChecked(),
            "reading_format": self.reading_format.currentData(),
            "furigana_granularity": self.granularity.currentData(),
            "ignore_furigana": self.ignore_furigana.isChecked(),
            "deinflect": self.deinflect.isChecked(),
            "preload_on_startup": self.preload.isChecked(),
            "remember_choices": self.remember.isChecked(),
        })
        for key, _label, _ctx in SHORTCUTS:
            cfg[key] = self._shortcut_value(key)
        return cfg

    def _update_definition_preview(self, *_):

        if not hasattr(self, "pos_preview") or not hasattr(self, "def_preview"):
            return

        cfg = self._current_cfg()
        senses = Dictionary.select_senses(
            {"senses": PREVIEW_SENSES}, cfg["number_of_definitions"]
        )
        html = dictionary.format_definition(senses, cfg)
        self.def_preview.setText(html)

        if cfg["pos_placement"] == "field":
            pos_html = (
                f"<b>{cfg['definition_field']}:</b><br>{html}<br><br>"
                f"<b>{cfg['pos_field']}:</b><br>{dictionary.format_pos(senses, cfg)}"
            )
        elif cfg["pos_placement"] == "inline":
            pos_html = html
        else:
            pos_html = "<i>Part of speech is not added.</i>"
        self.pos_preview.setText(pos_html)

    def _update_reading_preview(self, *_):

        if not hasattr(self, "reading_preview"):
            return

        cfg = self._current_cfg()
        lines = []
        for entry in PREVIEW_ENTRIES:
            written = entry["kanji"][0]["word"]
            lines.append(_preview_dict.format_reading(
                entry, written, cfg["reading_format"], cfg["furigana_granularity"]
            ))
        if not cfg["fill_reading"]:
            lines.append("(disabled — the Input (Furigana) field won't be filled)")
        self.reading_preview.setText("\n".join(lines))

    def _update_pos_widgets(self, *_):
        placement = self.pos_placement.currentData()
        inline = placement == "inline"
        self.pos_template.setEnabled(inline)
        self.pos_every.setEnabled(inline)
        self.pos_style.setEnabled(placement != "none")
        self.pos_sep.setEnabled(placement != "none")
        self.labels_btn.setEnabled(
            placement != "none" and self.pos_style.currentData() == "custom"
        )
        self._update_definition_preview()

    def _edit_pos_labels(self):
        dlg = PosLabelsDialog(self, self.pos_labels)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.pos_labels = dlg.result_labels()
            self._update_definition_preview()

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    def accept(self):

        cfg = self._current_cfg()

        if not cfg["input_field"]:
            showWarning("Input field cannot be empty.", parent=self)
            return

        if not cfg["definition_field"]:
            showWarning("Definition field cannot be empty.", parent=self)
            return

        if cfg["fill_reading"] and not cfg["reading_field"]:
            showWarning("Please set an Input (Furigana) field, or disable 'Fill the Input (Furigana) field'.", parent=self)
            return

        if cfg["pos_placement"] == "field" and not cfg["pos_field"]:
            showWarning("Please set a part-of-speech field.", parent=self)
            return

        if "{definition}" not in cfg["pos_inline_template"]:
            showWarning("The inline template must contain {definition}.", parent=self)
            return

        warnings = self._shortcut_conflicts()
        if warnings and not askUser(
            "Some shortcuts conflict:\n\n" + "\n".join(warnings) + "\n\nSave anyway?",
            parent=self,
        ):
            return

        save_config(cfg)

        if self.on_saved:
            self.on_saved(cfg)

        super().accept()
        tooltip("Settings saved.", parent=self.parent())


# ============================================================
# POS LABELS
# ============================================================

class PosLabelsDialog(QDialog):

    def __init__(self, parent, custom_labels):

        super().__init__(parent)
        self.setWindowTitle("Part-of-speech labels")
        self.setMinimumSize(720, 560)

        v = QVBoxLayout(self)
        v.addWidget(make_description(
            "Edit the 'Label' column. Several codes can share the same label (they are "
            "shown once). Leave a label empty to hide that part of speech."
        ))

        self.codes = list(POS_DESCRIPTIONS)
        self.table = QTableWidget(len(self.codes), 3)
        self.table.setHorizontalHeaderLabels(["Code", "JMdict description", "Label"])
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        labels = dict(DEFAULT_SHORT_LABELS)
        labels.update(custom_labels or {})

        for row, code in enumerate(self.codes):
            for col, text in enumerate((code, POS_DESCRIPTIONS[code], labels.get(code, ""))):
                item = QTableWidgetItem(text)
                if col < 2:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, col, item)

        v.addWidget(self.table)

        reset = QPushButton("Reset to defaults")
        reset.clicked.connect(self._reset)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        row = QHBoxLayout()
        row.addWidget(reset)
        row.addStretch()
        row.addWidget(buttons)
        v.addLayout(row)

    def _reset(self):
        for row, code in enumerate(self.codes):
            self.table.item(row, 2).setText(DEFAULT_SHORT_LABELS.get(code, ""))

    def result_labels(self):
        """Only differences from the defaults are kept."""
        out = {}
        for row, code in enumerate(self.codes):
            text = self.table.item(row, 2).text().strip()
            if text != DEFAULT_SHORT_LABELS.get(code, ""):
                out[code] = text
        return out


# ============================================================
# REMEMBERED CHOICES
# ============================================================

class OverridesDialog(QDialog):

    def __init__(self, parent):

        super().__init__(parent)
        self.setWindowTitle("Remembered choices")
        self.setMinimumSize(760, 480)

        self.overrides = load_overrides()

        v = QVBoxLayout(self)
        v.addWidget(make_description(
            "Words for which a specific dictionary entry was chosen. "
            "'Populate Definitions' uses these instead of the automatic guess. "
            "Use Choose Definition on a card to add or change one."
        ))

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Word", "Entry", "Definitions"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        v.addWidget(self.table)

        self._fill()

        remove = QPushButton("Remove selected")
        remove.clicked.connect(self._remove_selected)
        remove_all = QPushButton("Remove all")
        remove_all.clicked.connect(self._remove_all)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)

        row = QHBoxLayout()
        row.addWidget(remove)
        row.addWidget(remove_all)
        row.addStretch()
        row.addWidget(close)
        v.addLayout(row)

    def _fill(self):

        self.table.setRowCount(0)

        for word in sorted(self.overrides):
            ov = self.overrides[word]
            entry = dictionary.entries.get(ov.get("ent_seq")) if dictionary.loaded else None
            summary = entry_summary(entry) if entry else f"JMdict #{ov.get('ent_seq')}"
            senses = ov.get("senses")
            senses_text = ", ".join(str(i + 1) for i in senses) if senses else "default"

            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(word))
            self.table.setItem(row, 1, QTableWidgetItem(summary))
            self.table.setItem(row, 2, QTableWidgetItem(senses_text))

    def _remove_selected(self):
        rows = {i.row() for i in self.table.selectedIndexes()}
        for row in rows:
            word = self.table.item(row, 0).text()
            self.overrides.pop(word, None)
        save_overrides(self.overrides)
        self._fill()

    def _remove_all(self):
        if not self.overrides:
            return
        if askUser(f"Remove all {len(self.overrides)} remembered choices?", parent=self):
            self.overrides = {}
            save_overrides(self.overrides)
            self._fill()
