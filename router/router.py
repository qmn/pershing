from __future__ import print_function

from copy import deepcopy
from collections import defaultdict
import random

import numpy as np
from scipy.spatial.distance import cityblock

from util.blocks import block_names

class Router:
    def __init__(self, blif, pregenerated_cells):
        self.blif = blif
        self.pregenerated_cells = pregenerated_cells

    def extract_pin_locations(self, placements):
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
                net_name = placement["pins"][pin]
                net_pins[net_name].append(coord)

        return net_pins
        
    def create_net_segments(self, placements):

        def minimum_spanning_tree(net_pins):
            """
            For a given set of (y, z, x) coordinates given by net_pins, compute
            the segments that form the minimum spanning tree, using Kruskal's
            algorithm.
            """

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
                    # Weight each pin distance based on the Manhattan
                    # distance.
                    weights[(pin, pin2)] = cityblock(pin, pin2)

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

        net_pins = self.extract_pin_locations(placements)

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

    def net_to_wire_and_violation(self, net, dimensions, pins):
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

        for coord in net:
            y, z, x = coord
            # Generate the wire itself
            wire[y, z, x] = redstone
            wire[y - 1, z, x] = stone

            # Generate the violation matrix, unless it's a pin
            if coord not in pins:
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

    def unify_violations(self, nets, violations, dimensions, pins):
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

    def initial_routing(self, net_segments, placements):
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

    def generate_violation_matrices(self, routing, net_segments, net_pins, layout_dimensions):
        violations = defaultdict(list)
        for net_name, nets in routing.iteritems():
            pins = net_pins[net_name]
            for net in nets:
                _, v = self.net_to_wire_and_violation(net, layout_dimensions, pins)
                violations[net_name].append(v)

        return violations

    def generate_net_matrices(self, routing, net_segments, net_pins, layout_dimensions):
        """
        For the nets specified by routing, create:
        net_wires: a dictionary on net names with a list of blocks with
            wires connecting the net.
        net_violations: a dictionary on net names with 3D matrices
            specifying which blocks to test for violations.
        """
        net_wires = defaultdict(list)
        net_violations = defaultdict(list)

        for net_name, nets in routing.iteritems():
            pins = net_pins[net_name]
            for net in nets:
                w, v = self.net_to_wire_and_violation(net, layout_dimensions, pins)
                net_wires[net_name].append(w)
                net_violations[net_name].append(v)

        return net_wires, net_violations

    def generate_usage_matrix(self, placed_layout, routing, exclude=[]):
        usage_matrix = np.copy(placed_layout)
        for net_name, wires in routing.iteritems():
            for i, wire in enumerate(wires):
                if (net_name, i) in exclude:
                    continue
                for coord in wire:
                    usage_matrix[coord] = 1

        return usage_matrix

    def score_routing(self, routing, net_segments, layout, net_pins, violation_matrices, usage_matrix):
        """
        For the given layout, and the routing, produce the score of the
        routing.

        The score is composed of its constituent nets' scores, and the
        score of each net is based on the number of violations it has,
        the number of vias and pins and the ratio of its actual length
        and the lower bound on its length.

        layout is the 3D matrix produced by the placer.
        """
        alpha = 3
        beta = 0.1
        gamma = 1

        net_scores = {}
        net_num_violations = {}

        # Score each net segment in the entire net
        for net_name in net_segments:
            net_scores[net_name] = []
            net_num_violations[net_name] = []

            for i, pins in enumerate(net_segments[net_name]):
                routed_net = routing[net_name][i]

                # Violations
                violation_matrix = violation_matrices[net_name][i]
                violations = self.compute_net_violations(violation_matrix, usage_matrix)
                net_num_violations[net_name].append(violations)

                # Number of vias and pins
                vias = 0
                num_pins = 2
                pins_vias = vias - num_pins

                # Lower length bound
                lower_length_bound = max(1, cityblock(pins[0], pins[1]))
                length_ratio = len(routed_net) / lower_length_bound

                score = (alpha * violations) + (beta * pins_vias) + (gamma * length_ratio)

                net_scores[net_name].append(score)

        # print(routing)
        # print(net_scores)
        return net_scores, net_num_violations

    def normalize_net_scores(self, net_scores, norm_margin=0.1):
        """
        Normalize scores to [norm_margin, 1-norm_margin].
        """
        scores = sum(net_scores.itervalues(), [])
        min_score, max_score = min(scores), max(scores)
        norm_range = 1.0 - 2*norm_margin
        scale = norm_range / (max_score - min_score)

        normalized_scores = {}
        for net_name, scores in net_scores.iteritems():
            new_net_scores = [norm_margin + score * scale for score in scores]
            normalized_scores[net_name] = new_net_scores

        return normalized_scores

    def natural_selection(self, net_scores):
        """
        natural_selection() selects which nets and net segments to rip up
        and replace. It returns a list of (net name, index) tuples, in
        which the index represents the net to replace.
        """
        rip_up = []
        for net_name, norm_scores in net_scores.iteritems():
            for i, norm_score in enumerate(norm_scores):
                x = random.random()
                if x < norm_score:
                    rip_up.append((net_name, i))

        return rip_up

    def re_route(self, initial_routing, net_segments, net_pins, placed_layout):
        """
        re_route() produces new routings until there are no more net
        violations that cause the routing to be infeasible.
        """
        violation_matrices = self.generate_violation_matrices(initial_routing, net_segments, net_pins, placed_layout.shape)
        usage_matrix = self.generate_usage_matrix(placed_layout, initial_routing)

        # Score the initial routing
        net_scores, net_violations = self.score_routing(initial_routing, net_segments, placed_layout, net_pins, violation_matrices, usage_matrix)
        num_violations = sum(sum(net_violations.itervalues(), []))
        iterations = 0

        routing = deepcopy(initial_routing)

        while num_violations > 0:
            print("Iteration:", iterations, " Violations:", num_violations)

            # Normalize net scores
            normalized_scores = self.normalize_net_scores(net_scores)

            # Select nets to rip-up and re-route
            rip_up = self.natural_selection(normalized_scores)

            print("Re-routing", len(rip_up), "nets")

            # Re-route these nets
            routing = routing

            # Re-score this net
            net_scores, net_violations = self.score_routing(routing, net_segments, placed_layout, net_pins, violation_matrices, usage_matrix)
            num_violations = sum(sum(net_violations.itervalues(), []))
            iterations += 1

        return routing

