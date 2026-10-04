# SPDX-License-Identifier: LGPL-2.1-or-later
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ICONS = os.path.join(ROOT, "resources", "icons")
DIAGRAMS = os.path.join(ROOT, "resources", "diagrams")


def icon(name):
    return os.path.join(ICONS, name)


def diagram(name):
    return os.path.join(DIAGRAMS, name)
