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

    # dimensions = (10, 10, 10)
    cells = placer.pregenerate_cells(blif, cell_library)
    placements, dimensions = placer.initial_placement(blif, cells)

    dimensions = (2, 50, 50)

    score = placer.score(blif, cells, placements, dimensions)

    print("Initial Placement Penalty:", score)

    T_0 = 250
    new_placements = placer.simulated_annealing_placement(blif, cells, placements, dimensions, T_0)

    print(new_placements)

    grid = placer.create_layout(dimensions, new_placements, cells)
    shrunk_layout = placer.grid_to_layout(grid)
    png.layout_to_png(shrunk_layout)
