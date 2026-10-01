from aqt.operations.note import update_note
from aqt.qt import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QVBoxLayout,
    QWidget,
    Qt,
)
from aqt.utils import showWarning, tooltip

from .config_util import get_config, load_overrides, save_overrides
from .core import compute_values, dictionary, input_word, target_fields
from .ui_common import (
    CAPITALIZATION_OPTIONS,
    FORMAT_OPTIONS,
    NUMBER_OPTIONS,
    ensure_loaded,
    make_combo,
    make_description,
    make_section_title,
    make_separator,
)

ROLE_INDEX = Qt.ItemDataRole.UserRole


def choose_definition_for_note(parent, note):
    """Shared entry point (browser and reviewer)."""

    cfg = get_config()

    for key in ("input_field", "definition_field"):
        if cfg[key] not in note:
            showWarning(
                "This note does not have the configured fields:\n\n"
                f"Input: {cfg['input_field']}\n"
                f"Definition: {cfg['definition_field']}",
                parent=parent,
            )
            return

    word = input_word(note, cfg)

    if not word:
        showWarning(f"The field '{cfg['input_field']}' is empty.", parent=parent)
        return

    def open_dialog():
        candidates = dictionary.find(word, cfg.get("deinflect", True))
        if not candidates:
            showWarning(f"No dictionary entry found for:\n\n{word}", parent=parent)
            return
        ChooseDialog(parent, note, word, cfg, candidates).exec()

    ensure_loaded(parent, open_dialog)


