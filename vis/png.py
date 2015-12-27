from __future__ import print_function

import random

from PIL import Image, ImageDraw

from util import blocks

def blockid2texture(blockid):
    block_name = blocks.block_names[blockid]
    return lut[block_name]

def layout_to_composite(layout, layers=None):
    img = None
    
    if layers is None:
        layers = xrange(layout.shape[0])

    for y in layers:
        new_img = layer_to_img(layout, y)
        # img.save("{}_{}.png".format(filename_base, y))
        # print("Wrote layer {}".format(y))

        if img is None:
            img = new_img
        else:
            img.paste(new_img, mask=new_img)

    return img

def random_color():
    r = random.randint(0, 255)
    g = random.randint(0, 255)
    b = random.randint(0, 255)
    return "#{:02x}{:02x}{:02x}".format(r, g, b)

def nets_to_png(layout, nets, filename_base="nets", layers=None):
    img = layout_to_composite(layout, layers)
    draw = ImageDraw.Draw(img)

    for name, net in nets.iteritems():
        color = random_color()
        for u, v in net:
            (_, uz, ux), (_, vz, vx) = u, v
            x1 = (ux * 16) + 8
            y1 = (uz * 16) + 8
            x2 = (vx * 16) + 8
            y2 = (vz * 16) + 8
            draw.line((x1, y1, x2, y2), fill=color, width=3)

    full_name = filename_base + ".png"
    img.save(full_name)
    print("Image written to", full_name)

def layout_to_png(layout, filename_base="composite", layers=None):
    img = layout_to_composite(layout, layers)
    full_name = filename_base + ".png"
    img.save(full_name)
    print("Image written to", full_name)

def layer_to_img(layout, y):
    image_width = 16 * layout.shape[2]
    image_height = 16 * layout.shape[1]

    img = Image.new("RGBA", (image_width, image_height))
    for z in xrange(layout.shape[1]):
        for x in xrange(layout.shape[2]):
            img_x = x * 16
            img_y = z * 16
            tile = blockid2texture(layout[y, z, x])
            img.paste(tile, (img_x, img_y))

    return img

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

