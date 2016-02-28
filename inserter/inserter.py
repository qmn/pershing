from __future__ import print_function

import sys

from util.blocks import block_names

from nbt import nbt, region, chunk

class Region:
    """Convenience class for achieving some MPRT tasks."""
    def __init__(self, region):
        self.region = region
        self.chunks = {}

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        # Writing the affected chunks
        for k, v in self.chunks.iteritems():
            (chunk_x, chunk_z) = k
            self.region.write_chunk(chunk_x, chunk_z, v)

    def get_chunk(self, chunk_x, chunk_z):
        key = (chunk_x, chunk_z)
        if not key in self.chunks:
            try:
                self.chunks[key] = self.region.get_chunk(chunk_x, chunk_z)
            except region.InconceivedChunk:
                # create the chunk
                new_chunk = nbt.NBTFile()
                level_tag = nbt.TAG_Compound()
                level_tag.name = "Level"
                level_tag.tags.append(nbt.TAG_Int(name="xPos", value=chunk_x*32))
                level_tag.tags.append(nbt.TAG_Int(name="zPos", value=chunk_z*32))
                level_tag.tags.append(nbt.TAG_List(name="Sections", type=nbt.TAG_Compound))
                new_chunk.tags.append(level_tag)
                self.chunks[key] = new_chunk

        return self.chunks[key]

    def set_chunk(self, chunk_x, chunk_z, chunk):
        key = (chunk_x, chunk_z)
        # If we don't have the chunk in this wrapper, load it
        if key not in self.chunks:
            get_chunk(chunk_x, chunk_z)
        self.chunks[key] = chunk

    def create_empty_section(self, section_y):
        new_section = nbt.TAG_Compound()

        data = nbt.TAG_Byte_Array(u"Data")
        skylight = nbt.TAG_Byte_Array(u"SkyLight")
        blocklight = nbt.TAG_Byte_Array(u"BlockLight")
        y = nbt.TAG_Byte()
        blocks = nbt.TAG_Byte_Array(u"Blocks")

        # TAG_Byte_Array(u'Data'): [2048 byte(s)]
        # TAG_Byte_Array(u'SkyLight'): [2048 byte(s)]
        # TAG_Byte_Array(u'BlockLight'): [2048 byte(s)]
        # TAG_Byte(u'Y'): 0
        # TAG_Byte_Array(u'Blocks'): [4096 byte(s)]

        data.value = bytearray(2048)
        skylight.value = bytearray(2048)
        blocklight.value = bytearray(2048)
        y.name = u"Y"
        y.value = section_y
        blocks.value = bytearray(4096)

        new_section.tags.extend([data, skylight, blocklight, y, blocks])
        return new_section

    def create_section(self, section_y, chunk_x, chunk_z):
        """
        Creates a new section y in chunk (x, z).
        """
        new_section = self.create_empty_section(section_y)
        chunk = self.get_chunk(chunk_x, chunk_z)
        chunk["Level"]["Sections"].append(new_section)

        return new_section

    def get_section(self, section_y, chunk_x, chunk_z):
        """
        Gets the section y in chunk (x, z).
        """
        chunk = self.get_chunk(chunk_x, chunk_z)
        for section in chunk["Level"]["Sections"]:
            if section["Y"].value == section_y:
                return section
        return None

    def set_section(self, y, chunk_x, chunk_z, section):
        chunk = self.get_chunk(chunk_x, chunk_z)
        old_section = self.get_section(y, chunk_x, chunk_z)
        if old_section:
            chunk["Level"]["Sections"].remove(old_section)
        chunk["Level"]["Sections"].append(section)

    def set_block(self, x, y, z, id):
        """
        Sets the region-relative coordinate (x, y, z) to block id.
        """
        chunk_x, offset_x = divmod(x, 16)
        section_y, offset_y = divmod(y, 16)
        chunk_z, offset_z = divmod(z, 16)

        section = self.get_section(section_y, chunk_x, chunk_z)
        if not section:
            section = self.create_section(section_y, chunk_x, chunk_z)

        block_position = (offset_y * 16 * 16) + (offset_z * 16) + offset_x

        section["Blocks"][block_position] = id

    def get_block(self, x, y, z):
        chunk_x, offset_x = divmod(x, 16)
        section_y, offset_y = divmod(y, 16)
        chunk_z, offset_z = divmod(z, 16)

        section = self.get_section(section_y, chunk_x, chunk_z)
        if not section:
            section = self.create_section(section_y, chunk_x, chunk_z)

        block_position = (offset_y * 16 * 16) + (offset_z * 16) + offset_x

        return section["Blocks"][block_position]

    def set_section_blocks(self, section_y, chunk_x, chunk_z, blocks):
        section = self.get_section(section_y, chunk_x, chunk_z)
        if not section:
            section = self.create_section(section_y, chunk_x, chunk_z)

        section["Blocks"].value = bytearray(blocks)

    def set_redstone(self, x, y, z):
        """Sets a redstone dust piece above the block noted."""
        self.set_block(x, y+1, z, 55)

    def set_data(self, x, y, z, data):
        chunk_x, offset_x = divmod(x, 16)
        section_y, offset_y = divmod(y, 16)
        chunk_z, offset_z = divmod(z, 16)

        section = self.get_section(section_y, chunk_x, chunk_z)
        if not section:
            section = self.create_section(section_y, chunk_x, chunk_z)

        block_position = (offset_y * 16 * 16) + (offset_z * 16) + offset_x

        pos, off = divmod(block_position, 2)

        data_byte = section["Data"].value[pos]

        data_nibble = data & 0xF
        if off == 1:
            data_byte = data_byte & 0xF | data_nibble << 4
        else:
            data_byte = data_byte & 0xF0 | data_nibble

        section["Data"].value[pos] = data_byte

def place_block(world, y, z, x, i):
    region_x, offset_x = divmod(x, 32*16)
    region_z, offset_z = divmod(z, 32*16)

    with Region(world.get_region(region_x, region_z)) as region:
        region.set_block(offset_x, y, offset_z, i)

def insert_extracted_layout(world, extracted_layout, offset=(0, 0, 0)):
    """
    Places the extracted layout at offset (y, z, x) in the world.
    """
    
    len_z = extracted_layout.shape[1]
    len_x = extracted_layout.shape[2]
    start_y, start_z, start_x = offset

    height, width, length = extracted_layout.shape
    count = 0

    # place base
    for z in xrange(width):
        for x in xrange(length):
            place_block(world, start_y - 1, z, x, block_names.index("dirt"))

    for yy in xrange(height):
        for zz in xrange(width):
            for xx in xrange(length):
                block = extracted_layout[yy, zz, xx]

                if block == 0:
                    continue

                y = start_y + yy
                z = start_z + zz
                x = start_x + xx
                place_block(world, y, z, x, block)
                count += 1
                msg = "Wrote {} blocks to Minecraft world".format(count)
                sys.stdout.write("\b" * len(msg))
                sys.stdout.write(msg)
                sys.stdout.flush()
    
    sys.stdout.write(" ... done.\n")
    sys.stdout.flush()