class ChooseDialog(QDialog):

    def __init__(self, parent, note, word, cfg, candidates):

        super().__init__(parent)

        self.note = note
        self.word = word
        self.cfg = cfg
        self.candidates = candidates
        self.overrides = load_overrides()
        self.override = self.overrides.get(word)

        self.setWindowTitle(f"Choose Definition — {word}")
        self.setMinimumSize(900, 760)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(8)

        title = QLabel("Choose a dictionary entry for")
        title.setStyleSheet("QLabel { font-size: 16px; font-weight: bold; }")
        layout.addWidget(title)

        word_label = QLabel(word)
        word_label.setStyleSheet("QLabel { font-size: 24px; font-weight: bold; }")
        layout.addWidget(word_label)
        layout.addWidget(make_separator())

        splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(splitter, 1)

        # ---------------- Candidates ----------------
        self.entry_list = QListWidget()
        self.entry_list.setStyleSheet(
            "QListWidget { font-size: 14px; }"
            "QListWidget::item { padding: 10px; border-bottom: 1px solid #dcdcdc; }"
        )
        for i, cand in enumerate(candidates):
            item = QListWidgetItem(self._candidate_text(cand))
            item.setData(ROLE_INDEX, i)
            self.entry_list.addItem(item)
        splitter.addWidget(self.entry_list)

        # ---------------- Settings ----------------
        bottom = QWidget()
        bl = QVBoxLayout(bottom)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.addWidget(make_section_title("DEFINITION SETTINGS"))

        form = QFormLayout()

        self.mode = make_combo(
            [("Automatic (first N)", "automatic"), ("Choose manually", "manual")],
            "manual" if self.override and self.override.get("senses") else "automatic",
        )
        form.addRow("Definition selection:", self.mode)

        self.number = make_combo(NUMBER_OPTIONS, cfg.get("number_of_definitions", 1))
        self.number_label = QLabel("Number of definitions:")
        form.addRow(self.number_label, self.number)

        self.sense_list = QListWidget()
        self.sense_list.setMaximumHeight(170)
        self.sense_label = QLabel("Choose definitions:")
        form.addRow(self.sense_label, self.sense_list)

        self.fmt = make_combo(FORMAT_OPTIONS, cfg.get("definition_format", "plain"))
        form.addRow("Definition format:", self.fmt)

        self.cap = make_combo(CAPITALIZATION_OPTIONS, cfg.get("capitalization", "none"))
        form.addRow("Capitalization:", self.cap)

        self.semi = QCheckBox("Replace ';' with ','")
        self.semi.setChecked(cfg.get("replace_semicolons", False))
        form.addRow("", self.semi)

        # Optional fields present in the note
        self.fill_reading = QCheckBox(f"Also fill Input (Furigana) field ({cfg.get('reading_field')})")
        self.fill_reading.setChecked(cfg.get("fill_reading", False))
        self.has_reading_field = bool(cfg.get("reading_field")) and cfg.get("reading_field") in note
        self.fill_reading.setVisible(self.has_reading_field)
        form.addRow("", self.fill_reading)

        self.fill_pos = QCheckBox(f"Also fill POS field ({cfg.get('pos_field')})")
        self.fill_pos.setChecked(cfg.get("pos_placement") == "field")
        self.has_pos_field = bool(cfg.get("pos_field")) and cfg.get("pos_field") in note
        self.fill_pos.setVisible(self.has_pos_field)
        form.addRow("", self.fill_pos)

        self.remember = QCheckBox(
            "Remember this choice for this word (used by 'Populate Definitions')"
        )
        self.remember.setChecked(cfg.get("remember_choices", True))
        form.addRow("", self.remember)

        bl.addLayout(form)

        bl.addWidget(make_section_title("PREVIEW"))
        self.preview = QLabel()
        self.preview.setWordWrap(True)
        self.preview.setTextFormat(Qt.TextFormat.RichText)
        self.preview.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Sunken)
        self.preview.setContentsMargins(10, 8, 10, 8)
        bl.addWidget(self.preview)

        bl.addWidget(make_description(
            "Double-click an entry to use it immediately with the settings above."
        ))

        splitter.addWidget(bottom)
        splitter.setSizes([420, 340])

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Use Selected")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # ---------------- Signals ----------------
        self.entry_list.currentRowChanged.connect(self._on_entry_changed)
        self.entry_list.itemDoubleClicked.connect(lambda _item: self.accept())
        self.mode.currentIndexChanged.connect(self._update_mode)
        for w in (self.number, self.fmt, self.cap):
            w.currentIndexChanged.connect(self._update_preview)
        self.semi.stateChanged.connect(self._update_preview)
        self.sense_list.itemChanged.connect(self._update_preview)

        # Initial selection (remembered choice if any)
        start = 0
        if self.override:
            for i, cand in enumerate(candidates):
                if cand["entry"]["id"] == self.override.get("ent_seq"):
                    start = i
                    break
        self.entry_list.setCurrentRow(start)
        self._update_mode()

    # --------------------------------------------------------

    def _candidate_text(self, cand):

        entry = cand["entry"]
        kanji = ", ".join(k["word"] for k in entry["kanji"])
        readings = ", ".join(r["word"] for r in entry["readings"])

        text = f"{kanji}   【{readings}】" if kanji else f"{readings}   (kana only)"

        if cand["reasons"]:
            text += f"\n← {self.word} → {cand['matched']}  ({', '.join(cand['reasons'])})"

        if any(s["uk"] for s in entry["senses"][:2]):
            text += "\nUsually written using kana"

        if self.override and self.override.get("ent_seq") == entry["id"]:
            text += "\n★ Remembered choice"

        text += "\n"

        prev = None
        for i, s in enumerate(entry["senses"], 1):
            line = f"\n{i}. "
            if s["pos"] != prev:
                labels = dictionary.pos_labels_for(s["pos"], self.cfg)
                if labels:
                    line += f"({', '.join(labels)}) "
            prev = s["pos"]
            text += line + s["definition"]

        return text

    def _current_candidate(self):
        item = self.entry_list.currentItem()
        if not item:
            return None
        return self.candidates[item.data(ROLE_INDEX)]

    def _on_entry_changed(self, _row):

        self.sense_list.blockSignals(True)
        self.sense_list.clear()

        cand = self._current_candidate()
        if cand:
            remembered = None
            if self.override and self.override.get("ent_seq") == cand["entry"]["id"]:
                remembered = self.override.get("senses")
            for i, s in enumerate(cand["entry"]["senses"]):
                item = QListWidgetItem(f"{i + 1}. {s['definition']}")
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                checked = remembered is not None and i in remembered
                item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
                self.sense_list.addItem(item)

        self.sense_list.blockSignals(False)
        self._update_preview()

    def _update_mode(self):
        manual = self.mode.currentData() == "manual"
        self.sense_list.setVisible(manual)
        self.sense_label.setVisible(manual)
        self.number.setVisible(not manual)
        self.number_label.setVisible(not manual)
        self._update_preview()

    def _checked_senses(self):
        return [
            i for i in range(self.sense_list.count())
            if self.sense_list.item(i).checkState() == Qt.CheckState.Checked
        ]

    def _local_cfg(self):
        cfg = dict(self.cfg)
        cfg["number_of_definitions"] = self.number.currentData()
        cfg["definition_format"] = self.fmt.currentData()
        cfg["capitalization"] = self.cap.currentData()
        cfg["replace_semicolons"] = self.semi.isChecked()
        return cfg

    def _selection(self):
        if self.mode.currentData() == "manual":
            return self._checked_senses()
        return None

    def _update_preview(self, *_args):

        cand = self._current_candidate()
        if not cand:
            self.preview.setText("")
            return

        indices = self._selection()
        if indices == []:
            self.preview.setText("<i>Check at least one definition.</i>")
            return

        values = compute_values(cand, indices, self._local_cfg())
        extra = f"<br><span style='color:#888'>Furigana: {values['reading']} · POS: {values['pos']}</span>"
        self.preview.setText(values["definition"] + extra)

    # --------------------------------------------------------

    def accept(self):

        cand = self._current_candidate()
        if not cand:
            return

        indices = self._selection()
        if indices == []:
            showWarning("Please select at least one definition.", parent=self)
            return

        cfg = self._local_cfg()
        values = compute_values(cand, indices, cfg)

        targets = target_fields(
            self.note,
            cfg,
            fill_reading=self.has_reading_field and self.fill_reading.isChecked(),
            fill_pos=self.has_pos_field and self.fill_pos.isChecked(),
            overwrite=True,
        )

        for key, field in targets.items():
            self.note[field] = values[key]

        if self.remember.isChecked():
            self.overrides[self.word] = {
                "ent_seq": cand["entry"]["id"],
                "senses": indices,
                "written": dictionary.best_written_form(
                    cand["entry"], cand["matched"], cand["form_type"]
                ),
            }
            save_overrides(self.overrides)

        parent = self.parent()
        super().accept()

        update_note(parent=parent, note=self.note).success(
            lambda _: tooltip("Definition updated.", parent=parent)
        ).run_in_background()
