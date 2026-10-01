"""
Simple Japanese deinflection (inspired by Yomichan's rules).

deinflect("食べさせられた") ->
    [("食べさせられた", None, []),
     ("食べさせられる", {"v1"}, ["past"]),
     ("食べさせる", {"v1"}, ["passive/potential", "past"]),
     ("食べる", {"v1"}, ["causative", "passive/potential", "past"]), ...]

Each result = (form, expected types or None, reasons).
The dictionary then checks that the matching entry has
a part of speech compatible with the expected types.
"""

# Rule type -> JMdict POS codes
TYPE_TO_POS = {
    "v1": ("v1", "v1-s"),
    "v5": ("v5",),
    "vk": ("vk",),
    "vs": ("vs", "vs-i", "vs-s"),
    "adj-i": ("adj-i", "adj-ix"),
}


def pos_matches(types, pos_codes):
    """True if one of the entry's POS codes matches one of the types."""

    if types is None:
        return True

    for t in types:
        if t not in TYPE_TO_POS:
            continue
        allowed = TYPE_TO_POS[t]
        for code in pos_codes:
            if t == "v5":
                if code.startswith("v5"):
                    return True
            elif code in allowed:
                return True

    return False


# (kana_in, kana_out, rules_in, rules_out, reason)
RULES = []


def _r(kana_in, kana_out, rules_in, rules_out, reason):
    RULES.append((kana_in, kana_out, frozenset(rules_in), frozenset(rules_out), reason))


# ------------------------------------------------------------
# Godan
# ------------------------------------------------------------
# fin: (a, i, e, o, te, ta)
GODAN = {
    "う": ("わ", "い", "え", "お", "って", "った"),
    "く": ("か", "き", "け", "こ", "いて", "いた"),
    "ぐ": ("が", "ぎ", "げ", "ご", "いで", "いだ"),
    "す": ("さ", "し", "せ", "そ", "して", "した"),
    "つ": ("た", "ち", "て", "と", "って", "った"),
    "ぬ": ("な", "に", "ね", "の", "んで", "んだ"),
    "ぶ": ("ば", "び", "べ", "ぼ", "んで", "んだ"),
    "む": ("ま", "み", "め", "も", "んで", "んだ"),
    "る": ("ら", "り", "れ", "ろ", "って", "った"),
}

# 行く : 行って / 行った
for base in ("行く", "いく", "逝く", "往く"):
    stem = base[:-1]
    _r(stem + "って", base, ["te"], ["v5"], "te-form")
    _r(stem + "った", base, [], ["v5"], "past")
    _r(stem + "ったら", base, [], ["v5"], "conditional (tara)")
    _r(stem + "ったり", base, [], ["v5"], "tari")

for u, (a, i, e, o, te, ta) in GODAN.items():
    _r(a + "ない", u, ["adj-i"], ["v5"], "negative")
    _r(a + "ず", u, [], ["v5"], "negative (zu)")
    _r(a + "ぬ", u, [], ["v5"], "negative (nu)")
    _r(i + "ます", u, [], ["v5"], "polite")
    _r(i + "ました", u, [], ["v5"], "polite past")
    _r(i + "ません", u, [], ["v5"], "polite negative")
    _r(i + "ませんでした", u, [], ["v5"], "polite past negative")
    _r(i + "ましょう", u, [], ["v5"], "polite volitional")
    _r(i + "たい", u, ["adj-i"], ["v5"], "want")
    _r(i + "ながら", u, [], ["v5"], "while")
    _r(i + "なさい", u, [], ["v5"], "polite imperative")
    _r(i, u, [], ["v5"], "masu stem")
    _r(te, u, ["te"], ["v5"], "te-form")
    _r(ta, u, [], ["v5"], "past")
    _r(ta + "ら", u, [], ["v5"], "conditional (tara)")
    _r(ta + "り", u, [], ["v5"], "tari")
    _r(e + "る", u, ["v1"], ["v5"], "potential")
    _r(e + "ば", u, [], ["v5"], "conditional (ba)")
    _r(e, u, [], ["v5"], "imperative")
    _r(a + "れる", u, ["v1"], ["v5"], "passive")
    _r(a + "せる", u, ["v1"], ["v5"], "causative")
    _r(a + "す", u, ["v5"], ["v5"], "causative (short)")
    _r(a + "される", u, ["v1"], ["v5"], "causative-passive")
    _r(o + "う", u, [], ["v5"], "volitional")

# ------------------------------------------------------------
# Ichidan
# ------------------------------------------------------------
for kin, reason, rin in (
    ("ない", "negative", ["adj-i"]),
    ("ず", "negative (zu)", []),
    ("ます", "polite", []),
    ("ました", "polite past", []),
    ("ません", "polite negative", []),
    ("ませんでした", "polite past negative", []),
    ("ましょう", "polite volitional", []),
    ("たい", "want", ["adj-i"]),
    ("ながら", "while", []),
    ("なさい", "polite imperative", []),
    ("て", "te-form", ["te"]),
    ("た", "past", []),
    ("たら", "conditional (tara)", []),
    ("たり", "tari", []),
    ("られる", "passive/potential", ["v1"]),
    ("れる", "potential (colloquial)", ["v1"]),
    ("させる", "causative", ["v1"]),
    ("さす", "causative (short)", ["v5"]),
    ("させられる", "causative-passive", ["v1"]),
    ("よう", "volitional", []),
    ("れば", "conditional (ba)", []),
    ("ろ", "imperative", []),
    ("よ", "imperative", []),
):
    _r(kin, "る", rin, ["v1"], reason)

