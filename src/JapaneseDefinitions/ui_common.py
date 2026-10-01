from aqt import mw
from aqt.operations import QueryOp
from aqt.qt import QComboBox, QFrame, QLabel
from aqt.utils import showWarning, tooltip

from .core import dictionary


# ============================================================
# WIDGETS
# ============================================================

def make_separator():
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    return line


def make_section_title(text):
    label = QLabel(text)
    label.setStyleSheet(
        "QLabel { font-size: 13px; font-weight: bold; margin-top: 8px; margin-bottom: 2px; }"
    )
    return label


def make_description(text):
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet("QLabel { color: #888888; font-size: 11px; margin-bottom: 4px; }")
    return label


def make_combo(options, current):
    """options: list of (label, value)."""
    combo = QComboBox()
    for label, value in options:
        combo.addItem(label, value)
    set_combo(combo, current)
    return combo


def set_combo(combo, value):
    for i in range(combo.count()):
        if combo.itemData(i) == value:
            combo.setCurrentIndex(i)
            return


NUMBER_OPTIONS = [(f"{n} definition{'s' if n > 1 else ''}", n) for n in range(1, 6)] + [
    ("All definitions", "all")
]

FORMAT_OPTIONS = [
    ("Plain — line breaks", "plain"),
    ("Bulleted list", "bulleted"),
    ("Numbered list", "numbered"),
]

CAPITALIZATION_OPTIONS = [
    ("No change (to drink; to gulp)", "none"),
    ("Capitalize every gloss (To drink; To gulp)", "all"),
    ("Capitalize first gloss only (To drink; to gulp)", "first"),
]


# ============================================================
# DICTIONARY LOADING
# ============================================================

def _progress(label):
    mw.taskman.run_on_main(lambda: mw.progress.update(label=label))


def ensure_loaded(parent, callback):
    """Load the dictionary in the background if needed, then call callback()."""

    if dictionary.loaded:
        callback()
        return

    def op(_col):
        return dictionary.load(progress=_progress)

    def done(ok):
        if not ok:
            showWarning(dictionary.error or "Could not load the dictionary.", parent=parent)
            return
        callback()

    QueryOp(parent=parent, op=op, success=done).with_progress(
        "Loading JMdict..."
    ).run_in_background()


def rebuild_cache(parent):

    def op(_col):
        dictionary.delete_cache()
        return dictionary.load(progress=_progress, force_rebuild=True)

    def done(ok):
        if ok:
            tooltip("Dictionary cache rebuilt.", parent=parent)
        else:
            showWarning(dictionary.error or "Could not rebuild the cache.", parent=parent)

    QueryOp(parent=parent, op=op, success=done).with_progress(
        "Rebuilding dictionary cache..."
    ).run_in_background()


def preload_in_background():

    if dictionary.loaded:
        return

    def done(fut):
        try:
            fut.result()
        except Exception as e:
            print(f"JapaneseDefinitions: preload failed: {e}")

    mw.taskman.run_in_background(dictionary.load, done)


def all_field_names():

    names = set()

    try:
        for model in mw.col.models.all():
            for fld in model["flds"]:
                names.add(fld["name"])
    except Exception:
        pass

    return sorted(names, key=str.lower)


def entry_summary(entry, max_len=60):
    kanji = ", ".join(k["word"] for k in entry["kanji"])
    readings = ", ".join(r["word"] for r in entry["readings"])
    gloss = entry["senses"][0]["definition"] if entry["senses"] else ""
    if len(gloss) > max_len:
        gloss = gloss[: max_len - 1] + "…"
    head = f"{kanji} 【{readings}】" if kanji else readings
    return f"{head} — {gloss}"
