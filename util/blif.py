
from __future__ import print_function

class BLIF:
    def __init__(self, model, inputs, outputs, clocks, cells, names):
        self.model = model
        self.inputs = inputs    # list of input nets (strings)
        self.outputs = outputs  # list of output nets (strings)
        self.clocks = clocks    # list of clocks (strings)
        self.cells = cells      # list of cells of {name: "", pins: ["", ...]}
        self.names = names      # list of names of {inputs: ["", ...], output: "", cover: ["", ]}

    def extract_subcircuit_nets(self):
        nets = set()

        # nets |= set(self.inputs)
        # nets |= set(self.outputs)
        # nets |= set(self.clocks)

        for cell in self.cells:
            for pin, net in cell["pins"].iteritems():
                nets.add(net)

        # for name in self.names:
        #     nets |= set(name["inputs"])
        #     nets |= set(name["output"])

        return nets


def load(f):
    """
    Reads in a BLIF file.
    """
    model = ""
    inputs = []
    outputs = []
    clocks = []
    cells = []
    names = []

    def get_next_whole_line():
        """
        get_next_whole_line reads in the full line, including any backslashes
        to indicate a continuation of the previous line.
        """
        line = ""

        # Skip blank lines and comment lines
        while True:
            line = f.readline()
            if line == "":
                return None

            line = line.strip()

            # Remove comments
            if "#" in line:
                comment_start = line.index("#")
                line = line[:comment_start]

            if line == "":
                continue

            break

        # Fully build the line, ignoring comments
        while "#" not in line[:-1] and line[-1] == "\\":
            line = line[:-1] + " " + f.readline().strip()

        # Remove comments
        if "#" in line:
            comment_start = line.index("#")
            line = line[:comment_start]

        return line

    line = "\n"
    reread = False
    while True:
        # Read in next line, if needed
        if reread:
            reread = False
            # keep previous line
        else:
            line = get_next_whole_line()
            if line is None:
                break

        # Tokenize line
        tokens = line.split()
        command = tokens[0]

        # Read in BLIF directives
        if command == ".model":
            model = tokens[1]

        elif command == ".inputs":
            inputs = tokens[1:]

        elif command == ".outputs":
            outputs = tokens[1:]

        elif command == ".clock":
            clocks = tokens[1:]

        elif command == ".names":
            names_inputs = tokens[1:-1]
            names_output = tokens[-1]
            names_single_output_cover = []
            new_line_seen = False

            # Read in the single-output-cover lines
            while not new_line_seen:
                line = get_next_whole_line()
                if line is None:
                    break

                tokens = line.split()
                command = tokens[0]
                if command[0] == ".":
                    new_line_seen = True
                else:
                    names_single_output_cover.append(line)

            names_dict = {"inputs": names_inputs,
                          "output": names_output,
                          "cover": names_single_output_cover}
            names.append(names_dict)
            reread = True

        elif command == ".subckt":
            subckt_name = tokens[1]
            subckt_connections = tokens[2:]
            subckt_pins = dict([c.split("=") for c in subckt_connections])
            subckt_dict = {"name": subckt_name,
                           "pins": subckt_pins}
            cells.append(subckt_dict)

        elif command == ".end":
            break

        else:
            raise ValueError("Unrecognized command {}".format(command))

    return BLIF(model, inputs, outputs, clocks, cells, names)
