from __future__ import print_function

from collections import defaultdict

import numpy as np
from scipy.spatial.distance import cityblock

def pin_distance(a, b):
    return cityblock(a, b)

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
        
    
def create_net_segments(blif, cell_library, placements):
    net_pins = defaultdict(list)

    # For each wire, locate its pins according to the placement
    for blif_cell, placement in zip(blif.cells, placements):
        # Do the cell lookup
        rotation = placement["turns"]
        cell_name = placement["name"]
        cell = cell_library[cell_name][rotation]

        yy, zz, xx = placement["placement"]

        for y in xrange(cell.ports.shape[0]):
            for z in xrange(cell.ports.shape[1]):
                for x in xrange(cell.ports.shape[2]):
                    port_name = cell.ports[y, z, x]
                    if port_name:
                        net_name = placement["pins"][port_name]
                        coord = (y + yy, z + zz, x + xx)
                        net_pins[net_name].append(coord)

    net_segments = {}
    for net, pin_list in net_pins.iteritems():
        if len(pin_list) < 2:
            continue
        net_segments[net] = minimum_spanning_tree(pin_list)

    print(net_segments)

    return net_segments
