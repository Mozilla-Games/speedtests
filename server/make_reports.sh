#!/bin/bash

for PLATFORM in "Windows 7" "Linux" "Android"; do
  for BENCHMARK in "octane" "sunspider-1.0" "kraken" "canvasmark"; do
    python report_xls.py -p "$PLATFORM" -b Firefox Chrome -B $BENCHMARK
  done
done
