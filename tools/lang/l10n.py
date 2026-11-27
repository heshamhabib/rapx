#!/usr/bin/env python3
"""Translation workflow for the interface languages (FluentLanguages in mods/rapx/mod.yaml).

  python3 tools/lang/l10n.py texts               regenerate mods/rapx/fluent/px-text.ftl from PxText.T/F calls in C#
  python3 tools/lang/l10n.py export <lang>       write tools/lang/work/<lang>/todo.txt: every English text still untranslated
  python3 tools/lang/l10n.py merge <lang>        build mods/rapx/fluent/lang/<lang>/game.ftl from work/<lang>/done-*.txt
  python3 tools/lang/l10n.py status              coverage per language

todo.txt has one unique English text per line as "<id>\t<text>"; multi-line texts and select expressions are joined
with a literal \\n. Translations go in work/<lang>/done-*.txt in the same "<id>\t<text>" form (any number of files,
any order). merge maps each id back to every message/attribute that uses that text, keeps English for anything
missing, and refuses translations whose { placeables } differ from the English ones.
Hand-written files in fluent/lang/<lang>/ (chrome.ftl) win: their messages are never exported or generated.
"""
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MOD = os.path.join(ROOT, "mods/rapx")
WORK = os.path.join(ROOT, "tools/lang/work")
GENERATED = "game.ftl"
KEY = re.compile(r"^(-?[a-zA-Z][\w-]*) =(.*)$")
ATTR = re.compile(r"^\s+\.([\w-]+) =(.*)$")
PLACEABLE = re.compile(r"\{\s*([$-]?[\w-]+)")


def resolve(path):
    package, rel = path.split("|", 1)
    return os.path.join(ROOT, "engine/mods/common" if package == "common" else "mods/rapx", rel)


def manifest_files():
    text = open(os.path.join(MOD, "mod.yaml"), encoding="utf-8").read()
    block = text.split("\nFluentMessages:\n", 1)[1].split("\n\n", 1)[0]
    return [resolve(line.strip()) for line in block.splitlines() if line.strip()]


def parse(path):
    """Messages as {key: {None: value, attr: value}} keeping multi-line text joined with \\n."""
    messages = {}
    key = attr = None
    for raw in open(path, encoding="utf-8"):
        line = raw.rstrip("\n")
        if not line.strip() or line.startswith("#"):
            if not line.strip():
                continue
            key = attr = None
            continue

        m = KEY.match(line)
        if m:
            key, attr = m.group(1), None
            messages[key] = {}
            if m.group(2).strip():
                messages[key][None] = m.group(2).strip()
            continue

        if key is None:
            continue

        m = ATTR.match(line)
        if m:
            attr = m.group(1)
            messages[key][attr] = m.group(2).strip()
            continue

        # Continuation of the current value or attribute
        current = messages[key].get(attr, "")
        messages[key][attr] = (current + "\\n" if current else "") + line.strip()
    return messages


def english():
    merged = {}
    for f in manifest_files():
        merged.update(parse(f))
    return merged


def handwritten(lang):
    keys = set()
    for f in glob.glob(os.path.join(MOD, "fluent/lang", lang, "*.ftl")):
        if os.path.basename(f) != GENERATED:
            keys |= set(parse(f))
    return keys


def translatable(text):
    stripped = PLACEABLE.sub("", text)
    return re.search(r"[A-Za-z]{2,}", stripped) is not None


def units(lang):
    """Unique English texts still to translate -> list of (key, attr)."""
    skip = handwritten(lang)
    texts = {}
    for key, parts in english().items():
        if key in skip:
            continue
        for attr, text in parts.items():
            if translatable(text):
                texts.setdefault(text, []).append((key, attr))
    return texts


def load_done(lang):
    done = {}
    for f in sorted(glob.glob(os.path.join(WORK, lang, "done-*.txt"))):
        for n, line in enumerate(open(f, encoding="utf-8"), 1):
            line = line.rstrip("\n")
            if not line.strip():
                continue
            if "\t" not in line:
                sys.exit(f"{f}:{n}: missing tab")
            i, text = line.split("\t", 1)
            done[int(i)] = text.strip()
    return done


def todo_list(lang):
    return sorted(units(lang).items(), key=lambda kv: (kv[1][0][0], str(kv[1][0][1])))


def export(lang):
    os.makedirs(os.path.join(WORK, lang), exist_ok=True)
    items = todo_list(lang)
    with open(os.path.join(WORK, lang, "todo.txt"), "w", encoding="utf-8") as f:
        for i, (text, _) in enumerate(items):
            f.write(f"{i}\t{text}\n")
    print(f"{lang}: {len(items)} texts, {sum(len(t.split()) for t, _ in items)} words")


def placeables(text):
    return sorted(PLACEABLE.findall(text))


def render(value):
    """Turns a \\n-joined text back into Fluent lines (continuation lines indented)."""
    lines = value.split("\\n")
    if len(lines) == 1:
        return " " + lines[0]
    return "\n" + "\n".join("    " + l for l in lines)


