from __future__ import print_function

from extractor import Extractor

class MineTime:
    def compute_net_delay(self, extracted_net):
        total = 0
        for extraction_type, _ in extracted_net:
            if extraction_type == Extractor.WIRE:
                continue
            elif extraction_type == Extractor.REPEATER:
                total += 1
            elif extraction_type == Extractor.UP_VIA:
                total += 2
            elif extraction_type == Extractor.DOWN_VIA:
                total += 2
            else:
                raise ValueError("Unknown extraction type", extraction_type)
        return total

    def compute_combinational_delay(self, placements, routing, cell_library):
        # For each input or sequential unit output,
        # find the longest delay to the output or to another sequential unit's input
        driver_names = ["input_pin", "DFF"]
        driver_indices = [i for i, placement in enumerate(placements) if placement["name"] in driver_names]

        driven_names = ["DFF", "output_pin"]
        driven_indices = [i for i, placement in enumerate(placements) if placement["name"] in driven_names]

        def get_cell_outputs(cell_name):
            output_names = []
            for pin_name, pin_dict in cell_library.cells[cell_name]["pins"].iteritems():
                if pin_dict["direction"] == "output":
                    output_names.append(pin_name)
            return output_names

        def get_segments(net_name, cell_index):
            """
            Get the segments of this net driven by this cell.
            """
            net_segments = routing[net_name]["segments"]
            driven_segments = [segment for segment in net_segments if segment["pins"][0]["cell_index"] == cell_index]
            return driven_segments

        def dfs(driver_index, visited=[]):
            visited.append(driver_index)

            to_explore = [([driver_index], 0, [])]
            completed = []

            while len(to_explore) > 0:
                explore_list, delay, path = to_explore.pop()
                driver = explore_list[-1]

                # Compute delays pertaining to this cell
                cell = placements[driver]
                cell_name = cell["name"]
                delay_dict = cell_library.cells[cell_name]["delay"]

                if "combinational" in delay_dict:
                    cell_delay = delay_dict["combinational"]
                else:
                    cell_delay = 0

                if driver in driven_indices or driver in explore_list[:-1]:
                    # done
                    completed.append((delay, path + [cell_name]))
                    continue

                # Iterate over the outputs to see which cells are being
                # driven by this cell
                outputs = get_cell_outputs(cell_name)
                for output in outputs:
                    driven_net = cell["pins"][output]

                    indices_along_net = [driver]

                    while len(indices_along_net) > 0:
                        temp_driver = indices_along_net.pop()
                        for segment in get_segments(driven_net, temp_driver):
                            segment_delay = self.compute_net_delay(segment["extracted_net"])
                            cumulative_delay = delay + cell_delay + segment_delay

                            # also see other nets driven by this one
                            driven_cell_index = segment["pins"][1]["cell_index"]
                            indices_along_net.append(driven_cell_index)

                            new_exploration = (explore_list[:] + [driven_cell_index], cumulative_delay, path[:] + [cell_name, driven_net])
                            to_explore.append(new_exploration)

            return completed

        return sum([dfs(driver_index) for driver_index in driver_indices], [])
