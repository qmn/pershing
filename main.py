#!/usr/bin/env python2.7

from __future__ import print_function

import numpy as np

from util import blif, cell, cell_library
from placer import placer
from vis import png

if __name__ == "__main__":
    with open("lib/quan.yaml") as f:
        cell_library = cell_library.load(f)

    with open("counter.blif") as f:
        blif = blif.load(f)

    dimensions = (10, 10, 10)
    cells = placer.pregenerate_cells(blif, cell_library)
    placements, dimensions = placer.initial_placement(blif, cells)

    score = placer.score(blif, cells, placements, dimensions)

    print("Initial Placement Penalty:", score)

    new_placements = placer.generate(placements)
    score2 = placer.score(blif, cells, new_placements, dimensions)

    print("First iteration penalty:", score2)

    layout = placer.create_layout(dimensions, placements, cells)
    shrunk_layout = placer.shrink_layout(layout)
    png.layout_to_png(shrunk_layout)
