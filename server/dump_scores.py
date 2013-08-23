#!/usr/bin/env python

import sys
import sets
import math
import getopt
import datetime

import ConfigParser
import web
import json

from matplotlib import rcParams
rcParams.update({'figure.autolayout': True})

import numpy
import scipy.stats

def usage():
    print "Usage: dump_scores.py -p <platform> -c <client> -b <browserid>,... <benchmark> ..."
    print ""
    print " -p <platform>       Which platform to construct plot for."
    print " -c <client>         Which client to construct plot for."
    print " -b ...              Comma separated list of browser ids to plot scores for."
    print " <benchmark> ...     The list of benchmarks to plot."

def pretty(d, indent=0):
    for key, value in d.iteritems():
        print '\t' * indent + str(key)
        if isinstance(value, dict):
            pretty(value, indent+1)
        else:
            print '\t' * (indent+1) + str(value)

class DefaultConfigParser(ConfigParser.ConfigParser):
    def get_default(self, section, option, default, func='get'):
        try:
            return getattr(cfg, func)(section, option)
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            return default

DEFAULT_CONF_FILE = 'speedtests_server.conf'
cfg = DefaultConfigParser()

cfg.read(DEFAULT_CONF_FILE)
DB_TYPE = cfg.get_default('server', 'db_type', 'sqlite')
DB_NAME = cfg.get_default('server', 'db_name', 'speedtests.sqlite')
DB_HOST = cfg.get_default('server', 'db_host', 'localhost')
DB_USER = cfg.get_default('server', 'db_user', 'speedtests')
DB_PASSWD = cfg.get_default('server', 'db_passwd', 'speedtests')

platform = None
client = None
benchmarks = None
browser_ids = None
def get_options(args):
    global platform
    global client
    global benchmarks
    global browser_ids
    optlist, args = getopt.getopt(args, "p:c:b:")
    for optpair in optlist:
        if optpair[0] == '-e':
            show_error = True
        if optpair[0] == '-o':
            outfile = optpair[1]
        if optpair[0] == '-p':
            platform = optpair[1]
        if optpair[0] == '-c':
            client = optpair[1]
        if optpair[0] == '-b':
            try:
                browser_ids = [int(x) for x in optpair[1].split(',')]
            except:
                raise Exception("Invalid browser ids: " + optpair[1])
    benchmarks = args

def main():
    if DB_TYPE is 'sqlite':
        dbargs = { 'dbn': DB_TYPE, 'db': DB_NAME }
    else:
        dbargs = { 'dbn': DB_TYPE, 'db': DB_NAME, 'db': DB_NAME,
                   'host': DB_HOST, 'user': DB_USER, 'pw': DB_PASSWD }
    db = web.database(**dbargs)

    get_options(sys.argv[1:])
    if not platform or not client or not benchmarks or not browser_ids:
        usage()
        exit(1)

    benchmark_data = {}
    browser_data = {}

    for benchmark in benchmarks:
        for bid in browser_ids:
            benchmark_data[bid] = {}
            entries = db.select(['browsers'], {'i':bid},
                                what='name, version, platform',
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

            benchmark_data[bid][benchmark] = result

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
