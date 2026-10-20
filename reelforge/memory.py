"""Per-project tuning memory.

The rules are where a project starts, not where it stays. When someone says
"slower", "less text", "always end on the pricing page", that goes here and is
applied to every later storyboard. It lives in <repo>/.reelforge/memory.json,
so it travels with the project through git and the whole team benefits from
one person's correction.
"""
import os
import time

from . import config as C


def path(project):
    return os.path.join(project, "memory.json")


def load(project):
    return C.read_json(path(project), {"notes": []})


def add(project, note, who=""):
    m = load(project)
    m["notes"].append({"at": time.strftime("%Y-%m-%d"), "by": who, "text": note.strip()})
    C.write_json(path(project), m)
    return m


def remove(project, index):
    m = load(project)
    if 0 <= index < len(m["notes"]):
        m["notes"].pop(index)
        C.write_json(path(project), m)
    return m


def as_prompt(project):
    notes = load(project)["notes"]
    if not notes:
        return ""
    return ("Team preferences for this project, learned from reviewing earlier videos. "
            "Apply ALL of them:\n" + "\n".join(f"- {n['text']}" for n in notes))
