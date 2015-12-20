from __future__ import print_function

import numpy as np

class MaskedSubChunk:
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

    def rotate(self, turns=1):
        """
        Rotates the blocks in the counter-clockwise direction. (As numpy
        does it.)
        """
        new_blocks = np.array([np.rot90(by, turns) for by in self.blocks])
        new_data = np.array([np.rot90(dy, turns) for dy in self.data])
        new_mask = np.array([np.rot90(my, turns) for my in self.mask])

        return MaskedSubChunk(new_blocks, new_data, new_mask)
