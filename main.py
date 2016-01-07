#!/usr/bin/env python2.7

from __future__ import print_function

import json
import sys
import numpy as np

from util import blif, cell, cell_library
from placer import placer
from router import router
from vis import png

def underline_print(s):
    print()
    print(s)
    print("-" * len(s))

if __name__ == "__main__":
    placements = None
    dimensions = None
    routing = None

    # Load placements, if provided
    if len(sys.argv) >= 2:
        placements_file = sys.argv[1]
        print("Using placements file:", placements_file)
        with open(placements_file) as f:
            placements = json.loads(f.readline())
            dimensions = json.loads(f.readline())


    with open("lib/quan.yaml") as f:
        cell_lib = cell_library.load(f)

    with open("and.blif") as f:
        blif = blif.load(f)

    pregenerated_cells = cell_library.pregenerate_cells(cell_lib, pad=1)

    placer = placer.GridPlacer(blif, pregenerated_cells, grid_spacing=5)

    # PLACE =============================================================
    if placements is None:
        underline_print("Performing Initial Placement...")

        placements, dimensions = placer.initial_placement()

        score = placer.score(placements, dimensions)

        print("Initial Placement Penalty:", score)

        underline_print("Doing Placement...")

        # Place cells
        T_0 = 250
        iterations = 2000
        new_placements = placer.simulated_annealing_placement(placements, dimensions, T_0, iterations)

        placements, dimensions = placer.shrink(new_placements)

        # Place pins and resize
        placements += placer.place_pins(dimensions)
        placements, dimensions = placer.shrink(placements)

        # print(new_placements)
        print("Placed", len(new_placements), "cells")
        with open("placements.json", "w") as f:
            json.dump(new_placements, f)
            f.write("\n")
            json.dump(dimensions, f)

        layout = placer.placement_to_layout(dimensions, placements)
        png.layout_to_png(layout)
        print("Dimensions:", dimensions)


    # ROUTE =============================================================
    underline_print("Doing Routing...")

    placements, dimensions = placer.shrink(placements)
    layout = placer.placement_to_layout(dimensions, placements)

    router = router.Router(blif, pregenerated_cells)

    # Load routings, if provided
    if len(sys.argv) >= 3:
        routings_file = sys.argv[2]
        print("Using routings file:", routings_file)
        with open(routings_file) as f:
            routing = router.deserialize_routing(f)

    if routing is None:
        routing = router.initial_routing(placements, layout.shape)
        routing = router.re_route(routing, layout)

        # Preserve routing
        with open("routing.json", "w") as f:
            router.serialize_routing(routing, dimensions, f)

        print("Routed", len(routing), "nets")

    routed_layout = router.extract(routing, layout)

    # VISUALIZE =========================================================
    underline_print("Doing Visualization...")

    # Get the pins
    pins = placer.locate_circuit_pins(placements)

    # png.nets_to_png(layout, routing)
    png.layout_to_composite(routed_layout, pins=pins).save("layout.png")
    print("Image written to layout.png")
