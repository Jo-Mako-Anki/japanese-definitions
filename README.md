# Japanese Definitions — Anki add-on

Fill your Japanese cards with **English definitions from JMdict**, the word's **furigana** and its **part of speech** — fully offline and fully configurable.

![Choose Definition](screenshots/choose-definition.png)

## Features

- **Populate Definitions** — fill hundreds of notes at once from the browser, with a progress bar. Undo with *Edit → Undo*.
- **Choose Definition** — pick the right entry when a word has several meanings (はし: bridge, chopsticks, edge…), choose which senses to keep, with a live preview. Works in the browser and during review.
- **Remembered choices** — once you've picked an entry for a word, batch filling reuses it.
- **Conjugated words** — 食べさせられた, 書いていた, 勉強しました… are looked up as 食べる, 書く, 勉強.
- **Furigana** — `覚[かく]悟[ご]`, `覚悟[かくご]`, plain kana or HTML `<ruby>`.
- **Part of speech** — in its own field or inline, with editable labels.
- **Ignores furigana in your input** — `覚悟[かくご]` is looked up as 覚悟.
- **Fast** — the dictionary is cached and loaded in the background.

## Installation

- **AnkiWeb (recommended):** Tools → Add-ons → Get Add-ons… and enter the code from the [AnkiWeb page](ANKIWEB_LINK).
- **Manual:** download the `.ankiaddon` file from [Releases](https://github.com/Jo-Mako-Anki/japanese-definitions/releases), then Tools → Add-ons → Install from file…

Requires Anki 2.1.50 or later.

## Usage

1. **Tools → Japanese Definitions Settings…** — choose your input field (the Japanese word) and the output fields.
2. In the browser, select notes → **Edit → Japanese Definitions → Populate Definitions** (also in the right-click menu).
3. To pick a specific meaning, select one note → **Choose Definition…**, or press the shortcut during review.

| Action | Default shortcut |
|---|---|
| Choose Definition (reviewer) | `Ctrl+Alt+D` |
| Choose Definition (browser) | `Ctrl+Alt+D` |
| Populate Definitions (browser) | `Ctrl+Alt+Shift+D` |

All shortcuts can be changed in the settings.

![Settings](screenshots/settings.png)

## Settings

| Tab | Options |
|---|---|
| Fields | Input field, Definition, Part of speech, Input (Furigana); overwrite existing content |
| Definitions | Number of definitions, format (plain / bulleted / numbered), capitalization, `;` → `,` |
| Part of speech | Separate field or inline, label style, custom labels, separator, HTML template |
| Furigana | Kana / Anki furigana / HTML ruby, per kanji or per word |
| Lookup | Ignore bracketed furigana, deinflection, background loading, remembered choices, cache |
| Shortcuts | Every keyboard shortcut, with conflict detection |

The first use builds a dictionary cache (~20 seconds, once). It is rebuilt automatically when the dictionary files change.

## Building from source

Requires Python 3.9+, standard library only.

```bash
python build.py                 # downloads the dictionaries if needed, then builds
python build.py --update-data   # forces the latest JMdict and JmdictFurigana
```

The add-on is written to `dist/JapaneseDefinitions-<version>.ankiaddon`. The version comes from `src/JapaneseDefinitions/manifest.json`.

For development, you can link `src/JapaneseDefinitions` into Anki's `addons21` folder and copy `JMdict_e.gz` and `JmdictFurigana.json.gz` from `data/` next to it.

## Bug reports

Please open an [issue](https://github.com/Jo-Mako-Anki/japanese-definitions/issues) with your Anki version, the word you looked up, and what you expected.

## Credits & licence

- Dictionary: [JMdict](https://www.edrdg.org/jmdict/j_jmdict.html), property of the [Electronic Dictionary Research and Development Group](https://www.edrdg.org/), used in conformance with the Group's [licence](https://www.edrdg.org/edrdg/licence.html) (CC BY-SA 4.0).
- Furigana: [JmdictFurigana](https://github.com/Doublevil/JmdictFurigana) by Doublevil (CC BY-SA).
- Deinflection rules inspired by [Yomitan](https://github.com/yomidevs/yomitan).
- Add-on code: [MIT](LICENSE).
