#!/usr/bin/env python

import sys
import json
import argparse

import google_auth
import numpy
import scipy.stats

def create_spreadsheet(data, out):
    for bid, benches in data['scores'].items():
        for bench, results in benches.items():
            print bid, bench
            for subbench, iters in results['scores'].items():
                values = [i['score'] for i in iters.values()]
                if len(values) > 1:
                    avg = numpy.average(values)
                    err = scipy.stats.sem(values)
                else:
                    avg = values[0]
                    err = None
                print subbench, 'avg:', avg, 'err:', err

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-o', '--out', dest='out', action='store', default=None,
                      help='output file name', required=True)
    options = parser.parse_args()

    create_spreadsheet(json.loads(sys.stdin.read()), options.out)