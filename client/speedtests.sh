#!/bin/bash

LOOP_TIME=3600

while True
do
    start=`date +%s`
    python speedtests.py
    end=`date +%s`
    sleeptime=$((LOOP_TIME - $((end-start))))
    if [ $sleeptime -gt 0 ]
    then
        sleep $sleeptime
    fi
done