#!/usr/bin/env python

import sys

import numpy as np
import matplotlib.pyplot as plt

import ConfigParser
import web

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
platform = 'Android'
client = 'GalaxyNexus'
benchmarks = ['octane']
browser_ids = [5, 6]

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
    processed_benchmark_data[bid][bench] = {}
    tests = benchmark_data[bid][bench]['scores']
    for test_name, test_results in tests.items():
      processed_benchmark_data[bid][bench][test_name] = {}
      sum_scores = 0
      for result in test_results.values():
        sum_scores += result['score']
      avg_score = sum_scores / len(test_results)
      processed_benchmark_data[bid][bench][test_name]['score'] = avg_score
      # TODO: compute error, if possible

print pretty(processed_benchmark_data)

sys.exit(0);

scores = {
  'firefox': [21, 10, 32],
  'nightly': [33, 11, 22]
}

browsers = scores.keys()

N = len(benchmarks);

ind = np.arange(N)  # the x locations for the groups
width = 0.2        # the width of the bars

fig = plt.figure()
ax = fig.add_subplot(111)

rects = dict.fromkeys(scores);
offset = 0;
cm = plt.get_cmap('gist_rainbow')
ax.set_color_cycle([cm(1.*i/N) for i in range(N)])
for browser in rects.keys():
  this_color = color = cm(1.*offset/N)
  rects[browser] = ax.bar(ind+width*offset, scores[browser], width, color=this_color)
  offset += 1

# add some
ax.set_ylabel('scores')
ax.set_title('benchmarks: %s' % (platform))
ax.set_xticks(ind+width)
ax.set_xticklabels( benchmarks )

ax.legend( [rect[0] for rect in rects.values()], browsers, loc='upper center', bbox_to_anchor=(0.5, -0.05), ncol=len(browsers) )

def autolabel(rects):
    # attach some text labels
    for rect in rects:
        height = rect.get_height()
        ax.text(rect.get_x()+rect.get_width()/2., 1.05*height, '%d'%int(height),
                ha='center', va='bottom')

for rect in rects.values():
  autolabel(rect)

# plt.show()