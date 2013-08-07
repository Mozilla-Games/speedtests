#!/usr/bin/env python

import sys
import sets
import math
import getopt
import datetime

import numpy as np
import matplotlib.pyplot as plt

import ConfigParser
import web

from matplotlib import rcParams
rcParams.update({'figure.autolayout': True})

def usage():
    print "Usage: chart.py [-o <out>] [-e] -p <platform> -c <client> "
    print "                -b <browserid>,... <benchmark> ..."
    print ""
    print " -o <out>            The output file."
    print " -e                  Whether to include error bars or not."
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

if DB_TYPE is 'sqlite':
    dbargs = { 'dbn': DB_TYPE, 'db': DB_NAME }
else:
    dbargs = { 'dbn': DB_TYPE, 'db': DB_NAME, 'db': DB_NAME, 'host': DB_HOST, 'user': DB_USER, 'pw': DB_PASSWD }
db = web.database(**dbargs)

# let's just make things work if the db is empty
try:
    db.query('SELECT COUNT(*) FROM browsers')
except:
    schema_lines = "".join(open("schema.sql", "r").readlines()).split(";")
    cursor = db.ctx.db.cursor()
    for line in schema_lines:
        cursor.execute(line)
    db.ctx.db.commit()
    cursor.close()
    print "Initialized empty sqlite database."

try:
    db.query('SELECT COUNT(*) FROM browsers')
except:
    print "Tried to initialize empty database, but failed!"
    raise

# TODO: load these from options, scores from db
outfile = None
platform = None
client = None
benchmarks = None
browser_ids = None
show_error = None

def get_options(args):
    global platform
    global client
    global benchmarks
    global browser_ids
    global outfile
    global show_error
    optlist, args = getopt.getopt(args, "o:p:c:b:e")
    print "%s, %s" % (optlist, args)
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
                pass
    benchmarks = args

def annotate_datetime(filename):
    dt = datetime.datetime.now()
    return '%04d-%02d-%02d-%s' % (dt.year, dt.month, dt.day, filename)

get_options(sys.argv[1:])
if not platform or not client or not benchmarks or not browser_ids:
    usage()
    exit(1)

if not outfile:
    outfile = "plot.png"
outfile = annotate_datetime(outfile)

benchmark_data = {}
browser_data = {}

for benchmark in benchmarks:
  for bid in browser_ids:
    benchmark_data[bid] = {}
    vars = {
      'i': bid
    }
    entries = db.select(['browsers'], vars, what='name, version, platform', where='id=$i')
    try:
      browser_data[bid] = dict(entries[0])
    except:
      print "Browser ID not found"
      raise

    result = None;

    vars = {
      'c': client,
      'b': benchmark,
      'i': bid
    }
    entries = db.select(['runs'], vars, what='uuid', where='client=$c AND bench_name=$b AND browser_id=$i', order='start_time desc', limit=1)
    try:
      result = dict(entries[0])
    except:
      print "No entries found!"
      raise

    vars = {
      'u': result['uuid']
    }
    iterations = db.select(['iterations'], vars, what='id', where='run_uuid=$u')
    result['scores'] = {}
    for i in iterations:
      iid = i['id']

      vars = {
        'i': iid
      }
      scores = db.select(['scores'], vars, what='id, score, test_name, window_width, window_height, extra_data', where='iteration_id=$i')
      for score in scores:
        sname = score['test_name']
        sid = score['id']
        if not sname in result['scores']:
          result['scores'][sname] = {}
        result['scores'][sname][sid] = dict(score)

    benchmark_data[bid][benchmark] = result

print pretty(benchmark_data)
print pretty(browser_data)

processed_benchmark_data = {}
for bid in benchmark_data.keys():
  processed_benchmark_data[bid] = {}
  for bench in benchmark_data[bid].keys():
    tests = benchmark_data[bid][bench]['scores']
    for test_name, test_results in tests.items():
      key = '%s/%s' % (bench, test_name)
      n_results = len(test_results)
      processed_benchmark_data[bid][key] = {}
      values = [v['score'] for v in test_results.values()]

      avg = np.average(values)
      processed_benchmark_data[bid][key]['score'] = avg

      std = np.std(values)
      processed_benchmark_data[bid][key]['std'] = std

print pretty(processed_benchmark_data)

def get_browser_name(id, data):
  return '%s %s' % (data[id]['name'], data[id]['version'].split('.')[0])

benchmark_test_names = processed_benchmark_data[processed_benchmark_data.keys()[0]].keys()
N = len(benchmark_test_names);

width = 1.0        # the width of the bars
ind = np.arange(N) * (width * 5)  # the x locations for the groups
nbrowsers = len(processed_benchmark_data.keys())

fig = plt.figure()
ax = fig.add_subplot(111)

offset = 0;
cm = plt.get_cmap('gist_rainbow')
ax.set_color_cycle([cm(1.*i/nbrowsers) for i in range(nbrowsers)])
colors = {
  1: 'orange',
  3: 'red',
  2: 'blue'
}
for bid in processed_benchmark_data.keys():
  # this_color = color = cm(1.*offset/nbrowsers)
  this_color = colors[bid]
  this_values = [x['score'] for x in processed_benchmark_data[bid].values()]
  this_err = [x['std'] for x in processed_benchmark_data[bid].values()]
  params = {}
  params['color'] = this_color
  if show_error:
    params['yerr'] = this_err
  processed_benchmark_data[bid]['rect'] = ax.bar(ind+width*offset, this_values, width, **params)
  offset += 1

# add some
ax.set_ylabel('scores')
ax.set_title('client: %s' % (client))
ax.set_xticks(ind+width)
ax.set_xticklabels(benchmark_test_names)

ylim = np.diff(ax.yaxis.get_data_interval())[0]
ax.set_ylim(0, ylim + 500)

rects = []
for bid in processed_benchmark_data:
  rects.append(processed_benchmark_data[bid]['rect'])

ax.legend( [rect[0] for rect in rects], [get_browser_name(bid, browser_data) for bid in processed_benchmark_data.keys()], loc='upper right', ncol=len(processed_benchmark_data), prop={'size':8} )

def autolabel(rects):
    # attach some text labels
    for rect in rects:
        height = rect.get_height()
        ax.text(rect.get_x()+rect.get_width()/2., 1.05*height, '%d'%int(height),
                ha='center', va='bottom', rotation='vertical', size='xx-small')

#for bid in processed_benchmark_data:
#    autolabel(processed_benchmark_data[bid]['rect'])

plt.setp(ax.get_xticklabels(), fontsize=8, rotation='vertical', ha='center')
#plt.show()
plt.savefig(outfile, orientation='landscape', pad_inches=0.2, papertype='legal', bbox_inches='tight')
