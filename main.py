#!/usr/bin/env python2.7

from __future__ import print_function

import json
import sys
import numpy as np

from util import blif, cell, cell_library
from placer import placer
from router import router
from vis import png

if __name__ == "__main__":
    placements = None
    dimensions = None

    # Load placements, if provided
    if len(sys.argv) >= 2:
        placements_file = sys.argv[1]
        print("Using placements file:", placements_file)
        with open(placements_file) as f:
            placements = json.loads(f.readline())
            dimensions = json.loads(f.readline())

    with open("lib/quan.yaml") as f:
        cell_library = cell_library.load(f)

    with open("counter.blif") as f:
        blif = blif.load(f)

    cells = placer.pregenerate_cells(blif, cell_library)

    # PLACE =============================================================
    if placements is None:
        print("""
Performing Initial Placement...
-------------------------------""")

        placements, dimensions = placer.initial_placement(blif, cells)

        dimensions = (2, 50, 50)

        score = placer.score(blif, cells, placements, dimensions)

        print("Initial Placement Penalty:", score)

        print("""
Doing Placement...
------------------""")

        T_0 = 250
        iterations = 2000
        new_placements = placer.simulated_annealing_placement(blif, cells, placements, dimensions, T_0, iterations)

        print(new_placements)
        with open("placements.json", "w") as f:
            json.dump(new_placements, f)
            f.write("\n")
            json.dump(dimensions, f)

        placements, dimensions = placer.shrink(placements, cells)
        layout = placer.placement_to_layout(dimensions, placements, cells)
        png.layout_to_png(layout)

        placements = new_placements


    # ROUTE =============================================================
    print("""
Doing Routing...
----------------""")

    placements, dimensions = placer.shrink(placements, cells)
    layout = placer.placement_to_layout(dimensions, placements, cells)
    net_segments = router.create_net_segments(blif, cells, placements)
    png.nets_to_png(layout, net_segments)
