#!/usr/bin/env python2.7

from __future__ import print_function

import json
import sys
import numpy as np
import os.path
import time
from math import ceil
import argparse

import nbt

from util import blif, cell, cell_library
from placer import placer
from router import router, extractor, minetime
from vis import png
from inserter import inserter

def underline_print(s):
    print()
    print(s)
    print("-" * len(s))

if __name__ == "__main__":
    placements = None
    dimensions = None
    routing = None

    # Create parser
    parser = argparse.ArgumentParser(description="An automatic place-and-route tool for Minecraft Redstone circuits.")
    parser.add_argument('blif', metavar="<input BLIF file>")
    parser.add_argument('-o', '--output_dir', metavar="output_directory", dest="output_dir")
    parser.add_argument('--library', metavar="library_file", dest="library_file", default="lib/quan.yaml")
    parser.add_argument('--placements', metavar="placements_file", dest="placements_file", help="Use this placements file rather than creating one. Must be previously generated from the supplied BLIF.")
    parser.add_argument('--routings', metavar="routings_file", dest="routings_file", help="Use this routings file rather than creating one. Must be previously generated from the supplied BLIF and placements JSON.")
    parser.add_argument('--world', metavar="world_folder", dest="world_folder", help="Place the extracted redstone circuit layout in this world.")

    args = parser.parse_args()

    # Load placements, if provided
    if args.placements_file is not None:
        print("Using placements file:", args.placements_file)
        with open(args.placements_file) as f:
            placements = json.loads(f.readline())
            dimensions = json.loads(f.readline())

    # Load library file
    with open(args.library_file) as f:
        cell_lib = cell_library.load(f)

    # Load BLIF
    with open(args.blif) as f:
        blif = blif.load(f)

    # Result directory
    if args.output_dir is not None:
        if os.path.isabs(args.output_dir):
            result_dir = args.output_dir
        else:
            result_dir = os.path.abspath(args.output_dir)
    else:
        result_base, _ = os.path.splitext(args.blif)
        result_dir = os.path.abspath(result_base + "_result")

    # Try making the directory
    if not os.path.exists(result_dir):
        try:
            os.mkdir(result_dir)
            print("Made result dir: ", result_dir)
        except OSError as e:
            print(e)

    pregenerated_cells = cell_library.pregenerate_cells(cell_lib, pad=1)

    placer = placer.GridPlacer(blif, pregenerated_cells, grid_spacing=5)

    start_time = time.time()
    print("Started", time.strftime("%c", time.localtime(start_time)))

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
        print("Placed", len(placements), "cells")
        with open(os.path.join(result_dir, "placements.json"), "w") as f:
            json.dump(placements, f)
            f.write("\n")
            json.dump(dimensions, f)

        # Visualize this layout
        layout = placer.placement_to_layout(dimensions, placements)
        png.layout_to_png(layout, filename_base=os.path.join(result_dir, "composite"))
        print("Dimensions:", dimensions)


    # ROUTE =============================================================
    underline_print("Doing Routing...")

    placements, dimensions = placer.shrink(placements)
    layout = placer.placement_to_layout(dimensions, placements)

    router = router.Router(blif, pregenerated_cells)

    # Load routings, if provided
    if args.routings_file is not None:
        print("Using routings file:", args.routings_file)
        with open(args.routings_file) as f:
            routing = router.deserialize_routing(f)

    if routing is None:
        print("Doing initial routing...")
        routing = router.initial_routing(placements, layout.shape)
        print("done.")
        routing = router.re_route(routing, layout)

        # Preserve routing
        with open(os.path.join(result_dir, "routing.json"), "w") as f:
            router.serialize_routing(routing, dimensions, f)

        print("Routed", len(routing), "nets")

    # EXTRACT ===========================================================
    underline_print("Doing Extraction...")
    extractor = extractor.Extractor(blif, pregenerated_cells)

    extracted_routing = extractor.extract_routing(routing)
    extracted_layout = extractor.extract_layout(extracted_routing, layout)

    with open(os.path.join(result_dir, "extraction.json"), "w") as f:
        json.dump(extracted_layout.tolist(), f)
        print("Wrote extraction to extraction.json")

    # VISUALIZE =========================================================
    underline_print("Doing Visualization...")

    # Get the pins
    pins = placer.locate_circuit_pins(placements)

    # png.nets_to_png(layout, routing)
    png_fn = os.path.join(result_dir, "layout.png")
    png.layout_to_composite(extracted_layout, pins=pins).save(png_fn)
    print("Image written to ", png_fn)

    # MINETIME =========================================================
    underline_print("Doing Timing Analysis with MineTime...")

    mt = minetime.MineTime()
    path_delays = mt.compute_combinational_delay(placements, extracted_routing, cell_lib)

    print("Path delays:")
    for path_delay, path in sorted(path_delays, key=lambda x: x[0], reverse=True):
        print(path_delay, "  ", " -> ".join(path))
    print()

    crit_delay, crit_path = max(path_delays, key=lambda x: x[0])

    print("Critical path delay: {} ticks".format(crit_delay))
    print("Minimum period: {:.2f} s".format(crit_delay * 0.05))
    print("Maximum frequency: {:.4f} Hz".format(1./(crit_delay * 0.05)))

    underline_print("Design Statistics")
    print("Layout size: {} x {} x {}".format(layout.shape[0], layout.shape[1], layout.shape[2]))
    print("  Blocks placed: {}".format(sum(layout.flat != 0)))
    print()
    print("Total nets: {}".format(len(extracted_routing)))
    print("  Segments routed: {}".format(sum(len(net["segments"]) for net in extracted_routing.itervalues())))
    print()
    end_time = time.time()
    print("Finished", time.strftime("%c", time.localtime(end_time)), "(took", ceil(end_time - start_time), "s)")

    # INSERTION ========================================================
    if args.world_folder is not None:
        underline_print("Inserting Design into Minecraft World...")
        world = nbt.world.WorldFolder(args.world_folder)
        inserter.insert_extracted_layout(world, extracted_layout, offset=(4, 0, 0))
