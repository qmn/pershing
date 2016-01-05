from __future__ import print_function

import sys
import random
import numpy as np

from collections import defaultdict
from copy import deepcopy
from math import exp, log, sqrt, ceil

from vis import png

class Placer(object):
    def __init__(self, blif, pregenerated_cells):
        self.blif = blif
        self.pregenerated_cells = pregenerated_cells

    def compute_max_cell_dimension(self):
        # Estimate the width by taking the maximum of X or Z of all cells
        # used in the layout
        cells = [a[0] for a in self.pregenerated_cells.itervalues()]
        max_cell_widths = [max(cell.blocks.shape[1], cell.blocks.shape[2]) for cell in cells]
        max_cell_width = max(max_cell_widths)

        return max_cell_width

    def initial_placement(self, dimensions=None):
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
        blif_cells = self.blif.cells

        # Convert them to references to cells in the cell library, using the
        # first rotation
        cells = [self.pregenerated_cells[bc["name"]][0] for bc in blif_cells]

        # Generate the square root (to place them in a square as best as possible
        num_cells_side = int(ceil(sqrt(len(cells))))

        max_height = max(cell.blocks.shape[0] for cell in cells)

        max_cell_width = self.compute_max_cell_dimension()

        # Add up the longest dimension, plus one for each cell
        width_estimate = (len(cells) * (max_cell_width + spacing))

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

    def locate_pins(self, placements):
        net_pins = defaultdict(list)
        for blif_cell, placement in zip(self.blif.cells, placements):
            # Do the cell lookup
            rotation = placement["turns"]
            cell_name = placement["name"]
            cell = self.pregenerated_cells[cell_name][rotation]

            yy, zz, xx = placement["placement"]
            height, width, length = cell.blocks.shape

            # Add the pins
            for pin, d in cell.ports.iteritems():
                (y, z, x) = d["coordinates"]
                coord = (y + yy, z + zz, x + xx)
                net_name = placement["pins"][pin]
                net_pins[net_name].append(coord)

        return net_pins

    def estimate_lengths_and_occupieds(self, placements):
        net_pins = defaultdict(list)
        grid = defaultdict(int)

        for blif_cell, placement in zip(self.blif.cells, placements):
            # Do the cell lookup
            rotation = placement["turns"]
            cell_name = placement["name"]
            cell = self.pregenerated_cells[cell_name][rotation]

            yy, zz, xx = placement["placement"]
            height, width, length = cell.blocks.shape

            # Add all items in this 3D matrix by the value 1
            for y in xrange(height):
                for z in xrange(width):
                    for x in xrange(length):
                        coord = (yy + y, zz + z, xx + x)
                        grid[coord] += 1

            # Add the pins
            for pin, d in cell.ports.iteritems():
                (y, z, x) = d["coordinates"]
                coord = (y + yy, z + zz, x + xx)
                net_name = placement["pins"][pin]
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


    def compute_occupied_locations(self, placements, dimensions):

        grid = defaultdict(int)

        for placement in placements:
            # Do the cell lookup
            rotation = placement["turns"]
            cell_name = placement["name"]
            cell = self.pregenerated_cells[cell_name][rotation]

            yy, zz, xx = placement["placement"]

            for y in xrange(cell.blocks.shape[0]):
                for z in xrange(cell.blocks.shape[1]):
                    for x in xrange(cell.blocks.shape[2]):
                        if cell.blocks[y, z, x] > 0:
                            grid[(yy + y, zz + z, xx + x)] += 1

        # print(grid)

        return grid

    def compute_bounds_penalty(self, grid, dimensions):
        penalty = 0
        for coord, v in grid.iteritems():
            y, z, x = coord
            if y < 0 or y >= dimensions[0] or \
               z < 0 or z >= dimensions[1] or \
               x < 0 or x >= dimensions[2]:
                penalty += v

        return penalty

    def compute_overlap_penalty(self, grid):
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

    def generate(self, old_placements, T, T_0, dimensions, method="displace", displace_interchange_ratio=5):
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


    def score(self, placements, dimensions):
        estimated_net_lengths, occupied = self.estimate_lengths_and_occupieds(placements)

        wire_length_penalty = sum(estimated_net_lengths.values())
        overlap_penalty = self.compute_overlap_penalty(occupied)
        oob_penalty = self.compute_bounds_penalty(occupied, dimensions)

        return wire_length_penalty + overlap_penalty + oob_penalty

    def last_consecutive(l, n):
        if len(l) < n:
            return False
        for i in xrange(1,n-1):
            if l[-i] != l[-i-1]:
                return False
        return True

    def simulated_annealing_placement(self, initial_placements, dimensions, T_0=500, iterations=2000, generations=20):
        """
        Given an inital placement and initial temperature T_0, perform simulated
        annealing to find the placement with the lowest cost.
        """

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

        T = T_0
        best_placements = initial_placements

        prev_scores = []
        iteration = 0

        try:
            prev_width = 0
            while iteration < iterations:
                method = "displace"
                for generation in xrange(generations):
                    # print("  Generation", generation)
                    new_placements, method_used = self.generate(best_placements, T, T_0, dimensions, method)

                    new_score = self.score(new_placements, dimensions)
                    old_score = self.score(best_placements, dimensions)

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
                msg = "Iteration: {}  Score: {}".format(iteration, taken_score)
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

    def placement_to_layout(self, dimensions, placements, min_y=5):
        """
        Returns a (y, z, x) -> blockid dict.
        """
        height, width, length = dimensions
        height = min(min_y, height)
        layout = np.zeros((height, width, length), dtype=np.int8)

        for placement in placements:
            # Do the cell lookup
            rotation = placement["turns"]
            cell_name = placement["name"]
            cell = self.pregenerated_cells[cell_name][rotation]

            y, z, x = placement["placement"]
            height, width, length = cell.blocks.shape

            # Paste cell.blocks into the layout
            layout[y:y+height, z:z+width, x:x+length] = cell.blocks

        return layout

    def shrink(self, placements):
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
            cell = self.pregenerated_cells[cell_name][rotation]

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