def merge(lang):
    items = todo_list(lang)
    # Ids are only stable against the todo.txt they were made from
    todo = {}
    for line in open(os.path.join(WORK, lang, "todo.txt"), encoding="utf-8"):
        i, text = line.rstrip("\n").split("\t", 1)
        todo[int(i)] = text

    done = load_done(lang)
    targets = dict(items)
    translated = {}
    bad = 0
    for i, text in done.items():
        source = todo.get(i)
        if source is None or source not in targets:
            continue
        if placeables(source) != placeables(text):
            print(f"{lang} #{i}: placeables differ\n  en: {source}\n  {lang}: {text}")
            bad += 1
            continue
        for key, attr in targets[source]:
            translated[(key, attr)] = text

    eng = english()
    keys = sorted({k for k, _ in translated})
    out = [f"## GENERATED by tools/lang/l10n.py merge {lang} from tools/lang/work/{lang}/done-*.txt - edit those, not this file.\n"]
    for key in keys:
        parts = eng[key]
        line = key + " ="
        if None in parts:
            line += render(translated.get((key, None), parts[None]))
        out.append(line)
        for attr, text in parts.items():
            if attr is not None:
                out.append(f"    .{attr} =" + render(translated.get((key, attr), text)).replace("\n    ", "\n        "))
        out.append("")

    os.makedirs(os.path.join(MOD, "fluent/lang", lang), exist_ok=True)
    with open(os.path.join(MOD, "fluent/lang", lang, GENERATED), "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print(f"{lang}: {len(translated)} of {sum(len(v) for v in targets.values())} entries translated, {bad} rejected")


def status():
    eng = english()
    total = sum(1 for parts in eng.values() for t in parts.values() if translatable(t))
    for d in sorted(glob.glob(os.path.join(MOD, "fluent/lang/*"))):
        lang = os.path.basename(d)
        left = sum(len(v) for v in units(lang).values())
        gen = os.path.join(d, GENERATED)
        if os.path.exists(gen):
            done = parse(gen)
            left -= sum(1 for k, parts in done.items() for a, t in parts.items() if t != eng.get(k, {}).get(a))
        print(f"{lang}: {100 * (total - left) / total:.0f}% ({total - left}/{total})")


# --- C# texts ----------------------------------------------------------------------------------------------------

YAML_TEXTS = [("rules/titans.yaml", "Subtitles"), ("rules/titans.yaml", "Specials")]
CALL = re.compile(r'PxText\.[TFN]\(\s*"((?:[^"\\]|\\.)*)"')


def slug(text):
    """Must match PxText.Key in OpenRA.Mods.RAPX/PxText.cs."""
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:48].strip("-")
    h = 0
    for ch in text.encode("utf-8"):
        h = (h * 31 + ch) & 0xFFFFFFFF
    return f"px-text-{s}-{h % 46656:x}" if s else f"px-text-{h % 46656:x}"


def to_fluent(text):
    # string.Format slots {0} become Fluent variables $p0; other braces are escaped
    text = re.sub(r"\{(\d+)\}", lambda m: "\x02" + m.group(1) + "\x03", text)
    text = text.replace("{", "\x00").replace("}", "\x01")
    text = text.replace("\x00", '{"{"}').replace("\x01", '{"}"}')
    text = re.sub("\x02(\\d+)\x03", r"{ $p\1 }", text)
    if text.startswith((" ", "[", "*", ".")):
        text = '{""}' + text
    return text.replace("\n", "\\n")


def texts():
    found = {}
    for f in sorted(glob.glob(os.path.join(ROOT, "OpenRA.Mods.RAPX/**/*.cs"), recursive=True)):
        if "/obj/" in f:
            continue
        for m in CALL.finditer(open(f, encoding="utf-8").read()):
            raw = re.sub(r"\\(.)", lambda e: "\n" if e.group(1) == "n" else e.group(1), m.group(1))
            found[slug(raw)] = to_fluent(raw)

    # English shown straight from rules data (translated with PxText.T where it is drawn)
    for rel, section in YAML_TEXTS:
        inside = False
        for line in open(os.path.join(MOD, rel), encoding="utf-8"):
            stripped = line.strip()
            if stripped == section + ":":
                inside, depth = True, len(line) - len(line.lstrip("\t"))
                continue
            if inside:
                if not stripped or len(line) - len(line.lstrip("\t")) <= depth:
                    inside = False
                    continue
                value = stripped.split(":", 1)[1].strip()
                if value:
                    found[slug(value)] = to_fluent(value)

    path = os.path.join(MOD, "fluent/px-text.ftl")
    with open(path, "w", encoding="utf-8") as f:
        f.write("## GENERATED by tools/lang/l10n.py texts from the PxText.T/F calls in OpenRA.Mods.RAPX - edit the C#, not this file.\n\n")
        for key in sorted(found):
            f.write(f"{key} =" + render(found[key]) + "\n")
    print(f"{len(found)} texts -> {os.path.relpath(path, ROOT)}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "export":
        export(sys.argv[2])
    elif cmd == "merge":
        merge(sys.argv[2])
    elif cmd == "texts":
        texts()
    else:
        status()
