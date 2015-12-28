from __future__ import print_function

from collections import defaultdict

import numpy as np
from scipy.spatial.distance import cityblock

from util.blocks import block_names

class Router:
    def __init__(self, blif, pregenerated_cells):
        self.blif = blif
        self.pregenerated_cells = pregenerated_cells
        
    def create_net_segments(self, placements):

        def minimum_spanning_tree(net_pins):
            """
            For a given set of (y, z, x) coordinates given by net_pins, compute
            the segments that form the minimum spanning tree, using Kruskal's
            algorithm.
            """

            def pin_distance(a, b):
                return cityblock(a, b)

            # Create sets for each of the pins
            sets = []
            for pin in net_pins:
                s = set([pin])
                sets.append(s)

            # Compute the weight matrix
            weights = {}
            for pin in net_pins:
                for pin2 in net_pins:
                    if pin == pin2:
                        continue

                    weights[(pin, pin2)] = pin_distance(pin, pin2)

            def find_set(u):
                for i, s in enumerate(sets):
                    if u in s:
                        return i
                return -1

            # Create spanning tree!
            A = set()
            for u, v in sorted(weights, key=weights.get):
                u_i = find_set(u)
                v_i = find_set(v)
                if u_i != v_i:
                    A.add((u, v))
                    # Union the two sets
                    sets[v_i] |= sets[u_i]
                    sets.pop(u_i)

            return A

        def extend_pin(coord, facing):
            """
            Returns the coordinates of the pin based moving in the
            direction given by "facing".
            """
            (y, z, x) = coord

            if facing == "north":
                z -= 1
            elif facing == "west":
                x -= 1
            elif facing == "south":
                z += 1
            elif facing == "east":
                x += 1

            return (y, z, x)


        net_pins = defaultdict(list)

        # For each wire, locate its pins according to the placement
        for blif_cell, placement in zip(self.blif.cells, placements):
            # Do the cell lookup
            rotation = placement["turns"]
            cell_name = placement["name"]
            cell = self.pregenerated_cells[cell_name][rotation]

            yy, zz, xx = placement["placement"]

            for pin, d in cell.ports.iteritems():
                (y, z, x) = d["coordinates"]
                facing = d["facing"]
                coord = (y + yy, z + zz, x + xx)
                coord = extend_pin(coord, facing)
                net_name = placement["pins"][pin]
                net_pins[net_name].append(coord)

        net_segments = {}
        for net, pin_list in net_pins.iteritems():
            if len(pin_list) < 2:
                continue
            net_segments[net] = minimum_spanning_tree(pin_list)

        return net_segments

    def dumb_route(self, a, b):
        """
        Routes, on one Y layer only, the path between a and b, going
        east/west, then north/south, ignorant of all intervening objects.
        """
        ay, az, ax = a
        by, bz, bx = b

        net = []

        # Move horizontally from a to b
        start, stop = min(ax, bx), max(ax, bx) + 1
        for x in xrange(start, stop):
            coord = (ay, az, x)
            net.append(coord)

        # Move vertically from bx to b
        start, stop = min(az, bz), max(az, bz) + 1
        for z in xrange(start, stop):
            coord = (ay, z, bx)
            net.append(coord)

        return net

    def net_to_wire_and_violation(self, net, dimensions):
        """
        Converts a realized net, which is a list of block positions from
        one pin to another, into two matrices:
        - wire: the redstone + stone block
        - violation: the places where this redstone may possibly transmit

        The net is the list of where the _redstone_ is.
        """
        wire = np.zeros(dimensions, dtype=np.int8)
        violation = np.zeros(dimensions, dtype=np.bool)

        redstone = block_names.index("redstone_wire")
        stone = block_names.index("stone")

        violation_directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]

        for y, z, x in net:
            # Generate the wire itself
            wire[y, z, x] = redstone
            wire[y - 1, z, x] = stone

            # Generate the violation matrix
            for vy in [0, -1]:
                for vz, vx in violation_directions:
                    violation[y + vy, z + vz, x + vx] = True

        # Remove "wire" from the violation matrix so that it doesn't
        # violate itself
        for y, z, x in net:
            violation[y, z, x] = False
            violation[y - 1, z, x] = False

        return wire, violation

    def compute_net_violations(self, violation, occupieds):
        """
        For each non-zero entry, see if there is anything in "occupieds".
        """
        return sum(np.logical_and(violation, occupieds).flat)

    def unify_violations(self, nets, violations, dimensions):
        """
        Given the set of wires and violations, produce a unified view of
        the violations to search for.
        """
        v = np.zeros(dimensions, dtype=np.bool)

        # Add together the violation matrices
        for violation_matrix in violations:
            v = np.logical_or(v, violation_matrix)

        # Remove the nets from the violation matrix
        for net in nets:
            for y, z, x in net:
                v[y, z, x] = False
                v[y - 1, z, x] = False

        return v

    def initial_routing(self, net_segments):
        """
        For all nets, produce a dumb initial routing.
        """
        routings = defaultdict(list)
        for net_name, segments in net_segments.iteritems():
            for segment in segments:
                a, b = segment
                net = self.dumb_route(a, b)
                routings[net_name].append(net)
        return routings

    def score_routing(self, routing, layout):
        """
        For the given layout, and the routing, produce the score of the
        routing.

        The score is composed of its constituent nets' scores, and the
        score of each net is based on the number of violations it has,
        the number of vias and pins and the ratio of its actual length
        and the lower bound on its length.

        layout is the 3D matrix produced by the placer.
        """

        net_wires = defaultdict(list)
        net_violations = {}

        layout_dimensions = layout.shape

        usage_matrix = np.copy(layout)

        # Construct the usage matrix for each of the nets, and save
        # some time by pre-adding them to the usage_matrix
        for net_name, nets in routing.iteritems():
            vv = []

            for net in nets:
                w, v = self.net_to_wire_and_violation(net, layout_dimensions)
                net_wires[net_name].append(w)
                vv.append(v)
                # Add the wire to the usage matrix
                usage_matrix = np.logical_or(usage_matrix, w)

            # Assemble the violation matrix for the whole net
            violation_matrix = self.unify_violations(nets, vv, layout_dimensions)
            net_violations[net_name] = violation_matrix

        net_scores = {}

        for net_name, violation_matrix in net_violations.iteritems():
            violations = self.compute_net_violations(violation_matrix, usage_matrix)
            net_scores[net_name] = violations
            print(net_name, violations)

        return net_scores
