from __future__ import print_function

import heapq
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
        self.cost_matrix = None
        self.backtrace_matrix = None

    def extract_extended_pin_locations(self, placements):
        """
        Returns a dictionary keyed on net names, with arrays of
        dictionaries:
        { net_name: [ { "cell_index": i,
                        "pin": s,
                        "pin_coord": (y, z, x),
                        "route_coord": (y, z, x),
                        "is_output": True/False
                      }
                      ...
                    ]
          ...
        }

        pin_coord is the location of the actual pin, but route_coord is
        where a router should start from.
        """

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
        for i, placement in enumerate(placements):
            # Do the cell lookup
            rotation = placement["turns"]
            cell_name = placement["name"]
            cell = self.pregenerated_cells[cell_name][rotation]

            yy, zz, xx = placement["placement"]

            for pin, d in cell.ports.iteritems():
                (y, z, x) = d["coordinates"]
                facing = d["facing"]
                is_output = (d["direction"] == "output")
                coord = (y + yy, z + zz, x + xx)
                extended_coord = extend_pin(coord, facing)
                net_name = placement["pins"][pin]

                net_pin_info = {"cell_index": i,
                                "pin": pin,
                                "pin_coord": coord,
                                "route_coord": extended_coord,
                                "is_output": is_output}
                net_pins[net_name].append(net_pin_info)

        return net_pins

    def create_net_segments(self, pin_locations):

        def minimum_spanning_tree(size, distance_metric):
            """
            Compute the segments that form the minimum spanning tree,
            using Kruskal's algorithm.

            The input is the size of the graph, and the tree is organized
            as a list of elements, with no gaps. (To be precise,
            distance_metric(u, v) must be defined for all u, v in [0, size).)

            distance_metric(u, v) is the function that computes the distance
            between the nodes indexed u and v.

            The output is a list of (i, j) pairs specifying the MST.
            """

            # Create sets for each of the pins
            sets = []
            for i in xrange(size):
                s = set([i])
                sets.append(s)

            # Compute the weight matrix
            weights = {}
            for i in xrange(size):
                for j in xrange(i+1, size):
                    weights[(i, j)] = distance_metric(i, j)

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

        def dag_from_output_mst(graph_connections, pin_list):
            """
            Perform a depth-first search from the locations marked output
            so that all tuples are ordered so that the driver comes first
            and the driven pin comes second.
            """
            # Each MST has n nodes and n-1 edges.
            drivers = set()

            for u, v in graph_connections:
                uio = pin_list[u]["is_output"]
                vio = pin_list[v]["is_output"]

                if uio:
                    drivers.add(u)
                if vio:
                    drivers.add(v)

            dag = []
            # Assemble the DAG
            seen = [False] * len(graph_connections)
            while not all(seen):
                for i, (u, v) in enumerate(graph_connections):
                    if seen[i]:
                        continue

                    # If one of the endpoints of the segment appears in
                    # drivers, then now the other end is driven, and is
                    # therefore a driver.
                    if u in drivers:
                        dag.append((u, v))
                        drivers.add(v)
                        seen[i] = True
                    elif v in drivers:
                        dag.append((v, u))
                        drivers.add(u)
                        seen[i] = True

            assert len(dag) == len(graph_connections)

            dag = [(pin_list[u], pin_list[v]) for (u, v) in dag]
            return dag

        net_segments = {}
        for net, pin_list in pin_locations.iteritems():
            if len(pin_list) < 2:
                continue

            # Define the metric on the pin list
            def metric(u, v):
                coord_u = pin_list[u]["route_coord"]
                coord_v = pin_list[v]["route_coord"]
                return cityblock(coord_u, coord_v)

            graph_connections = minimum_spanning_tree(len(pin_list), metric)
            dag = dag_from_output_mst(graph_connections, pin_list)
            net_segments[net] = dag

        return net_segments

    def dumb_route(self, a, b):
        """
        Routes, on one Y layer only, the path between a and b, going
        east/west, then north/south, ignorant of all intervening objects.
        """
        ay, az, ax = a
        by, bz, bx = b

        net = [a]

        cy, cz, cx = a
        while cy != by or cz != bz or cx != bx:
            if cz > bz:
                cz -= 1
            elif cz < bz:
                cz += 1
            elif cx > bx:
                cx -= 1
            elif cx < bx:
                cx += 1
            else:
                raise ValueError("dumb_route cannot route on Y layer")

            coord = (cy, cz, cx)
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
        wire = np.zeros(dimensions, dtype=np.uint8)
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
                        try:
                            violation[y + vy, z + vz, x + vx] = True
                        except IndexError:
                            pass

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
        violations = np.logical_and(violation, occupieds)
        return sum(violations.flat)

    def initial_routing(self, placements, layout_dimensions):
        """
        For all nets, produce a dumb initial routing.

        The returned routing dictionary is of the structure:
        { net name:
            { pins: [(y, z, x) tuples]
              segments: [
                { pins: [(ay, az, ax), (by, bz, bx)],
                  net: [path of redstone],
                  wire: [path of redstone and blocks],
                  violation: [violation matrix]
                }
              ]
            }
        }
        """
        routings = {}

        pin_locations = self.extract_extended_pin_locations(placements)
        net_segments = self.create_net_segments(pin_locations)

        for net_name, segment_endpoints in net_segments.iteritems():
            segments = []
            for a, b in segment_endpoints:
                coord_a = a["route_coord"]
                coord_b = b["route_coord"]
                net = self.dumb_route(coord_a, coord_b)
                w, v = self.net_to_wire_and_violation(net, layout_dimensions, [coord_a, coord_b])
                segment = {"pins": [a, b], "net": net, "wire": w, "violation": v}
                segments.append(segment)

            net_pins = pin_locations[net_name]
            routings[net_name] = {"pins": net_pins, "segments": segments}

        return routings

    def generate_usage_matrix(self, placed_layout, routing, exclude=[]):
        blocks, _ = placed_layout
        usage_matrix = np.copy(blocks)
        for net_name, d in routing.iteritems():
            for i, segment in enumerate(d["segments"]):
                if (net_name, i) in exclude:
                    continue
                else:
                    usage_matrix = np.logical_or(usage_matrix, segment["wire"])

        return usage_matrix

    def score_routing(self, routing, usage_matrix):
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
        for net_name, d in routing.iteritems():
            net_scores[net_name] = []
            net_num_violations[net_name] = []

            for i, segment in enumerate(d["segments"]):
                routed_net = segment["net"]

                # Violations
                violation_matrix = segment["violation"]
                violations = self.compute_net_violations(violation_matrix, usage_matrix)
                net_num_violations[net_name].append(violations)

                # Number of vias and pins
                vias = 0
                num_pins = 2
                pins_vias = vias - num_pins

                # Lower length bound
                coord_a = segment["pins"][0]["route_coord"]
                coord_b = segment["pins"][1]["route_coord"]
                lower_length_bound = max(1, cityblock(coord_a, coord_b))
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

    def maze_route(self, a, b, placed_layout, usage_matrix):
        """
        Given two pins to re-route, find the best path using Lee's maze
        routing algorithm.
        """
        blocks, _ = placed_layout

        def clear_matrices():
            height, width, length = self.cost_matrix.shape
            for y in xrange(height):
                for z in xrange(width):
                    for x in xrange(length):
                        self.cost_matrix[y, z, x] = -1
                        self.backtrace_matrix[y, z, x] = 0

        # If not created yet, create the cost matrices, otherwise, just zero them out
        if self.cost_matrix is None or self.backtrace_matrix is None:
            self.cost_matrix = np.full_like(blocks, -1, dtype=np.int)
            self.backtrace_matrix = np.zeros_like(blocks, dtype=np.int)
        else:
            clear_matrices()

        def violating(coord):
            if coord in [a, b]:
                return False

            violation_directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]
            for dy in [0, -1]:
                for dz, dx in violation_directions:
                    y, z, x = coord
                    new_coord = (y + dy, z + dz, x + dx)
                    if new_coord in [a, b]:
                        continue
                    try:
                        if usage_matrix[new_coord]:
                            return True
                    except IndexError:
                        continue

            return False

        # Possible list of movements
        EAST = 1
        MOVE_EAST = (0, 0, 1)
        NORTH = 2
        MOVE_NORTH = (0, 1, 0)
        WEST = 3
        MOVE_WEST = (0, 0, -1)
        SOUTH = 4
        MOVE_SOUTH = (0, -1, 0)
        UP = 5
        MOVE_UP = (3, 0, 0)
        DOWN = 6
        MOVE_DOWN = (-3, 0, 0)

        # Backtrace is the way you go from the start.
        movements = [MOVE_EAST, MOVE_NORTH, MOVE_WEST, MOVE_SOUTH, MOVE_UP, MOVE_DOWN]
        backtraces = [WEST, SOUTH, EAST, NORTH, DOWN, UP]
        costs = [1, 1, 1, 1, 3, 3]

        violation_cost = 1000

        # Start breadth-first with a
        visited = np.zeros_like(blocks, dtype=bool)
        heap_locations = np.zeros_like(blocks, dtype=bool)
        min_dist_heap = []
        self.cost_matrix[a] = 0
        heapq.heappush(min_dist_heap, (0, a))
        heap_locations[a] = 1

        visited_size = sum(visited.flat != 0)

        while len(min_dist_heap) > 0:
            # print("{} -> {}".format(len(to_visit), len(visited)))
            _, location = heapq.heappop(min_dist_heap)
            heap_locations[location] = 0
            visited[location] = 1

            # For each candidate movement
            for movement, backtrace, movement_cost in zip(movements, backtraces, costs):
                dy, dz, dx = movement
                y, z, x = location
                new_location = (y + dy, z + dz, x + dx)

                try:
                    # less-than-zero checks
                    if y + dy < 0 or z + dz < 0 or x + dx < 0:
                        continue

                    if visited[new_location] == 1:
                        continue

                    if violating(new_location):
                        new_location_cost = self.cost_matrix[location] + violation_cost
                    else:
                        new_location_cost = self.cost_matrix[location] + movement_cost

                    # print(location, cost_matrix[location], "->", new_location, cost_matrix[new_location], new_location_cost)
                    if self.cost_matrix[new_location] == -1 or new_location_cost < self.cost_matrix[new_location]:
                        self.cost_matrix[new_location] = new_location_cost
                        self.backtrace_matrix[new_location] = backtrace

                    if heap_locations[new_location] == 0:
                        heapq.heappush(min_dist_heap, (new_location_cost, new_location))
                        heap_locations[new_location] = 1

                except IndexError:
                    continue


        # Backtrace, if a path found
        backtrace_movements = [MOVE_WEST, MOVE_SOUTH, MOVE_EAST, MOVE_NORTH, MOVE_DOWN, MOVE_UP]
        if visited[b] == 1:
            net = [b]
            while net[-1] != a:
                last = net[-1]
                backtrace_entry = self.backtrace_matrix[last]
                if backtrace_entry == 0 or backtrace_entry > 6:
                    raise ValueError("Unknown backtrace entry {}".format(backtrace_entry))
                movement = backtrace_movements[backtraces.index(backtrace_entry)]
                dy, dz, dx = movement
                y, z, x = net[-1]
                back_location = (y + dy, z + dz, x + dx)
                net.append(back_location)

            print("Net score:", self.cost_matrix[b], " Length:", len(net))
            net.reverse()
            return net
        else:
            raise ValueError("No path between {} and {} found!".format(a, b))
            # print(cost_matrix[1])
            # print(backtrace_matrix[1])
            return None

    def re_route(self, initial_routing, placed_layout):
        """
        re_route() produces new routings until there are no more net
        violations that cause the routing to be infeasible.
        """
        usage_matrix = self.generate_usage_matrix(placed_layout, initial_routing)

        # Score the initial routing
        net_scores, net_violations = self.score_routing(initial_routing, usage_matrix)
        num_violations = sum(sum(net_violations.itervalues(), []))
        iterations = 0

        routing = deepcopy(initial_routing)

        blocks, _ = placed_layout
        shape = blocks.shape

        try:
            while num_violations > 0:
                print("Iteration:", iterations, " Violations:", num_violations)

                # Normalize net scores
                normalized_scores = self.normalize_net_scores(net_scores)

                # Select nets to rip-up and re-route
                rip_up = self.natural_selection(normalized_scores)

                # Re-route these nets
                usage_matrix = self.generate_usage_matrix(placed_layout, routing, exclude=rip_up)

                print("Re-routing", len(rip_up), "nets")
                for net_name, i in sorted(rip_up, key=lambda x: normalized_scores[x[0]][x[1]], reverse=True):
                    pin_info_a, pin_info_b = routing[net_name]["segments"][i]["pins"]
                    a = pin_info_a["route_coord"]
                    b = pin_info_b["route_coord"]
                    new_net = self.maze_route(a, b, placed_layout, usage_matrix)
                    routing[net_name]["segments"][i]["net"] = new_net

                    w, v = self.net_to_wire_and_violation(new_net, shape, [a, b])
                    routing[net_name]["segments"][i]["wire"] = w
                    routing[net_name]["segments"][i]["violation"] = v

                    # Re-add this net to the usage matrix
                    usage_matrix = np.logical_or(usage_matrix, w)

                # Re-score this net
                net_scores, net_violations = self.score_routing(routing, usage_matrix)
                num_violations = sum(sum(net_violations.itervalues(), []))
                iterations += 1
                print()
        except KeyboardInterrupt:
            pass

        return routing

    def serialize_routing(self, original_routing, shape, f):
        """
        Return the routing without the wire or the violation matrices
        (which can't be serialized as-is and takes too much space
        anyway).
        """
        import json
        routing = deepcopy(original_routing)
        for net_name, net in routing.iteritems():
            for i, segment in enumerate(net["segments"]):
                del segment["violation"]
                del segment["wire"]

        json.dump(routing, f)
        f.write("\n")
        json.dump(shape, f)

    def deserialize_routing(self, f):
        import json
        routing = json.loads(f.readline())
        shape = json.loads(f.readline())
        for net_name, net in routing.iteritems():
            for i, segment in enumerate(net["segments"]):
                a, b = segment["pins"]
                n = segment["net"]
                w, v = self.net_to_wire_and_violation(n, shape, [a, b])
                segment["wire" ] = w
                segment["violation"] = v

        return routing

