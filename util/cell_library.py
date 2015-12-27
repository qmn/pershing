from __future__ import print_function

import yaml
from util.cell import from_lib

class CellLibrary:
    def __init__(self, cells):
        self.cells = cells

def load(f):
    """
    Loads a YAML file containing standard cell library information.
    """
    d = yaml.load(f)

    library_name = d["library_name"]
    print("Loaded library:", library_name)

    cells = d["cells"]
    print("Library contains {} cells".format(len(cells)))

    return CellLibrary(cells)

def pregenerate_cells(cell_library):
    """
    Generates each cell and each of its four (yaw) rotations.

    The returned dictionary is indexed by the cell name (e.g., "AND")
    and then by the rotation (0-3).
    """
    cells = {}
    for cell_name, cell_data in cell_library.cells.iteritems():
        # Generate first cell
        cell_rot0 = from_lib(cell_name, cell_data)

        # Generate all four rotations
        cell_rot1 = cell_rot0.rot90()
        cell_rot2 = cell_rot1.rot90()
        cell_rot3 = cell_rot2.rot90()

        cells[cell_name] = [cell_rot0, cell_rot1, cell_rot2, cell_rot3]

    return cells

