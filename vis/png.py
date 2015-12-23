from __future__ import print_function

from PIL import Image

from util import blocks

def blockid2texture(blockid):
    block_name = blocks.block_names[blockid]
    return lut[block_name]

def layout_to_png(layout, filename_base="layer", layers=None):
    image_width = 16 * layout.shape[2]
    image_height = 16 * layout.shape[1]

    prev_img = None

    if layers is None:
        layers = xrange(1, layout.shape[0] - 1)

    for y in layers:
        img = Image.new("RGBA", (image_width, image_height))
        for z in xrange(layout.shape[1]):
            for x in xrange(layout.shape[2]):
                img_x = x * 16
                img_y = z * 16
                tile = blockid2texture(layout[y, z, x])
                img.paste(tile, (img_x, img_y))

        if prev_img is not None:
            prev_img.paste(img, mask=img)
            img = prev_img.copy()

        img.save("{}_{}.png".format(filename_base, y))
        print("Wrote layer {}".format(y))
        prev_img = img

def extract_texture(coord):
    x, y = coord

    left = x * 16
    right = (x + 1) * 16
    top = y * 16
    bottom = (y + 1) * 16

    return textures.crop((left, top, right, bottom))

# Load in the textures and build the lookup table
texture_path = "/Users/qmn/Library/Application Support/minecraft/textures_0.png"
textures = Image.open(open(texture_path))

blank = Image.new("RGBA", (16, 16))

coords = {"stone": (20, 9),
          "redstone_wire": (18, 11),
          "redstone_torch": (19, 3),
          "unlit_redstone_torch": (19, 2),
          "unpowered_repeater": (19, 5),
          "powered_repeater": (19, 6),
          "unpowered_comparator": (1, 6),
          "powered_comparator": (2, 6)
         }

lut = {"air": blank}
for name, coord in coords.iteritems():
    lut[name] = extract_texture(coord)

