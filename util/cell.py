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
    def __init__(self, blocks, data, mask, name, ports):
        super(Cell, self).__init__(blocks, data, mask)

        self.name = name
        self.ports = ports

    def rot90(self, turns=1):
        """
        Rotates the cell and its ports in the counter-clockwise direction (As numpy
        does it.)
        """
        
        # Rotate the ports
        height, width, length = self.blocks.shape
        new_ports = {}
        for pin, (y, z, x) in self.ports.iteritems():
            ny = y
            nz = length - 1 - x
            nx = width - 1 - z
            new_ports[pin] = (ny, nz, nx)

        new_msc = super(Cell, self).rot90(turns)
        new_blocks = new_msc.blocks
        new_data = new_msc.data
        new_mask = new_msc.mask

        return Cell(new_blocks, new_data, new_mask, self.name, new_ports)

def from_lib(name, cell, pad=0):
    blocks = np.asarray(cell["blocks"], dtype=np.int8)
    data = np.asarray(cell["data"], dtype=np.int8)
    mask = np.full_like(blocks, True, dtype=np.bool)

    if pad != 0:
        pad_out = (pad,)
        blocks = np.pad(blocks, pad_out, "constant")
        data = np.pad(data, pad_out, "constant")
        mask = np.pad(mask, pad_out, "constant")

    # build ports
    ports = {}
    for pin, d in cell["pins"].iteritems():
        y, z, x = d["coordinates"]
        ports[pin] = (y + pad, z + pad, x + pad)

    return Cell(blocks, data, mask, name, ports)
