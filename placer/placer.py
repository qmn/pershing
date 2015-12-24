from __future__ import print_function

import sys
import random
import numpy as np

from collections import defaultdict
from copy import deepcopy
from math import exp, log, sqrt, ceil

from util.cell import from_lib
from vis import png

def pregenerate_cells(blif, cell_library):
    """
    Generates each cell and each of its four (yaw) rotations.

    The returned dictionary is indexed by the cell name (e.g., "AND")
    and then by the rotation (0-3).
    """
    cells = {}
    for cell_name, cell_data in cell_library.cells.iteritems():
        # Generate first cell
        cell_rot0 = from_lib(cell_name, cell_data)

        # Generate all four rotations
        cell_rot1 = cell_rot0.rot90()
        cell_rot2 = cell_rot1.rot90()
        cell_rot3 = cell_rot2.rot90()

        cells[cell_name] = [cell_rot0, cell_rot1, cell_rot2, cell_rot3]

    return cells

def initial_placement(blif, pregenerated_cells, dimensions=None):
    """
    Generate an initial stupid placement of cells.
    If dimensions is not specified, then make an educated guess based
    on the cells used.

    The returned dictionary is a list of cells and their placements:
    [ { "name": "AND",
        "placement": (y, z, x),
        "turns": 0 | 1 | 2 | 3,
        "pins": {"A": "rst", ... }
      },

      ...
    ]
    """
    spacing = 1

    # Get the subcircuits from the BLIF
    blif_cells = blif.cells

    # Convert them to references to cells in the cell library, using the
    # first rotation
    cells = [pregenerated_cells[bc["name"]][0] for bc in blif_cells]

    # Generate the square root (to place them in a square as best as possible
    num_cells_side = int(ceil(sqrt(len(cells))))

    max_height = max(cell.blocks.shape[0] for cell in cells)

    # Estimate the width by taking the maximum of X or Z of all cells
    # used in the layout
    max_cell_widths = [max(cell.blocks.shape[1], cell.blocks.shape[2]) for cell in cells]

    max_cell_width = max(max_cell_widths)

    # Add up the longest dimension, plus one for each cell
    width_estimate = sum(max_cell_widths) + (len(max_cell_widths) * spacing)

    if dimensions is None:
        dimensions = (max_height, width_estimate, width_estimate)

        print("Estimating dimensions to be {}".format(dimensions))
    else:
        if len(dimensions) != 3:
            raise ValueError("Dimensions ({}) is not a tuple of length 3".format(dimensions))

    # Lay them out on a grid
    anchor = [0, 0, 0]

    placements = []

    for i, (cell, blif_cell) in enumerate(zip(cells, blif_cells)):
        row = i / num_cells_side
        col = i % num_cells_side

        dz = row * (max_cell_width + spacing)
        dx = col * (max_cell_width + spacing)

        cell_anchor = [anchor[0], anchor[1] + dz, anchor[2] + dx]

        placement = {"name": cell.name,
                     "placement": cell_anchor,
                     "turns": 0,
                     "pins": blif_cell["pins"]}

        placements.append(placement)

    return placements, dimensions

def estimate_lengths_and_occupieds(blif, pregenerated_cells, placements, pad_y=1):
    net_pins = defaultdict(list)
    grid = defaultdict(int)

    for blif_cell, placement in zip(blif.cells, placements):
        # Do the cell lookup
        rotation = placement["turns"]
        cell_name = placement["name"]
        cell = pregenerated_cells[cell_name][rotation]

        yy, zz, xx = placement["placement"]

        for y in xrange(pad_y, cell.ports.shape[0]-pad_y):
            for z in xrange(cell.ports.shape[1]):
                for x in xrange(cell.ports.shape[2]):
                    coord = (y + yy, z + zz, x + xx)

                    # Add to the list of occupied locations
                    grid[coord] += 1

                    # Add to the list of pins
                    port_name = cell.ports[y, z, x]
                    if port_name:
                        net_name = placement["pins"][port_name]
                        net_pins[net_name].append(coord)

    net_lengths = {}

    # Figure the point-to-point of these pins' locations
    for net, pins in net_pins.iteritems():
        dy = max(c[0] for c in pins) - min(c[0] for c in pins)
        dz = max(c[1] for c in pins) - min(c[1] for c in pins)
        dx = max(c[2] for c in pins) - min(c[2] for c in pins)

        net_lengths[net] = dy + dz + dx

    # print(net_lengths)

    return net_lengths, grid

