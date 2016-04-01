PlacE RedStone Hardware IN Game (PERSHING)
==========================================
PERSHING (formerly called MPRT) accepts Berkeley Logic Interchange Files
(BLIFs) and produces a compacted layout of logic cells and the redstone wire
connections needed to produce a functioning circuit in Minecraft.

		       Verilog file (*.v)
			       |
			       |  yosys (not this repo)
			       V
		       BLIF file (*.blif)
			       |
		               |  PERSHING (this repo)
			       V
		 Fully placed-and-routed layout
			       |
		               |  inserter.py (this repo too)
			       V
			   Minecraft

Combined with a synthesis tool like Yosys, PERSHING can accept Verilog and
produce functional circuits, paving the way for vastly more complex circuits
than can be manually laid by hand.

Requirements
------------
- Yosys (or another way to create BLIFs)
- Python 2.7
- NBT

Setup
-----
To read/write Minecraft worlds, we use the [NBT package](https://github.com/twoolie/NBT).
Initialize it with the `git submodule` command.

	$ git submodule update --init

You must also already have `yosys` installed.

Usage
-----
The easiest way to use PERSHING is to use the convenience script `main.sh`:

	$ ./main.sh <input Verilog file>

Advanced Users
--------------
For finer-grained control, including resuming partial runs, execute `main.py`
at the command line. Below is the help text:

	main.py [-h] [-o output_directory] [--library library_file]
	    [--placements placements_file] [--routings routings_file]
	    [--world world_folder]
	    <input BLIF file>

To generate BLIF files (using Yosys), run `yosys.sh`:

	$ ./yosys.sh <input Verilog file>

The resulting BLIF file is the name of the Verilog file without the suffix, and
with `.blif` added. Then, to run PERSHING, use:

	$ ./main.py <output blif file>

Why is it called PERSHING?
--------------------------
The [MGM-31A Pershing ballistic missle system](https://en.wikipedia.org/wiki/MGM-31_Pershing)
succeeded the United States' Redstone ballistic missle system in the 1960s. In a
project involving Redstone, "Pershing" sounds pretty cool.

Other Notes
-----------
A publication resulting from the creation of this project appeared at the first
annual conference on TBD ([SIGTBD](http://sigtbd.csail.mit.edu/)), a joke
conference at MIT.