class GridPlacer(Placer):
    """
    GridPlacer generates placements aligned on a grid with each location
    enough to fit the largest standard library cell.

    It takes an extra parameter, grid_spacing, to determine the spacing
    between adjacent cell rows and columns.
    """

    def __init__(self, blif, pregenerated_cells, grid_spacing=1):
        super(GridPlacer, self).__init__(blif, pregenerated_cells)
        self.grid_spacing = grid_spacing
        self.grid_width = self.compute_max_cell_dimension()
        self.interval = self.grid_spacing + self.grid_width

    def snap_to_grid(self, coord):
        y, z, x = coord
        nz = int(round(z / self.interval) * self.interval)
        nx = int(round(x / self.interval) * self.interval)
        return (y, nz, nx)

    def generate(self, old_placements, T, T_0, dimensions, method="displace", displace_interchange_ratio=5):
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

                window_half_height = max(2, round(self.interval * 5 * scaling_factor))
                window_half_width = max(2, round(self.interval * 5 * scaling_factor))

                old_y, window_center_z, window_center_x = cellA["placement"]

                # Select new X and Z from window
                new_x = random.randint(window_center_x - window_half_width, window_center_x + window_half_width)
                new_z = random.randint(window_center_z - window_half_height, window_center_z + window_half_height)

                new_coord = [old_y, new_z, new_x]
                
                cellA["placement"] = self.snap_to_grid(new_coord)
                method_used = "displace"

            elif method == "reorient":
                # Rotate 90 degrees
                cellA["turns"] = (cellA["turns"] + 1) % 4
                method_used = "reorient"

            else:
                raise ValueError("Method must be 'displace' or 'reorient'")

        return new_placements, method_used
