"""
Japanese Definitions — add-on Anki
Adds JMdict definitions, readings (furigana) and parts of speech to your notes.
"""

from aqt import gui_hooks, mw
from aqt.operations import CollectionOp
from aqt.qt import QAction, QKeySequence
from aqt.utils import showInfo, showWarning

from .config_util import get_config, load_overrides
from .core import dictionary, fill_note
from .ui_common import preload_in_background


# ============================================================
# SHORTCUT REGISTRY
# ============================================================

# [(QAction, config key)] — so shortcuts can be updated live
_actions = []


def _register(action, config_key):
    _actions.append((action, config_key))
    action.setShortcut(QKeySequence(get_config().get(config_key, "")))


def registered_actions():
    alive = []
    for action, _key in _actions:
        try:
            action.text()
            alive.append(action)
        except RuntimeError:
            pass
    return alive


def apply_shortcuts(cfg=None):
    """Apply the configured shortcuts to existing actions."""

    cfg = cfg or get_config()
    still_alive = []

    for action, key in _actions:
        try:
            action.setShortcut(QKeySequence(cfg.get(key, "")))
            still_alive.append((action, key))
        except RuntimeError:
            # Action was deleted along with its window
            pass

    _actions[:] = still_alive

    # Reviewer shortcut
    if mw.state == "review":
        try:
            mw.clearStateShortcuts()
            mw.setStateShortcuts(mw.reviewer._shortcutKeys())
        except Exception as e:
            print(f"JapaneseDefinitions: could not refresh reviewer shortcuts: {e}")


# ============================================================
# SETTINGS
# ============================================================

def open_settings(parent=None):
    from .settings_dialog import SettingsDialog
    SettingsDialog(parent or mw, on_saved=apply_shortcuts).exec()


# ============================================================
# POPULATE DEFINITIONS (lot, annulable)
# ============================================================

class _PopulateResult:
    def __init__(self, changes, stats):
        self.changes = changes
        self.stats = stats


def _selected_note_ids(browser):
    getter = getattr(browser, "selected_notes", None) or browser.selectedNotes
    return list(getter())


def populate_selected(browser):

    note_ids = _selected_note_ids(browser)

    if not note_ids:
        showWarning("Please select at least one note.", parent=browser)
        return

    cfg = get_config()
    overrides = load_overrides()
    total = len(note_ids)

    def progress(label, value=None):
        def update():
            if value is None:
                mw.progress.update(label=label)
            else:
                mw.progress.update(label=label, value=value, max=total)
        mw.taskman.run_on_main(update)

    def op(col):

        if not dictionary.loaded:
            progress("Loading JMdict...")
            if not dictionary.load(progress=progress):
                raise Exception(dictionary.error or "Could not load the dictionary.")

        undo_pos = col.add_custom_undo_entry("Populate Definitions")

        stats = {
            "updated": 0, "not_found": 0, "already_filled": 0,
            "missing_fields": 0, "empty": 0,
        }
        not_found_words = []
        to_update = []

        for i, nid in enumerate(note_ids):

            if i % 25 == 0:
                progress(f"Adding definitions… {i}/{total}", i)

            note = col.get_note(nid)
            status = fill_note(note, cfg, overrides)
            stats[status] += 1

            if status == "updated":
                to_update.append(note)
            elif status == "not_found" and len(not_found_words) < 30:
                not_found_words.append(note[cfg["input_field"]])

        if to_update:
            col.update_notes(to_update)

        stats["not_found_words"] = not_found_words
        return _PopulateResult(col.merge_undo_entries(undo_pos), stats)

    def done(result):
        s = result.stats
        msg = (
            "Finished!\n\n"
            f"Notes updated: {s['updated']}\n"
            f"Not found: {s['not_found']}\n"
            f"Already filled: {s['already_filled']}\n"
            f"Missing fields: {s['missing_fields']}\n"
            f"Empty input: {s['empty']}"
        )
        if s["not_found_words"]:
            msg += "\n\nNot found:\n" + "、".join(s["not_found_words"])
            if s["not_found"] > len(s["not_found_words"]):
                msg += "…"
        msg += "\n\n(Edit → Undo to revert.)"
        showInfo(msg, parent=browser)

    CollectionOp(parent=browser, op=op).success(done).run_in_background()


# ============================================================
# CHOOSE DEFINITION
# ============================================================

def choose_from_browser(browser):

    note_ids = _selected_note_ids(browser)

    if len(note_ids) != 1:
        showWarning("Please select exactly one note.", parent=browser)
        return

    from .choose_dialog import choose_definition_for_note
    choose_definition_for_note(browser, mw.col.get_note(note_ids[0]))


def choose_from_reviewer():

    if not mw.reviewer or not mw.reviewer.card:
        return

    from .choose_dialog import choose_definition_for_note
    choose_definition_for_note(mw, mw.reviewer.card.note())


# ============================================================
# BROWSER MENUS
# ============================================================

def build_definitions_menu(browser, parent_menu, register=False):

    menu = parent_menu.addMenu("Japanese Definitions")

    populate = menu.addAction("Populate Definitions")
    populate.triggered.connect(lambda: populate_selected(browser))

    choose = menu.addAction("Choose Definition…")
    choose.triggered.connect(lambda: choose_from_browser(browser))

    menu.addSeparator()

    settings = menu.addAction("Settings…")
    settings.triggered.connect(lambda: open_settings(browser))

    if register:
        _register(populate, "shortcut_browser_populate")
        _register(choose, "shortcut_browser_choose")

    return menu


def on_browser_menus(browser):
    browser.form.menuEdit.addSeparator()
    build_definitions_menu(browser, browser.form.menuEdit, register=True)


def on_browser_context_menu(browser, menu):
    menu.addSeparator()
    build_definitions_menu(browser, menu, register=False)


gui_hooks.browser_menus_did_init.append(on_browser_menus)
gui_hooks.browser_will_show_context_menu.append(on_browser_context_menu)


# ============================================================
# REVIEWER SHORTCUT
# ============================================================

def on_state_shortcuts(state, shortcuts):
    if state != "review":
        return
    key = get_config().get("shortcut_reviewer_choose", "")
    if key:
        shortcuts.append((key, choose_from_reviewer))


gui_hooks.state_shortcuts_will_change.append(on_state_shortcuts)


# ============================================================
# MAIN WINDOW
# ============================================================

settings_action = QAction("Japanese Definitions Settings…", mw)
settings_action.triggered.connect(lambda: open_settings(mw))
mw.form.menuTools.addAction(settings_action)
_register(settings_action, "shortcut_settings")

# Add-on manager "Config" button -> our settings window
mw.addonManager.setConfigAction(__name__, lambda: open_settings(mw))


_preloaded = False


def on_profile_open():
    global _preloaded
    if _preloaded:
        return
    _preloaded = True
    if get_config().get("preload_on_startup", True):
        preload_in_background()


gui_hooks.profile_did_open.append(on_profile_open)