def estimate_wire_lengths(blif, pregenerated_cells, placements):
    """
    Given the cells and their placements, determine the estimated wire
    lengths of all nets used by these cells.

    The estimate is the "half-perimeter of the bounding box of the net."
    """

    net_pins = defaultdict(list)

    # For each wire, locate its pins according to the placement
    for blif_cell, placement in zip(blif.cells, placements):
        # Do the cell lookup
        rotation = placement["turns"]
        cell_name = placement["name"]
        cell = pregenerated_cells[cell_name][rotation]

        yy, zz, xx = placement["placement"]

        for y in xrange(cell.ports.shape[0]):
            for z in xrange(cell.ports.shape[1]):
                for x in xrange(cell.ports.shape[2]):
                    port_name = cell.ports[y, z, x]
                    if port_name:
                        net_name = placement["pins"][port_name]
                        coord = (y + yy, z + zz, x + xx)
                        net_pins[net_name].append(coord)

    net_lengths = {}

    # Figure the point-to-point of these pins' locations
    for net, pins in net_pins.iteritems():
        dy = max(c[0] for c in pins) - min(c[0] for c in pins)
        dz = max(c[1] for c in pins) - min(c[1] for c in pins)
        dx = max(c[2] for c in pins) - min(c[2] for c in pins)

        net_lengths[net] = dy + dz + dx

    # print(net_lengths)

    return net_lengths

def compute_occupied_locations(blif, pregenerated_cells, placements, dimensions):

    grid = defaultdict(int)

    for placement in placements:
        # Do the cell lookup
        rotation = placement["turns"]
        cell_name = placement["name"]
        cell = pregenerated_cells[cell_name][rotation]

        yy, zz, xx = placement["placement"]

        for y in xrange(cell.blocks.shape[0]):
            for z in xrange(cell.blocks.shape[1]):
                for x in xrange(cell.blocks.shape[2]):
                    grid[(yy + y, zz + z, xx + x)] += 1

    # print(grid)

    return grid

def compute_bounds_penalty(grid, dimensions):
    penalty = 0
    for coord, v in grid.iteritems():
        y, z, x = coord
        if y < 0 or y >= dimensions[0] or \
           z < 0 or z >= dimensions[1] or \
           x < 0 or x >= dimensions[2]:
            penalty += v

    return penalty

def compute_overlap_penalty(grid):
    """
    Given a grid that trocks the number of cells that occupy a given
    coordinate, compute a penalty.

    Obviously, locations with no cells or one cell are not penalized.
    However, if there is more than one cell, penalize by the amount in
    excess of one cell.
    """

    penalty = 0
    for coord, v in grid.iteritems():
        if v > 1:
            penalty += (v - 1)

    return penalty

def generate(old_placements, T, T_0, dimensions, method="displace", displace_interchange_ratio=5):
    """
    Given an old placement, generate a new placement by either switching
    the location of two cells or displacing a cell or rotating it.

    T is the current temperature; T_0 is the starting temperature. This
    is used to scale the window for displacing a cell.

    method can be "displace" or "reorient".

    displace_interchange_ratio is the ratio of how often you displace
    a cell and how often you interchange it with another cell.
    """
    new_placements = deepcopy(old_placements)

    # Select a random cell to interchange, displace, or orient
    cellA = random.choice(new_placements)

    method_used = ""

    interchange = random.random() > (1. / displace_interchange_ratio)
    if interchange:
        cellB = cellA
        while cellB is cellA:
            cellB = random.choice(new_placements)

        # print("Interchanging {} (at {}) with {} (at {})".format(cellA["name"], cellA["placement"], cellB["name"], cellB["placement"]))
        cellA["placement"], cellB["placement"] = cellB["placement"], cellA["placement"]
        method_used = "interchange"
    else: # displace or reorient
        if method == "displace":
            scaling_factor = log(T) / log(T_0)

            window_half_height = max(2, np.round(dimensions[1] * scaling_factor))
            window_half_width = max(2, np.round(dimensions[2] * scaling_factor))

            # print("Window width:", window_half_width * 2)
            # print("Window height:", window_half_height * 2)

            old_y, window_center_z, window_center_x = cellA["placement"]

            # Select new X and Z from window
            new_x = random.randint(window_center_x - window_half_width, window_center_x + window_half_width)
            new_z = random.randint(window_center_z - window_half_height, window_center_z + window_half_height)

            cellA["placement"] = [old_y, new_z, new_x]
            method_used = "displace"

        elif method == "reorient":
            # Rotate 90 degrees
            cellA["turns"] = (cellA["turns"] + 1) % 4
            method_used = "reorient"

        else:
            raise ValueError("Method must be 'displace' or 'reorient'")

    return new_placements, method_used

def update(T, alpha=lambda x: 0.9):
    """
    Give the new temperature based on T and alpha.

    alpha is a function that produces a multiplicative factor 0 < a < 1
    that gradually lowers the temperature.
    """
    return T * alpha(T)

def accept(cost_new, cost_old, T):
    """
    Randomly accept this new change, or not, preferring decreases in
    cost.
    """
    delta_cost = cost_new - cost_old
    ratio = -delta_cost / T
    if ratio > 1:
        return True
    acceptance_criterion = min(1, exp(ratio))
    return random.random() < acceptance_criterion

def score(blif, cells, placements, dimensions):
    estimated_net_lengths, occupied = estimate_lengths_and_occupieds(blif, cells, placements)

    wire_length_penalty = sum(estimated_net_lengths.values())
    overlap_penalty = compute_overlap_penalty(occupied)
    oob_penalty = compute_bounds_penalty(occupied, dimensions)

    return wire_length_penalty + overlap_penalty + oob_penalty

