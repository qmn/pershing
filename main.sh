#!/bin/bash

EMPTY_WORLD=template_world

if [ "$1" = "" ]; then
	echo "Usage: $0 [input verilog]"
	exit
fi

BASE=$(basename -s .v $1)

# Determine result folder name
let i=1
while [ -d results/${BASE}_result_$i ]; do
	let i=$i+1
done
RESULT_DIR=results/${BASE}_result_$i
mkdir ${RESULT_DIR}

BLIF_FILE=${BASE}.blif

# Create the blif
./yosys.sh $1
mv ${BLIF_FILE} ${RESULT_DIR}

WORLD=result_world
# Create copy of world
rm -rf ${WORLD}
cp -r template_world ${WORLD}

./main.py -o ${RESULT_DIR} --world ${WORLD} ${RESULT_DIR}/${BLIF_FILE}
