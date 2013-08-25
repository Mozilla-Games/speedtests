#!/usr/bin/env python

import sys
import sets
import math
import getopt
import datetime
import argparse

import ConfigParser
import web
import json

import numpy
import scipy.stats

class DefaultConfigParser(ConfigParser.ConfigParser):
    def get_default(self, section, option, default, func='get'):
        try:
            return getattr(cfg, func)(section, option)
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            return default

def parse_range(l):
    result=set()
    for astr in l:
        for part in astr.split(','):
            x=part.split('-')
            result.update(range(int(x[0]),int(x[-1])+1))
    return sorted(result)

DEFAULT_CONF_FILE = 'speedtests_server.conf'
cfg = DefaultConfigParser()

cfg.read(DEFAULT_CONF_FILE)
DB_TYPE = cfg.get_default('server', 'db_type', 'sqlite')
DB_NAME = cfg.get_default('server', 'db_name', 'speedtests.sqlite')
DB_HOST = cfg.get_default('server', 'db_host', 'localhost')
DB_USER = cfg.get_default('server', 'db_user', 'speedtests')
DB_PASSWD = cfg.get_default('server', 'db_passwd', 'speedtests')

def main():
    if DB_TYPE is 'sqlite':
        dbargs = { 'dbn': DB_TYPE, 'db': DB_NAME }
    else:
        dbargs = { 'dbn': DB_TYPE, 'db': DB_NAME, 'db': DB_NAME,
                   'host': DB_HOST, 'user': DB_USER, 'pw': DB_PASSWD }
    db = web.database(**dbargs)

    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--client', dest='client', action='store', default=None,
                      help='target client to export', required=True)
    parser.add_argument('-p', '--platform', dest='platform', action='store', default=None,
                      help='target platform to export', required=True)
    parser.add_argument('-b', '--browser', dest='browsers', action='append', default=None,
                      help='browser name and (optional) version to export', required=True)
    parser.add_argument('benchmarks', action='append', default=None,
                      help='benchmarks to export')
    options = parser.parse_args()

    platform = options.platform
    client = options.client
    browsers = parse_range(options.browsers)
    benchmarks = options.benchmarks

    benchmark_data = {}
    browser_data = {}

    for benchmark in benchmarks:
        benchmark_data[benchmark] = {}
        for bid in browsers:
            entries = db.select(['browsers'], {'i':bid},
                                what='name, version, platform, arch',
                                where='id=$i')
            try:
                browser_data[bid] = dict(entries[0])
            except:
                print "Browser ID not found"
                raise

            result = None;

            entries = db.select(['runs'], {'c':client, 'b':benchmark, 'i':bid},
                                what='uuid',
                                where='client=$c AND bench_name=$b AND browser_id=$i',
                                order='start_time desc',
                                limit=1)

            try:
                result = dict(entries[0])
            except:
                print "No entries found!"
                raise

            iterations = db.select(['iterations'], {'u': result['uuid']},
                                   what='id',
                                   where='run_uuid=$u')
            result['scores'] = {}
            for i in iterations:
                iid = i['id']

                scores = db.select(['scores'], {'i':iid},
                                   what=('id, score, test_name, window_width, ' +
                                         'window_height, extra_data'),
                                   where='iteration_id=$i')
                for score in scores:
                    sname = score['test_name']
                    sid = score['id']
                    if not sname in result['scores']:
                        result['scores'][sname] = {}
                    result['scores'][sname][sid] = dict(score)

            benchmark_data[benchmark][bid] = result

    data = {'scores':benchmark_data, 'browsers':browser_data}

    #for bid, benches in data['scores'].items():
    #    for bench, results in benches.items():
    #        for subbench, iters in results['scores'].items():
    #            values = [i['score'] for i in iters.values()]
    #            avg = numpy.average(values)
    #            err = scipy.stats.sem(values)
    #            print subbench, 'avg:', avg, 'err:', err

    print json.dumps(data, indent=4)

main()
