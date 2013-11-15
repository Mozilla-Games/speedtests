#!/bin/bash

for BENCHMARK in "octane" "sunspider-1.0" "kraken" "canvasmark"; do
  python report_xls.py -p "Windows 7" -b Firefox Chrome -B $BENCHMARK
  python report_xls.py -p "Linux" -b Firefox Chrome -B $BENCHMARK
  python report_xls.py -p "Android" "Firefox OS" -b Firefox Chrome -B $BENCHMARK
done