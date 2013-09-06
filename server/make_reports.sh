#!/bin/bash

FIREFOX_VERSIONS="23-26"
CHROME_VERSIONS="29-30"
SUFFIX=""

for PLATFORM in "Windows 7" "Linux" "Android"; do
  for BENCHMARK in "octane" "sunspider-1.0"; do
    if [ "$PLATFORM" = "Android" ]; then
      SUFFIX=" Mobile"
    fi
    python report.py -p "${PLATFORM}" -b "Firefox${SUFFIX}" "${FIREFOX_VERSIONS}" -b "Chrome${SUFFIX}" "${CHROME_VERSIONS}" -B "${BENCHMARK}"
  done
done