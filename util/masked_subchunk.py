from __future__ import print_function

import numpy as np
import blocks

class MaskedSubChunk(object):
    """
    A MaskedSubChunk stores blocks and their associated data values, but
    only for certain locations (the mask). There must be three dimensions
    for these values.

    The mask is a three-dimensional matrix of Boolean values specifying
    whether the block is to be placed or not. That is, True places the
    block, False does not.

    Dimensions are organized (Y, Z, X).
    """
    def __init__(self, blocks, data, mask):
        blocks = np.asarray(blocks, dtype=np.int8)
        data = np.asarray(data, dtype=np.int8)
        mask = np.asarray(mask, dtype=np.bool)

        if blocks.shape != data.shape:
            raise ValueError("Blocks shape does not match data shape: {} != {}".format(blocks.shape, data.shape))
        if blocks.shape != mask.shape:
            raise ValueError("Blocks shape does not match mask shape: {} != {}".format(blocks.shape, mask.shape))

        self.blocks = blocks
        self.data = data
        self.mask = mask

    def render_all(self):
        """
        Iterates through ((y, z, x), block id, block data) values of this
        MaskedSubChunk.
        """
        for y in xrange(self.blocks.shape[0]):
            for z in xrange(self.blocks.shape[1]):
                for x in xrange(self.blocks.shape[2]):
                    block_coords = (y, z, x)
                    block_mask = self.mask[block_coords]

                    # Do we place the block?
                    if block_mask:
                        block_id = self.blocks[block_coords]
                        block_data = self.data[block_coords]
                        yield (block_coords, block_id, block_data)

    def rot90(self, turns=1):
        """
        Rotates the blocks in the counter-clockwise direction. (As numpy
        does it.)
        """
        # Rotate the individual Y-layer matrices
        new_blocks = np.array([np.rot90(by, turns) for by in self.blocks])
        new_data = np.array([np.rot90(dy, turns) for dy in self.data])
        new_mask = np.array([np.rot90(my, turns) for my in self.mask])

        # Rotate the data (if applicable)
        for y in xrange(new_data.shape[0]):
            for z in xrange(new_data.shape[1]):
                for x in xrange(new_data.shape[2]):
                    b = new_blocks[y, z, x]
                    d = new_data[y, z, x]
                    new_data[y, z, x] = self.data_rot90(b, d, turns)

        return MaskedSubChunk(new_blocks, new_data, new_mask)

    def data_rot90(self, block, data, turns):
        """
        Specially rotate this block, which has an orientation that depends on
        the data value.
        """
        blockname = blocks.block_names[block]

        # Torches (redstone and normal)
        torches = ["redstone_torch", "unlit_redstone_torch", "torch"]
        if blockname in torches:
            return blocks.Torch.rot90(data, turns)

        # Repeaters
        repeaters = ["unpowered_repeater", "powered_repeater"]
        if blockname in repeaters:
            return blocks.Repeater.rot90(data, turns)

        # Comparators
        comparators = ["unpowered_comparator", "powered_comparator"]
        if blockname in comparators:
            return blocks.Comparator.rot90(data, turns)

        return data
