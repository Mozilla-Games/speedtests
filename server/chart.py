#!/usr/bin/env python

import numpy as np
import matplotlib.pyplot as plt

import ConfigParser
import web

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
platform = 'android'
benchmarks = ['webgl-aquarium', 'octane', 'sunspider']
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

plt.show()