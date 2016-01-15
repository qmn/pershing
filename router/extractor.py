from __future__ import print_function

from copy import deepcopy
import numpy as np

from util.blocks import block_names, Piston

class Extractor:
    WIRE = 1
    REPEATER = 2
    UP_VIA = 3
    DOWN_VIA = 4

    def extraction_to_string(extracted_net):
        d = {Extractor.WIRE: "WIRE",
             Extractor.REPEATER: "REPEATER",
             Extractor.UP_VIA: "UP_VIA",
             Extractor.DOWN_VIA: "DOWN_VIA"}
        return [d[i] for i in extracted_net]

    def __init__(self, blif, pregenerated_cells):
        self.blif = blif
        self.pregenerated_cells = pregenerated_cells

    def extract_net_segment(self, segment, start_pin, stop_pin):
        """
        Given the coordinates of the path of this net, generate the
        actual wire path, inserting repeaters as needed.
        """

        def determine_movement(c1, c2):
            y1, z1, x1 = c1
            y2, z2, x2 = c2

            # Functions determining which is next
            def is_up_via():
                return (z1 == z2) and (x1 == x2) and (y2 - y1 == 3)

            def is_down_via():
                return (z1 == z2) and (x1 == x2) and (y2 - y1 == -3)

            def is_wire():
                """
                It's a wire if it moves in any of the compass directions and
                the change in Y is no more than one.
                """
                return abs(y1 - y2) <= 1 and \
                    ((x1 == x2 and abs(z1 - z2) == 1) or \
                     (z1 == z2 and abs(x1 - x2) == 1))

            if is_wire():
                return Extractor.WIRE
            elif is_up_via():
                return Extractor.UP_VIA
            elif is_down_via():
                return Extractor.DOWN_VIA
            else:
                raise ValueError("Unknown connection between {} and {}".format(c1, c2))
                return None

        # Actually 15, but assume that the gates have a margin of 2.
        # TODO: have gates define their output signal strength
        max_output_signal_strength = 13
        min_input_signal_strength = 1

        def generate_initial_extraction(net):
            # print(start_pin)
            # print(net)
            # print(stop_pin)

            # start_pin to 0
            extracted_net = [determine_movement(start_pin, net[0])]

            # (0 to 1) to (n-2 to n-1)
            for i in xrange(len(net)-1):
                c1, c2 = net[i], net[i+1]
                extracted_net.append(determine_movement(c1, c2))

            # n-1 to stop_pin
            extracted_net.append(determine_movement(net[-1], stop_pin))

            return extracted_net

        net_coords = segment["net"]
        inital_extraction = generate_initial_extraction(net_coords)

        # Split the extraction, determine redundant pieces (namely, the
        # wire-to-via connections), and then insert repeaters as needed.
        item, coords = self.split_extraction(inital_extraction, net_coords, start_pin, stop_pin)

        return zip(item, coords)

    def place_repeaters(self, extracted_net_subsection, coords, start_coord, stop_coord, start_strength=13, min_strength=1):
        """
        Place repeaters along this path until the final location has
        strength min_strength. min_strength must be at least 1.

        extracted_net_subsection is the list of [WIRE, WIRE, WIRE, ...]
        wire pieces to place repeaters along.

        start_coord and stop_coord are the coordinates of the coordinates
        immediately before and after (for usage with repeatable()).
        """

        subsection = list(extracted_net_subsection)

        def repeatable(before, after):
            """
            A signal can be repeated as long as the block before the
            repeater and after the repeater form a line in X or Z.
            """
            yb, zb, xb = before
            ya, za, xa = after

            return yb == ya and \
                ((zb == za and abs(xb - xa) == 2) or \
                 (xb == xa and abs(zb - za) == 2))

        def compute_strength(subsection):
            if subsection == []:
                return []

            strengths = [0] * len(subsection)
            strengths[0] = start_strength
            i = 1
            while strengths[i-1] > 0 and i < len(strengths):
                if subsection[i] == Extractor.WIRE:
                    strengths[i] = strengths[i-1] - 1
                elif subsection[i] == Extractor.REPEATER:
                    strengths[i] = 16
                i += 1

            return strengths

        strengths = compute_strength(subsection)
        while any(strength < min_strength for strength in strengths):
            # find candidate section, the first section where it is less than
            # the minimum strength
            repeater_i = strengths.index(min_strength - 1)

            while repeater_i >= 0:
                if repeater_i > 0:
                    before = coords[repeater_i - 1]
                else:
                    before = start_coord

                if repeater_i < len(coords) - 1:
                    after = coords[repeater_i + 1]
                else:
                    after = stop_coord

                if repeatable(before, after):
                    subsection[repeater_i] = Extractor.REPEATER
                    break
                else:
                    # move the repeater back
                    repeater_i -= 1

            if repeater_i < 0:
                raise ValueError("Cannot place repeaters to satisfy minimum strength.")

            strengths = compute_strength(subsection)

        # print("Placed repeaters:", subsection)
        return subsection

    def split_extraction(self, extracted_net, net_coords, start_coord, stop_coord):
        """
        Split up the extracted net based on sections of wire.
        """
        split_on = [[Extractor.REPEATER], [Extractor.WIRE, Extractor.UP_VIA], [Extractor.WIRE, Extractor.DOWN_VIA]]
        replacements = [[Extractor.REPEATER], [Extractor.UP_VIA], [Extractor.DOWN_VIA]]
        prev = 0
        curr = 0

        result = []
        coords = []

        # Try to find the sequences in split_on, and then chunk them up
        while curr < len(extracted_net):
            found = False
            for candidate_split, replacement in zip(split_on, replacements):
                chunk_size = len(candidate_split)
                if extracted_net[curr:curr+chunk_size] == candidate_split:
                    # If it's empty, just skip it
                    if prev == curr:
                        curr += chunk_size
                        prev = curr
                        found = True
                        break

                    # Get the coordinates before and after this subsection (for repeaters)
                    before = start_coord if prev == 0 else net_coords[prev - 1]
                    after = net_coords[curr]

                    # Place the repeaters
                    repeated_subsection = self.place_repeaters(extracted_net[prev:curr], net_coords[prev:curr], before, after)
                    result.append(repeated_subsection)
                    coords.append(net_coords[prev:curr])

                    # Place the replacement section (using the coordinate of the first part)
                    result.append(replacement)
                    coords.append(net_coords[curr:curr+1])

                    # Update indices
                    curr += chunk_size
                    prev = curr

                    found = True
                    break

            if not found:
                curr += 1

        # Add the last section, unless it's empty (prev == curr)
        before = net_coords[prev - 1]
        result.append(self.place_repeaters(extracted_net[prev:curr], net_coords[prev:curr], before, stop_coord))
        coords.append(net_coords[prev:curr])

        return sum(result, []), sum(coords, [])

    def place_blocks(self, extracted_net, layout):
        """
        Modify layout to have the extracted net.
        """
        redstone_wire = block_names.index("redstone_wire")
        stone = block_names.index("stone")
        planks = block_names.index("planks")
        sticky_piston = block_names.index("sticky_piston")
        unpowered_repeater = block_names.index("unpowered_repeater")
        redstone_torch = block_names.index("redstone_torch")
        unlit_redstone_torch = block_names.index("unlit_redstone_torch")
        redstone_block = block_names.index("redstone_block")
        air = block_names.index("air")

        # For each of the types, place
        for extraction_type, placement in extracted_net:
            y, z, x = placement
            if extraction_type == Extractor.WIRE:
                layout[y  , z, x] = redstone_wire
                layout[y-1, z, x] = stone if y == 1 else planks
            elif extraction_type == Extractor.REPEATER:
                layout[y  , z, x] = unpowered_repeater
                layout[y-1, z, x] = stone if y == 1 else planks
            elif extraction_type == Extractor.UP_VIA:
                layout[y-1, z, x] = stone
                layout[y  , z, x] = stone
                layout[y+1, z, x] = redstone_torch
                layout[y+2, z, x] = planks
                layout[y+3, z, x] = unlit_redstone_torch
            elif extraction_type == Extractor.DOWN_VIA:
                layout[y  , z, x] = sticky_piston
                layout[y-1, z, x] = redstone_block
                layout[y-2, z, x] = air
                layout[y-3, z, x] = stone
            else:
                raise ValueError("Unknown extraction type", extraction_type)

    def extract_routing(self, routing):
        """
        Place the wires and vias specified by routing.
        """
        routing = deepcopy(routing)
        for net_name, d in routing.iteritems():
            for segment in d["segments"]:
                endpoints = segment["pins"]
                start_pin = endpoints[0]["pin_coord"]
                stop_pin = endpoints[1]["pin_coord"]

                extracted_net = self.extract_net_segment(segment, start_pin, stop_pin)
                segment["extracted_net"] = extracted_net

        return routing

    def extract_layout(self, extracted_routing, placed_layout):
        """
        Place the wires and vias specified by routing.
        """
        extracted_layout = np.copy(placed_layout)
        for net_name, d in extracted_routing.iteritems():
            for segment in d["segments"]:
                self.place_blocks(segment["extracted_net"], extracted_layout)

        return extracted_layout