def last_consecutive(l, n):
    if len(l) < n:
        return False
    for i in xrange(1,n-1):
        if l[-i] != l[-i-1]:
            return False
    return True

def simulated_annealing_placement(blif, cell_library, initial_placements, dimensions, T_0=500, iterations=2000, generations=20):
    """
    Given an inital placement and initial temperature T_0, perform simulated
    annealing to find the placement with the lowest cost.
    """

    T = T_0
    best_placements = initial_placements

    prev_scores = []
    iteration = 0

    try:
        while iteration < iterations:
            prev_width = 0
            method = "displace"
            for generation in xrange(generations):
                # print("  Generation", generation)
                new_placements, method_used = generate(best_placements, T, T_0, dimensions, method)

                new_score = score(blif, cell_library, new_placements, dimensions)
                old_score = score(blif, cell_library, best_placements, dimensions)

                # Accept or reject this new placement
                # If we rejected a "displace", do a reorientation next
                if accept(new_score, old_score, T):
                    best_placements = new_placements
                    taken_score = new_score
                    if method_used == "reorient":
                        method = "displace"
                else:
                    taken_score = old_score
                    if method_used == "displace":
                        method = "reorient"

            T = update(T)
            prev_scores.append(taken_score)

            # Print iteration and score
            sys.stdout.write("\b" * prev_width)
            msg = "Iteration: {}  Score: {}\r".format(iteration, taken_score)
            sys.stdout.write(msg)
            sys.stdout.flush()
            prev_width = len(msg)

            # if last_consecutive(prev_scores, 20):
            #     break

            iteration += 1

    except KeyboardInterrupt:
        pass

    print("\nPlacement complete")

    return best_placements

def create_layout(dimensions, placements, pregenerated_cells):
    """
    Returns a (y, z, x) -> blockid dict.
    """
    grid = {}

    for placement in placements:
        # Do the cell lookup
        rotation = placement["turns"]
        cell_name = placement["name"]
        cell = pregenerated_cells[cell_name][rotation]

        yy, zz, xx = placement["placement"]

        for y in xrange(cell.blocks.shape[0]):
            for z in xrange(cell.blocks.shape[1]):
                for x in xrange(cell.blocks.shape[2]):
                    blockid = cell.blocks[y, z, x]
                    grid[(yy + y, zz + z, xx + x)] = blockid

    return grid

def shrink(placements, cell_library):
    """
    Returns a copy of the placements with the smallest bounding box,
    and the dimensions of such.
    """
    ys = []
    zs = []
    xs = []

    placements = deepcopy(placements)

    for placement in placements:
        rotation = placement["turns"]
        cell_name = placement["name"]
        cell = cell_library[cell_name][rotation]

        y, z, x = placement["placement"]
        h, w, l = cell.blocks.shape

        ys += [y, y+h]
        zs += [z, z+w]
        xs += [x, x+l]

    min_y, max_y = min(ys), max(ys)
    min_z, max_z = min(zs), max(zs)
    min_x, max_x = min(xs), max(xs)

    dy = max_y - min_y + 1
    dz = max_z - min_z + 1
    dx = max_x - min_x + 1

    for placement in placements:
        y, z, x = placement["placement"]
        placement["placement"] = [y - min_y, z - min_z, x - min_x]

    return placements, [dy, dz, dx]

def grid_to_layout(grid):
    yy = [c[0] for c in grid.iterkeys()]
    zz = [c[1] for c in grid.iterkeys()]
    xx = [c[2] for c in grid.iterkeys()]

    min_y, max_y = min(yy), max(yy)
    min_z, max_z = min(zz), max(zz)
    min_x, max_x = min(xx), max(xx)

    dy = max_y - min_y + 1
    dz = max_z - min_z + 1
    dx = max_x - min_x + 1

    shrunk_layout = np.zeros((dy, dz, dx), dtype=np.int8)

    for (y, z, x), blockid in grid.iteritems():
        shrunk_layout[y-min_y, z-min_z, x-min_x] = blockid

    return shrunk_layout

def shrink_layout(layout):
    """
    Deterimines the smallest 3D array that fits the layout and
    creates a new layout to fit it.
    """
    min_y, min_z, min_x = layout.shape
    max_y, max_z, max_x = [0, 0, 0]

    for y in xrange(layout.shape[0]):
        for z in xrange(layout.shape[1]):
            for x in xrange(layout.shape[2]):
                blockid = layout[y, z, x]
                if blockid > 0:
                    min_y = min(min_y, y)
                    min_z = min(min_z, z)
                    min_x = min(min_x, x)
                    max_y = max(max_y, y)
                    max_z = max(max_z, z)
                    max_x = max(max_x, x)

    dy = max_y - min_y + 1
    dz = max_z - min_z + 1
    dx = max_x - min_x + 1

    shrunk_layout = np.zeros((dy, dz,dx), dtype=np.int8)

    for y in xrange(shrunk_layout.shape[0]):
        for z in xrange(shrunk_layout.shape[1]):
            for x in xrange(shrunk_layout.shape[2]):
                shrunk_layout[y, z, x] = layout[min_y + y, min_z + z, min_x + x]

    return shrunk_layout
