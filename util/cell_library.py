from __future__ import print_function

import yaml

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
