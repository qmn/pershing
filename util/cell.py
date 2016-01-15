from __future__ import print_function

import numpy as np

from blocks import block_names
from masked_subchunk import MaskedSubChunk

class Cell(MaskedSubChunk):
    """
    A Cell represents a part of a circuit that computes the value of a
    logic function.


    ports is a dict that maps pin names to the (y, z, x) coordinates in
    the blocks matrix.
    """
    def __init__(self, blocks, data, mask, name, ports, delay):
        super(Cell, self).__init__(blocks, data, mask)

        self.name = name
        self.ports = ports
        self.delay = delay

    def rot90(self, turns=1):
        """
        Rotates the cell and its ports in the counter-clockwise direction (As numpy
        does it.)
        """

        turns = turns % 4
        facing_arr = ["east", "north", "west", "south"]

        # Rotate the ports
        height, width, length = self.blocks.shape
        new_ports = {}
        for pin, d in self.ports.iteritems():
            (y, z, x) = d["coordinates"]

            # Compute new facing
            facing_i = facing_arr.index(d["facing"])
            new_facing_i = (facing_i + turns) % 4
            new_facing = facing_arr[new_facing_i]

            # Compute new coordinates
            ny = y
            if turns == 1:
                nz = length - 1 - x
                nx = z
            elif turns == 2:
                nz = width - z
                nx = length - x
            elif turns == 3:
                nz = x
                nx = width - 1 - z
            new_coordinates = (ny, nz, nx)

            new_ports[pin] = {"coordinates": new_coordinates,
                              "facing": new_facing,
                              "direction": d["direction"],
                              "level": d["level"]}

        new_msc = super(Cell, self).rot90(turns)
        new_blocks = new_msc.blocks
        new_data = new_msc.data
        new_mask = new_msc.mask

        # port_array = np.zeros_like(new_blocks)
        # for i, (y, z, x) in enumerate(new_ports.itervalues()):
        #     port_array[y, z, x] = i + 1

        # print(new_blocks)
        # print(port_array)

        return Cell(new_blocks, new_data, new_mask, self.name, new_ports, self.delay)

def from_lib(name, cell, pad=0):
    blocks = np.asarray(cell["blocks"], dtype=np.uint8)
    data = np.asarray(cell["data"], dtype=np.uint8)
    mask = np.full_like(blocks, True, dtype=np.bool)
    delay = cell["delay"]

    if pad != 0:
        pad_out = (pad,)
        blocks = np.pad(blocks, pad_out, "constant")
        data = np.pad(data, pad_out, "constant")
        mask = np.pad(mask, pad_out, "constant")

    # build ports
    ports = {}
    for pin, d in cell["pins"].iteritems():
        y, z, x = d["coordinates"]
        coord = (y + pad, z + pad, x + pad)
        facing = d["facing"]
        direction = d["direction"]
        level = d["level"]
        ports[pin] = {"coordinates": coord,
                      "facing": facing,
                      "direction": direction,
                      "level": level}

    return Cell(blocks, data, mask, name, ports, delay)
