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
        cell_lib = cell_library.load(f)

    with open("counter.blif") as f:
        blif = blif.load(f)

    pregenerated_cells = cell_library.pregenerate_cells(cell_lib, pad=1)

    placer = placer.Placer(blif, pregenerated_cells)

    # PLACE =============================================================
    if placements is None:
        print("""
Performing Initial Placement...
-------------------------------""")

        placements, dimensions = placer.initial_placement()

        score = placer.score(placements, dimensions)

        print("Initial Placement Penalty:", score)

        print("""
Doing Placement...
------------------""")

        T_0 = 250
        iterations = 2000
        new_placements = placer.simulated_annealing_placement(placements, dimensions, T_0, iterations)

        print(new_placements)
        with open("placements.json", "w") as f:
            json.dump(new_placements, f)
            f.write("\n")
            json.dump(dimensions, f)

        placements, dimensions = placer.shrink(placements)
        layout = placer.placement_to_layout(dimensions, placements)
        png.layout_to_png(layout)

        placements = new_placements


    # ROUTE =============================================================
    print("""
Doing Routing...
----------------""")

    placements, dimensions = placer.shrink(placements)
    layout = placer.placement_to_layout(dimensions, placements)

    router = router.Router(blif, pregenerated_cells)

    net_segments = router.create_net_segments(placements)

    # for net, segments in net_segments.iteritems():
    #     print("{}:".format(net))
    #     for segment in segments:
    #         print("  " + str(list(segment)))
    #     print()

    routing = router.initial_routing(net_segments)
    # print(routing)

    for nets in routing.itervalues():
        for net in nets:
            for y, z, x in net:
                layout[y, z, x] = 55
                layout[y-1, z, x] = 1

    scores = router.score_routing(routing, layout)

    # VISUALIZE =========================================================
    print("""
Doing Visualization...
-------------------""")
    png.nets_to_png(layout, net_segments)
