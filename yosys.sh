#!/bin/bash

LIBRARY=lib/quan.lib

if [ "$1" = "" ]; then
	echo "Usage: $0 [input verilog] [library file]"
	echo "  (library file is ${LIBRARY} unless specified)"
	exit
fi

if [ "$2" != "" ]; then
	LIBRARY=$2
fi

OUTFILE=$(basename -s .v $1).blif

yosys -p "read_verilog $1;
hierarchy -check -auto-top;
proc; opt; fsm; opt; memory; opt;
techmap; opt; dfflibmap -liberty ${LIBRARY};
abc -liberty ${LIBRARY};
clean; write_blif ${OUTFILE}"

