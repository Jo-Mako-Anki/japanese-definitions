"""Shared logic (no UI): filling a note."""

from .dictionary import Dictionary, clean_word

dictionary = Dictionary()


def input_word(note, cfg):
    return clean_word(note[cfg["input_field"]], cfg.get("ignore_furigana", True))


def compute_values(cand, sense_indices, cfg):
    """Compute definition, reading and POS for a candidate."""

    entry = cand["entry"]

    senses = dictionary.select_senses(
        entry, cfg.get("number_of_definitions", 1), sense_indices
    )

    written = dictionary.best_written_form(entry, cand.get("matched"), cand.get("form_type"))

    return {
        "definition": dictionary.format_definition(senses, cfg),
        "reading": dictionary.format_reading(
            entry,
            written,
            cfg.get("reading_format", "anki"),
            cfg.get("furigana_granularity", "kanji"),
        ),
        "pos": dictionary.format_pos(senses, cfg),
    }


def target_fields(note, cfg, fill_reading=None, fill_pos=None, overwrite=None):
    """
    Fields to fill: {"definition": field_name, "reading": ..., "pos": ...}
    """

    if fill_reading is None:
        fill_reading = cfg.get("fill_reading", False)
    if fill_pos is None:
        fill_pos = cfg.get("pos_placement") == "field"
    if overwrite is None:
        overwrite = cfg.get("overwrite_existing", False)

    targets = {"definition": cfg["definition_field"]}

    if fill_reading and cfg.get("reading_field") and cfg["reading_field"] in note:
        targets["reading"] = cfg["reading_field"]

    if fill_pos and cfg.get("pos_field") and cfg["pos_field"] in note:
        targets["pos"] = cfg["pos_field"]

    if not overwrite:
        targets = {k: f for k, f in targets.items() if not note[f].strip()}

    return targets


def fill_note(note, cfg, overrides):
    """
    Fill the note (without saving it).
    Returns: "updated", "not_found", "already_filled", "missing_fields", "empty".
    """

    if cfg["input_field"] not in note or cfg["definition_field"] not in note:
        return "missing_fields"

    word = input_word(note, cfg)

    if not word:
        return "empty"

    targets = target_fields(note, cfg)

    if not targets:
        return "already_filled"

    cand, sense_indices = dictionary.resolve(word, cfg, overrides)

    if cand is None:
        return "not_found"

    values = compute_values(cand, sense_indices, cfg)

    for key, field in targets.items():
        note[field] = values[key]

    return "updated"
