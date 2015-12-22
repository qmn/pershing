# List of all block IDs in Minecraft, taken from
# http://minecraft.gamepedia.com/Data_values/Block_IDs
block_names = [
    "air",
    "stone",
    "grass",
    "dirt",
    "cobblestone",
    "planks",
    "sapling",
    "bedrock",
    "flowing_water",
    "water",
    "flowing_lava",
    "lava",
    "sand",
    "gravel",
    "gold_ore",
    "iron_ore",
    "coal_ore",
    "log",
    "leaves",
    "sponge",
    "glass",
    "lapis_ore",
    "lapis_block",
    "dispenser",
    "sandstone",
    "noteblock",
    "bed",
    "golden_rail",
    "detector_rail",
    "sticky_piston",
    "web",
    "tallgrass",
    "deadbush",
    "piston",
    "piston_head",
    "wool",
    "piston_extension",
    "yellow_flower",
    "red_flower",
    "brown_mushroom",
    "red_mushroom",
    "gold_block",
    "iron_block",
    "double_stone_slab",
    "stone_slab",
    "brick_block",
    "tnt",
    "bookshelf",
    "mossy_cobblestone",
    "obsidian",
    "torch",
    "fire",
    "mob_spawner",
    "oak_stairs",
    "chest",
    "redstone_wire",
    "diamond_ore",
    "diamond_block",
    "crafting_table",
    "wheat",
    "farmland",
    "furnace",
    "lit_furnace",
    "standing_sign",
    "wooden_door",
    "ladder",
    "rail",
    "stone_stairs",
    "wall_sign",
    "lever",
    "stone_pressure_plate",
    "iron_door",
    "wooden_pressure_plate",
    "redstone_ore",
    "lit_redstone_ore",
    "unlit_redstone_torch",
    "redstone_torch",
    "stone_button",
    "snow_layer",
    "ice",
    "snow",
    "cactus",
    "clay",
    "reeds",
    "jukebox",
    "fence",
    "pumpkin",
    "netherrack",
    "soul_sand",
    "glowstone",
    "portal",
    "lit_pumpkin",
    "cake",
    "unpowered_repeater",
    "powered_repeater",
    "stained_glass",
    "trapdoor",
    "monster_egg",
    "stonebrick",
    "brown_mushroom_block",
    "red_mushroom_block",
    "iron_bars",
    "glass_pane",
    "melon_block",
    "pumpkin_stem",
    "melon_stem",
    "vine",
    "fence_gate",
    "brick_stairs",
    "stone_brick_stairs",
    "mycelium",
    "waterlily",
    "nethre_brick",
    "nether_brick_fence",
    "nether_brick_stairs",
    "nether_wart",
    "enchanting_table",
    "brewing_stand",
    "cauldron",
    "end_portal",
    "end_portal_frame",
    "end_stone",
    "dragon_egg",
    "redstone_lamp",
    "lit_redstone_lamp",
    "double_wooden_slab",
    "wooden_slab",
    "cocoa",
    "sandstone_stairs",
    "emerald_ore",
    "ender_chest",
    "tripwire_hook",
    "tripwire",
    "emerald_block",
    "spruce_stairs",
    "birch_stairs",
    "jungle_stairs",
    "command_block",
    "beacon",
    "cobblestone_wall",
    "flower_pot",
    "carrots",
    "potatoes",
    "wooden_button",
    "skull",
    "anvil",
    "trapped_chest",
    "light_weighted_pressure_plate",
    "heavy_weighted_pressure_plate",
    "unpowered_comparator",
    "powered_comparator",
    "daylight_detector",
    "redstone_block",
    "quartz_ore",
    "hopper",
    "quartz_block",
    "quartz_stairs",
    "activator_rail",
    "dropper",
    "stained_hardened_clay",
    "stained_glass_pane",
    "leaves2",
    "log2",
    "acacia_stairs",
    "dark_oak_stairs",
    "slime",
    "barrier",
    "iron_trapdoor",
    "prismarine",
    "sea_lantern",
    "hay_block",
    "carpet",
    "hardened_clay",
    "coal_block",
    "packed_ice",
    "double_plant",
    "standing_banner",
    "wall_banner",
    "daylight_detector_inverted",
    "red_sandstone",
    "red_sandstone_stairs",
    "double_stone_slab2",
    "stone_slab2",
    "spruce_fence_gate",
    "birch_fence_gate",
    "jungle_fence_gate",
    "dark_oak_fence_gate",
    "acacia_fence_gate",
    "spruce_fence",
    "birch_fence",
    "jungle_fence",
    "dark_oak_fence",
    "acacia_fence",
    "spruce_door",
    "birch_door",
    "jungle_door",
    "acacia_door",
    "dark_oak_door",
    "end_rod",
    "chorus_plant",
    "chorus_flower",
    "purpur_block",
    "purpur_pillar",
    "purpur_stairs",
    "purpur_double_slab",
    "purpur_slab",
    "end_bricks",
    "beetroots",
    "grass_path",
    "end_gateway",
    "repeating_command_block",
    "chain_command_block",
    "frosted_ice"
]

class Torch:
    EAST = 1
    WEST = 2
    SOUTH = 3
    NORTH = 4
    UP = 5
    rotations = [NORTH, WEST, SOUTH, EAST]

    @staticmethod
    def rot90(data, turns=1):
        """
        Given the current data, deterime the new data value based on the
        number of rotations given by turns.
        """
        if data == Torch.UP:
            return Torch.UP

        if data not in Torch.rotations:
            raise ValueError("Torch data ({}) is not valid".format(data))

        rot_index = Torch.rotations.index(data)
        new_rot = (rot_index + turns) % len(Torch.rotations)
        return Torch.rotations[new_rot]

class Repeater:
    NORTH = 0
    EAST = 1
    SOUTH = 2
    WEST = 3
    rotations = [NORTH, WEST, SOUTH, EAST]

    @staticmethod
    def rot90(data, turns=1):
        """
        Given the current data, deterime the new data value based on the
        number of rotations given by turns.
        """
        rot_bits = data & 0x3
        delay_bits = data & 0xc

        if rot_bits not in Repeater.rotations:
            raise ValueError("Repeater data ({}) is not valid".format(data))

        rot_index = Repeater.rotations.index(rot_bits)
        new_rot = (rot_index + turns) % len(Repeater.rotations)
        new_rot_bits = Repeater.rotations[new_rot] & 0x3
        return (delay_bits | rot_bits)

class Comparator:
    NORTH = 0
    EAST = 1
    SOUTH = 2
    WEST = 3
    rotations = [NORTH, WEST, SOUTH, EAST]

    @staticmethod
    def rot90(data, turns=1):
        """
        Given the current data, deterime the new data value based on the
        number of rotations given by turns.
        """
        rot_bits = data & 0x3
        other_bits = data & 0xc

        if rot_bits not in Comparator.rotations:
            raise ValueError("Repeater data ({}) is not valid".format(data))

        rot_index = Comparator.rotations.index(rot_bits)
        new_rot = (rot_index + turns) % len(Comparator.rotations)
        new_rot_bits = Comparator.rotations[new_rot] & 0x3
        return (other_bits | rot_bits)
