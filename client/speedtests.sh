#!/bin/bash

LOOP_TIME=3600

while True
do
    start=`date +%s`
    echo python speedtests.py
    sleep 10
    end=`date +%s`
    sleeptime=$((LOOP_TIME - $((end-start))))
    if [ $sleeptime -gt 0 ]
    then
        sleep $sleeptime
    fi
done