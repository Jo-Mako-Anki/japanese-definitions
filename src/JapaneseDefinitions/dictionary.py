import gzip
import json
import os
import pickle
import re
import threading
import xml.etree.ElementTree as ET

from .deinflect import deinflect, pos_matches
from .pos_data import DEFAULT_SHORT_LABELS, DESCRIPTION_TO_CODE, POS_DESCRIPTIONS


CACHE_VERSION = 3

ADDON_DIR = os.path.dirname(__file__)
USER_FILES_DIR = os.path.join(ADDON_DIR, "user_files")
XML_PATH = os.path.join(ADDON_DIR, "JMdict_e.xml")
FURIGANA_PATH = os.path.join(ADDON_DIR, "JmdictFurigana.json")
CACHE_PATH = os.path.join(USER_FILES_DIR, "jmdict_cache.pickle")


# Accepted file names (EDRDG distributes "JMdict_e.gz" / "JMdict_e")
_CANDIDATES = {
    XML_PATH: ["JMdict_e.xml", "JMdict_e.xml.gz", "JMdict_e.gz", "JMdict_e"],
    FURIGANA_PATH: ["JmdictFurigana.json", "JmdictFurigana.json.gz"],
}


def _resolve(path):
    """Return the first existing variant of a data file (plain or .gz)."""
    for name in _CANDIDATES.get(path, [os.path.basename(path)]):
        candidate = os.path.join(os.path.dirname(path), name)
        if os.path.isfile(candidate):
            return candidate
    return None


def _is_gzip(path):
    with open(path, "rb") as f:
        return f.read(2) == b"\x1f\x8b"


def _open(path, mode="rb", encoding=None):
    if _is_gzip(path):
        return gzip.open(path, mode if "b" in mode else "rt", encoding=encoding)
    return open(path, mode, encoding=encoding)


# ============================================================
# INPUT CLEANING
# ============================================================

_HTML_TAG_RE = re.compile(r"<[^>]*>")
_FURIGANA_RE = re.compile(r"[\[［][^\]］]*[\]］]")
_SPACES_RE = re.compile(r"[\s\u3000]+")


def clean_word(text, ignore_furigana=True):
    """
    Strip HTML and (optionally) bracketed furigana.
    覚悟[かくご] -> 覚悟 ; 食[た]べる -> 食べる ; 日本[にほん] 語[ご] -> 日本語
    """

    if not text:
        return ""

    text = _HTML_TAG_RE.sub("", text)
    text = text.replace("&nbsp;", " ")

    if ignore_furigana:
        text = _FURIGANA_RE.sub("", text)

    return _SPACES_RE.sub("", text)


def is_kana(text):

    has_kana = False

    for char in text:
        code = ord(char)
        if 0x3040 <= code <= 0x30FF:
            has_kana = True
            continue
        return False

    return has_kana


def has_kanji(text):
    return any(
        0x4E00 <= ord(c) <= 0x9FFF or 0x3400 <= ord(c) <= 0x4DBF or c in "々〆ヶ"
        for c in text
    )


# ============================================================
# PRIORITY
# ============================================================

_PRIORITY_SCORES = {
    "ichi1": 100, "ichi2": 80,
    "news1": 95, "news2": 75,
    "spec1": 90, "spec2": 70,
    "gai1": 60, "gai2": 40,
}


def priority_score(priorities):

    best = 0

    for p in priorities:
        if p in _PRIORITY_SCORES:
            score = _PRIORITY_SCORES[p]
        else:
            m = re.match(r"nf(\d{2})$", p)
            score = max(100 - (int(m.group(1)) - 1) * 2, 1) if m else 0
        best = max(best, score)

    return best


# ============================================================
# DICTIONARY
# ============================================================