# ------------------------------------------------------------
# Adjectifs en い
# ------------------------------------------------------------
for kin, reason, rin in (
    ("く", "adverbial", []),
    ("くて", "te-form", ["te"]),
    ("かった", "past", []),
    ("くない", "negative", ["adj-i"]),
    ("ければ", "conditional (ba)", []),
    ("かったら", "conditional (tara)", []),
    ("かろう", "volitional", []),
    ("さ", "noun (sa)", []),
    ("そう", "seems", []),
    ("すぎる", "too much", ["v1"]),
):
    _r(kin, "い", rin, ["adj-i"], reason)

# いい -> よい
for kin in ("よかった", "よくない", "よくて", "よければ", "よく"):
    _r(kin, "いい", [], ["adj-i"], "ii")

# ------------------------------------------------------------
# する
# ------------------------------------------------------------
for kin, reason, rin in (
    ("しない", "negative", ["adj-i"]),
    ("します", "polite", []),
    ("しました", "polite past", []),
    ("しません", "polite negative", []),
    ("しませんでした", "polite past negative", []),
    ("しましょう", "polite volitional", []),
    ("したい", "want", ["adj-i"]),
    ("して", "te-form", ["te"]),
    ("した", "past", []),
    ("したら", "conditional (tara)", []),
    ("したり", "tari", []),
    ("される", "passive", ["v1"]),
    ("させる", "causative", ["v1"]),
    ("させられる", "causative-passive", ["v1"]),
    ("できる", "potential", ["v1"]),
    ("しよう", "volitional", []),
    ("すれば", "conditional (ba)", []),
    ("しろ", "imperative", []),
    ("せよ", "imperative", []),
    ("せず", "negative (zu)", []),
):
    _r(kin, "する", rin, ["vs"], reason)

# 勉強する -> 勉強 (nom + する)
_r("する", "", ["vs"], ["vs"], "suru")

# ------------------------------------------------------------
# 来る
# ------------------------------------------------------------
for k, base in (("来", "来る"), ("", "くる")):
    pre = k
    forms = (
        ("こない" if not k else k + "ない", "negative", ["adj-i"]),
        (("き" if not k else k) + "ます", "polite", []),
        (("き" if not k else k) + "ました", "polite past", []),
        (("き" if not k else k) + "ません", "polite negative", []),
        (("き" if not k else k) + "たい", "want", ["adj-i"]),
        (("き" if not k else k) + "て", "te-form", ["te"]),
        (("き" if not k else k) + "た", "past", []),
        (("き" if not k else k) + "たら", "conditional (tara)", []),
        (("こ" if not k else k) + "られる", "passive/potential", ["v1"]),
        (("こ" if not k else k) + "れる", "potential (colloquial)", ["v1"]),
        (("こ" if not k else k) + "させる", "causative", ["v1"]),
        (("こ" if not k else k) + "よう", "volitional", []),
        (("く" if not k else k) + "れば", "conditional (ba)", []),
        (("こ" if not k else k) + "い", "imperative", []),
    )
    for kin, reason, rin in forms:
        _r(kin, base, rin, ["vk"], reason)

# ------------------------------------------------------------
# Auxiliaries on the te-form
# ------------------------------------------------------------
for t in ("て", "で"):
    _r(t + "いる", t, ["v1"], ["te"], "te-iru")
    _r(t + "る", t, ["v1"], ["te"], "te-iru (colloquial)")
    _r(t + "しまう", t, ["v5"], ["te"], "te-shimau")
    _r(t + "おく", t, ["v5"], ["te"], "te-oku")
    _r(t + "ある", t, ["v5"], ["te"], "te-aru")
    _r(t + "くる", t, ["vk"], ["te"], "te-kuru")
    _r(t + "いく", t, ["v5"], ["te"], "te-iku")
    _r(t + "ください", t, [], ["te"], "te-kudasai")
    _r(t + "も", t, [], ["te"], "te-mo")
_r("ちゃう", "て", ["v5"], ["te"], "chau")
_r("じゃう", "で", ["v5"], ["te"], "jau")
_r("とく", "て", ["v5"], ["te"], "toku")
_r("どく", "で", ["v5"], ["te"], "doku")


def deinflect(word, max_results=200):
    """
    Return candidate forms, the raw form first.
    """

    results = [(word, None, [])]
    seen = {(word, None)}
    i = 0

    while i < len(results) and len(results) < max_results:

        term, types, reasons = results[i]
        i += 1

        for kin, kout, rin, rout, reason in RULES:

            if not term.endswith(kin):
                continue

            if types is not None and not (types & rin):
                continue

            new_term = term[: len(term) - len(kin)] + kout

            if not new_term:
                continue

            key = (new_term, rout)

            if key in seen:
                continue

            seen.add(key)
            results.append((new_term, rout, [reason] + reasons))

    return results
