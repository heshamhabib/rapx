#!/usr/bin/env python3
"""
Builds mods/rapx/chrome/mainmenu-prompts.yaml from the engine's common version,
re-skinning the first-run "Establishing Battlefield Control" prompt with the Project X UI.
Re-run after an engine upgrade: python3 artsrc/px-ui/restyle_prompts.py
"""
import os
import re

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
SRC = os.path.join(ROOT, "engine", "mods", "common", "chrome", "mainmenu-prompts.yaml")
DST = os.path.join(ROOT, "mods", "rapx", "chrome", "mainmenu-prompts.yaml")

HEADER = re.compile(r"^(\t*)([A-Za-z]+)@([A-Z0-9_]+):$")
TEXT = "D6CFCC"
ACCENT = "FF6A50"


def restyle(kind, name, props):
    font = props.get("Font")
    if kind == "Background" and name == "MAINMENU_INTRODUCTION_PROMPT":
        props.update(Background="px-dialog", Width="760", Height="590")
    elif kind == "Background" and name.endswith("_SECTION_HEADER"):
        props.update(Background="px-section", Height="13")
    elif kind == "Label" and name == "PROMPT_TITLE":
        props.update(Font="PXTitle", Y="26", Height="34")
    elif kind == "Label" and name in ("DESC_A", "DESC_B"):
        props.update(Font="PXBody", TextColor=TEXT, Y="80" if name == "DESC_A" else "100", Height="20")
    elif kind == "Label" and font == "TinyBold":
        props.update(Font="PXHeader", TextColor="FFFFFF")
    elif kind in ("Label", "LabelWithHighlight"):
        props["Font"] = "PXSmall" if font == "Small" else "PXLabel"
        if font == "Small":
            props["TextColor"] = TEXT
        if kind == "LabelWithHighlight":
            props["HighlightColor"] = ACCENT
    elif kind == "TextField":
        props.update(Background="px-field", Font="PXBody")
    elif kind == "DropDownButton":
        props.update(Background="px-button", Separators="px-dropdown-separators", Font="PXBody")
    elif kind == "Checkbox":
        props.update(Background="px-field", Font="PXBody")
    elif kind == "ScrollPanel":
        props.update(X="30", Y="132", Width="PARENT_WIDTH - 60", Height="PARENT_HEIGHT - 206",
                     Background="", ScrollBarBackground="")
    elif kind == "Button" and name == "CONTINUE_BUTTON":
        props.update(Background="px-button-highlighted", Font="PXButton",
                     X="PARENT_WIDTH - 214", Y="PARENT_HEIGHT - 62", Width="180", Height="34")


def main():
    lines = open(SRC).read().split("\n")
    out, i, in_intro = [], 0, False
    while i < len(lines):
        m = HEADER.match(lines[i])
        if not m:
            out.append(lines[i])
            i += 1
            continue

        indent, kind, name = m.groups()
        if indent == "":
            in_intro = name == "MAINMENU_INTRODUCTION_PROMPT"

        # Gather this widget's own properties (lines one tab deeper, up to Children: or the next widget)
        prop_indent = indent + "\t"
        j, props = i + 1, {}
        while j < len(lines) and lines[j].startswith(prop_indent) and not lines[j].startswith(prop_indent + "\t"):
            key, _, value = lines[j].strip().partition(":")
            if key == "Children":
                break
            props[key] = value.strip()
            j += 1

        if in_intro:
            restyle(kind, name, props)

        out.append(lines[i])
        out.extend(f"{prop_indent}{k}: {v}".rstrip() for k, v in props.items())

        # Glowing underline beneath the title
        if in_intro and name == "PROMPT_TITLE":
            out += [
                f"{indent}Image@TITLE_LINE:",
                f"{prop_indent}X: (PARENT_WIDTH - WIDTH) / 2",
                f"{prop_indent}Y: 64",
                f"{prop_indent}Width: 320",
                f"{prop_indent}Height: 6",
                f"{prop_indent}ImageCollection: px-deco",
                f"{prop_indent}ImageName: title-line",
            ]
        i = j

    open(DST, "w").write("\n".join(out))
    print("wrote", os.path.relpath(DST, ROOT))


if __name__ == "__main__":
    main()
