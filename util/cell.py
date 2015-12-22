from __future__ import print_function

import numpy as np

from blocks import block_names
from masked_subchunk import MaskedSubChunk

class Cell(MaskedSubChunk):
    """
    A Cell represents a part of a circuit that computes the value of a
    logic function.


    ports is a 3D matrix that matches the dimensions of blocks which contains
    strings corresponding to port input names.
    """
    def __init__(self, blocks, data, mask, name, ports):
        super(Cell, self).__init__(blocks, data, mask)

        self.name = name

        ports = np.asarray(ports, dtype=np.str)
        if self.blocks.shape != ports.shape:
            raise ValueError("Blocks shape does not match ports shape: {} != {}".format(self.blocks.shape, ports.shape))

        self.ports = ports

    def rot90(self, turns=1):
        """
        Rotates the cell and its ports in the counter-clockwise direction (As numpy
        does it.)
        """
        
        # Rotate the ports
        new_ports = np.array([np.rot90(py, turns) for py in self.ports])

        new_msc = super(Cell, self).rot90(turns)
        new_blocks = new_msc.blocks
        new_data = new_msc.data
        new_mask = new_msc.mask

        return Cell(new_blocks, new_data, new_mask, self.name, new_ports)

def from_lib(name, cell):
    blocks = np.asarray(cell["blocks"], dtype=np.int8)
    data = np.asarray(cell["data"], dtype=np.int8)
    mask = np.full_like(blocks, True, dtype=np.bool)

    # build ports
    try:
        ports = np.full_like(blocks, "", dtype=object)
        for pin, d in cell["pins"].iteritems():
            y, z, x = d["coordinates"]
            ports[y, z, x] = pin
    except IndexError:
        print("Cell name:", name)
        print("Cell data:", cell)
        print("Faulty coordinates:", d["coordinates"])
        raise

    return Cell(blocks, data, mask, name, ports)