class Dictionary:

    def __init__(self):
        self.entries = {}       # ent_seq -> entry
        self.index = {}         # word -> [(ent_seq, "k"/"r", form_index)]
        self.furigana = {}      # "text\treading" -> ((ruby, rt), ...)
        self.loaded = False
        self.error = None
        self._lock = threading.Lock()

    # --------------------------------------------------------
    # LOADING
    # --------------------------------------------------------

    def _source_signature(self):
        sig = [CACHE_VERSION]
        for path in (_resolve(XML_PATH), _resolve(FURIGANA_PATH)):
            if path:
                st = os.stat(path)
                sig.append((st.st_size, int(st.st_mtime)))
            else:
                sig.append(None)
        return sig

    def load(self, progress=None, force_rebuild=False):
        """
        Load the dictionary (from the cache when possible).
        Thread-safe: may be called from a background thread.
        progress(label) is called to report progress.
        """

        with self._lock:

            if self.loaded and not force_rebuild:
                return True

            self.error = None
            signature = self._source_signature()

            if not force_rebuild and self._load_cache(signature):
                self.loaded = True
                print("JapaneseDefinitions: dictionary loaded from cache.")
                return True

            if not _resolve(XML_PATH):
                self.error = "JMdict_e.xml (or JMdict_e.gz) not found in:\n" + ADDON_DIR
                print("JapaneseDefinitions: " + self.error)
                return False

            self.entries = {}
            self.index = {}
            self.furigana = {}

            self._parse_xml(progress)

            if progress:
                progress("Loading furigana data...")
            self._load_furigana()

            if progress:
                progress("Writing cache...")
            self._save_cache(signature)

            self.loaded = True
            return True

    def _load_cache(self, signature):

        if not os.path.exists(CACHE_PATH):
            return False

        try:
            with open(CACHE_PATH, "rb") as f:
                data = pickle.load(f)
            if data.get("signature") != signature:
                return False
            self.entries = data["entries"]
            self.index = data["index"]
            self.furigana = data["furigana"]
            return True
        except Exception as e:
            print(f"JapaneseDefinitions: could not read cache: {e}")
            return False

    def _save_cache(self, signature):

        try:
            os.makedirs(USER_FILES_DIR, exist_ok=True)
            tmp = CACHE_PATH + ".tmp"
            with open(tmp, "wb") as f:
                pickle.dump(
                    {
                        "signature": signature,
                        "entries": self.entries,
                        "index": self.index,
                        "furigana": self.furigana,
                    },
                    f,
                    protocol=pickle.HIGHEST_PROTOCOL,
                )
            os.replace(tmp, CACHE_PATH)
        except Exception as e:
            print(f"JapaneseDefinitions: could not write cache: {e}")

    def delete_cache(self):
        try:
            if os.path.exists(CACHE_PATH):
                os.remove(CACHE_PATH)
        except Exception as e:
            print(f"JapaneseDefinitions: could not delete cache: {e}")

    # --------------------------------------------------------
    # XML PARSING
    # --------------------------------------------------------

    def _parse_xml(self, progress):

        count = 0

        with _open(_resolve(XML_PATH)) as source:
            self._iterparse(source, progress)

        print(f"JapaneseDefinitions: parsed {len(self.entries):,} JMdict entries.")

    def _iterparse(self, source, progress):

        count = 0

        for _event, elem in ET.iterparse(source, events=("end",)):

            if elem.tag != "entry":
                continue

            entry = self._parse_entry(elem)
            elem.clear()

            if entry is None:
                continue

            ent_seq = entry["id"]
            self.entries[ent_seq] = entry

            for i, k in enumerate(entry["kanji"]):
                self.index.setdefault(k["word"], []).append((ent_seq, "k", i))

            for i, r in enumerate(entry["readings"]):
                self.index.setdefault(r["word"], []).append((ent_seq, "r", i))

            count += 1

            if progress and count % 20000 == 0:
                progress(f"Building dictionary cache... {count:,} entries")

    @staticmethod
    def _texts(parent, tag):
        return [x.text.strip() for x in parent.findall(tag) if x.text]

    def _parse_entry(self, elem):

        seq_text = elem.findtext("ent_seq")

        if not seq_text:
            return None

        kanji = []
        for k_ele in elem.findall("k_ele"):
            word = (k_ele.findtext("keb") or "").strip()
            if word:
                kanji.append({
                    "word": word,
                    "pri": priority_score(self._texts(k_ele, "ke_pri")),
                    "infos": self._texts(k_ele, "ke_inf"),
                })

        readings = []
        for r_ele in elem.findall("r_ele"):
            word = (r_ele.findtext("reb") or "").strip()
            if word:
                readings.append({
                    "word": word,
                    "pri": priority_score(self._texts(r_ele, "re_pri")),
                    "infos": self._texts(r_ele, "re_inf"),
                    "restr": self._texts(r_ele, "re_restr"),
                    "nokanji": r_ele.find("re_nokanji") is not None,
                })

        if not kanji and not readings:
            return None

        senses = []
        last_pos = []

        for sense in elem.findall("sense"):

            glosses = self._texts(sense, "gloss")
            pos_desc = self._texts(sense, "pos")
            misc = self._texts(sense, "misc")

            # In JMdict, a sense without <pos> inherits the previous one
            if pos_desc:
                last_pos = [DESCRIPTION_TO_CODE.get(d, d) for d in pos_desc]

            if glosses:
                senses.append({
                    "definition": "; ".join(glosses),
                    "pos": list(last_pos),
                    "uk": "word usually written using kana alone" in misc,
                })

        if not senses:
            return None

        return {
            "id": int(seq_text),
            "kanji": kanji,
            "readings": readings,
            "senses": senses,
        }

    def _load_furigana(self):

        path = _resolve(FURIGANA_PATH)

        if not path:
            print("JapaneseDefinitions: JmdictFurigana.json not found, "
                  "per-kanji furigana disabled.")
            return

        try:
            with _open(path, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
        except Exception as e:
            print(f"JapaneseDefinitions: could not read furigana: {e}")
            return

        for item in data:
            text = item.get("text")
            reading = item.get("reading")
            if not text or not reading or not has_kanji(text):
                continue
            self.furigana[text + "\t" + reading] = tuple(
                (seg.get("ruby", ""), seg.get("rt", ""))
                for seg in item.get("furigana", [])
            )

    # --------------------------------------------------------
    # CANDIDATES
    # --------------------------------------------------------

    def _score(self, word, entry, form_type, form):

        score = 0

        if is_kana(word):
            if form_type == "r":
                score += 100
            score += form["pri"]
            if "word usually written using kana alone" in form["infos"] or any(
                s["uk"] for s in entry["senses"][:2]
            ):
                score += 50
            if form["pri"]:
                score += 10
        else:
            if form_type == "k":
                score += 150
            score += form["pri"]

        all_pri = [x["pri"] for x in entry["kanji"]] + [x["pri"] for x in entry["readings"]]
        score += max(all_pri or [0]) * 0.25

        return score

    def _raw_candidates(self, word, types=None):

        out = []
        seen = set()

        for ent_seq, form_type, idx in self.index.get(word, []):

            if ent_seq in seen:
                continue

            entry = self.entries[ent_seq]

            if types is not None:
                codes = {c for s in entry["senses"] for c in s["pos"]}
                if not pos_matches(types, codes):
                    continue

            seen.add(ent_seq)
            form = entry["kanji" if form_type == "k" else "readings"][idx]

            out.append({
                "entry": entry,
                "form_type": form_type,
                "form": form,
                "matched": word,
                "score": self._score(word, entry, form_type, form),
                "reasons": [],
            })

        out.sort(key=lambda c: c["score"], reverse=True)
        return out

    def find(self, word, use_deinflection=True):
        """
        All possible entries: exact matches first,
        then deinflected forms (simplest first).
        """

        self.load()

        if not word:
            return []

        results = self._raw_candidates(word)
        seen = {c["entry"]["id"] for c in results}

        if not use_deinflection:
            return results

        deinflected = []

        for term, types, reasons in deinflect(word)[1:]:
            for c in self._raw_candidates(term, types):
                if c["entry"]["id"] in seen:
                    continue
                seen.add(c["entry"]["id"])
                c["reasons"] = reasons
                c["score"] -= 20 * len(reasons)
                deinflected.append(c)

        deinflected.sort(key=lambda c: c["score"], reverse=True)

        return results + deinflected

    def get_entry(self, ent_seq):
        self.load()
        return self.entries.get(ent_seq)

    # --------------------------------------------------------
    # READING / FURIGANA
    # --------------------------------------------------------

    def best_written_form(self, entry, matched=None, form_type=None):
        """Written form to use for the reading."""

        if matched and form_type == "k":
            return matched

        if matched and form_type == "r":
            return matched

        if entry["kanji"]:
            return max(entry["kanji"], key=lambda k: k["pri"])["word"]

        return entry["readings"][0]["word"]

    def reading_for(self, entry, written):

        if is_kana(written) or not entry["kanji"]:
            return written

        for r in entry["readings"]:
            if r["nokanji"]:
                continue
            if r["restr"] and written not in r["restr"]:
                continue
            return r["word"]

        return entry["readings"][0]["word"]

    def format_reading(self, entry, written, fmt="anki", granularity="kanji"):
        """
        fmt : "kana" (かくご), "anki" (覚[かく]悟[ご]), "ruby" (<ruby>)
        granularity : "kanji" (par kanji) ou "word" (mot entier)
        """

        reading = self.reading_for(entry, written)

        if fmt == "kana" or written == reading or not has_kanji(written):
            return reading

        segments = self.furigana.get(written + "\t" + reading)

        if not segments:
            segments = ((written, reading),)

        if granularity == "word":
            merged = []
            for ruby, rt in segments:
                if rt and merged and merged[-1][1]:
                    merged[-1] = (merged[-1][0] + ruby, merged[-1][1] + rt)
                else:
                    merged.append((ruby, rt))
            segments = merged

        if fmt == "ruby":
            return "".join(
                f"<ruby>{ruby}<rt>{rt}</rt></ruby>" if rt else ruby
                for ruby, rt in segments
            )

        # Anki format: a space before a furigana group
        # when it follows text without furigana.
        out = ""
        prev_had_rt = True
        for ruby, rt in segments:
            if rt:
                if out and not prev_had_rt:
                    out += " "
                out += f"{ruby}[{rt}]"
                prev_had_rt = True
            else:
                out += ruby
                prev_had_rt = False

        return out

    # --------------------------------------------------------
    # POS
    # --------------------------------------------------------

    @staticmethod
    def pos_label(code, style="custom", custom_labels=None):

        if style == "code":
            return code

        if style == "full":
            return POS_DESCRIPTIONS.get(code, code)

        labels = dict(DEFAULT_SHORT_LABELS)
        if custom_labels:
            labels.update(custom_labels)

        return labels.get(code, POS_DESCRIPTIONS.get(code, code))

    def pos_labels_for(self, codes, cfg):

        out = []

        for code in codes:
            label = self.pos_label(
                code, cfg.get("pos_label_style", "custom"), cfg.get("pos_labels")
            )
            if label and label not in out:
                out.append(label)

        return out

    def format_pos(self, senses, cfg):

        codes = []
        for s in senses:
            for c in s["pos"]:
                if c not in codes:
                    codes.append(c)

        return cfg.get("pos_separator", ", ").join(self.pos_labels_for(codes, cfg))

    # --------------------------------------------------------
    # DEFINITIONS
    # --------------------------------------------------------

    @staticmethod
    def format_text(text, capitalization="none", replace_semicolons=False):

        parts = text.split("; ")

        if capitalization == "first":
            parts = [
                (p[0].upper() if i == 0 else p[0].lower()) + p[1:] if p else p
                for i, p in enumerate(parts)
            ]
        elif capitalization == "all":
            parts = [p[0].upper() + p[1:] if p else p for p in parts]

        return (", " if replace_semicolons else "; ").join(parts)

    @staticmethod
    def select_senses(entry, number="all", indices=None):

        senses = entry["senses"]

        if indices:
            return [senses[i] for i in indices if 0 <= i < len(senses)]

        if number == "all":
            return list(senses)

        try:
            n = max(1, int(number))
        except (TypeError, ValueError):
            n = 1

        return senses[:n]

    def format_definition(self, senses, cfg):

        lines = []
        prev_pos = None
        inline = cfg.get("pos_placement") == "inline"
        template = cfg.get("pos_inline_template", "<i>({pos})</i> {definition}")

        for s in senses:

            text = self.format_text(
                s["definition"],
                cfg.get("capitalization", "none"),
                cfg.get("replace_semicolons", False),
            )

            if inline:
                pos_text = cfg.get("pos_separator", ", ").join(
                    self.pos_labels_for(s["pos"], cfg)
                )
                show = pos_text and (
                    cfg.get("pos_inline_every_sense", False) or s["pos"] != prev_pos
                )
                if show:
                    try:
                        text = template.format(pos=pos_text, definition=text)
                    except (KeyError, IndexError, ValueError):
                        text = f"({pos_text}) {text}"
                prev_pos = s["pos"]

            lines.append(text)

        if not lines:
            return ""

        if len(lines) == 1:
            return lines[0]

        fmt = cfg.get("definition_format", "plain")

        if fmt == "bulleted":
            return "<ul>" + "".join(f"<li>{x}</li>" for x in lines) + "</ul>"

        if fmt == "numbered":
            return "<ol>" + "".join(f"<li>{x}</li>" for x in lines) + "</ol>"

        return "<br>".join(lines)

    # --------------------------------------------------------
    # RESOLVE (remplissage automatique)
    # --------------------------------------------------------

    def resolve(self, word, cfg, overrides=None):
        """
        Return (candidate, sense_indices or None) or (None, None).
        """

        self.load()

        if overrides and word in overrides:
            ov = overrides[word]
            entry = self.entries.get(ov.get("ent_seq"))
            if entry:
                written = ov.get("written") or self.best_written_form(entry)
                cand = {
                    "entry": entry,
                    "form_type": "r" if is_kana(written) else "k",
                    "matched": written,
                    "reasons": [],
                    "score": 0,
                }
                return cand, ov.get("senses")

        candidates = self.find(word, cfg.get("deinflect", True))

        if not candidates:
            return None, None

        return candidates[0], None
