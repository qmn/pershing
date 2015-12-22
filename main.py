#!/usr/bin/env python2.7

from __future__ import print_function

import numpy as np
from util import blif, cell, cell_library
from placer import placer

if __name__ == "__main__":
    with open("lib/quan.yaml") as f:
        cell_library = cell_library.load(f)

    with open("counter.blif") as f:
        blif = blif.load(f)

    dimensions = (10, 10, 10)
    cells = placer.pregenerate_cells(blif, cell_library)
    placements, dimensions = placer.initial_placement(blif, cells)

    estimated_net_lengths = placer.estimate_wire_lengths(blif, cells, placements)
    wire_length_penalty = sum(estimated_net_lengths.values())

    occupied = placer.compute_occupied_locations(blif, cells, placements, dimensions)
    overlap_penalty = placer.compute_overlap_penalty(occupied)

    print("Initial Placement Penalty:", wire_length_penalty + overlap_penalty)
