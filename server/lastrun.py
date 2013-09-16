import xlrd
import xlwt
import argparse
import sys
import ConfigParser
import web
from pprint import pprint
from datetime import datetime
import numpy
import scipy.stats
import os
import os.path

channel_names = {
  'Firefox': {
    '0': 'Release',
    '1': 'Beta',
    '2': 'Aurora',
    '3': 'Nightly'
  },
  'Chrome': {
    '0': 'Stable',
    '1': 'Beta',
    '2': 'Dev'
  }
}

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

def guess_width(num_characters):
    return int((2+num_characters) * 256)

DEFAULT_CONF_FILE = 'speedtests_server.conf'
cfg = DefaultConfigParser()

cfg.read(DEFAULT_CONF_FILE)
DB_TYPE = cfg.get_default('server', 'db_type', 'sqlite')
DB_NAME = cfg.get_default('server', 'db_name', 'speedtests.sqlite')
DB_HOST = cfg.get_default('server', 'db_host', 'localhost')
DB_USER = cfg.get_default('server', 'db_user', 'speedtests')
DB_PASSWD = cfg.get_default('server', 'db_passwd', 'speedtests')

def get_browser_data(db, platform, browsers):
  """
  Read browser ids from the database, along with some other data.
  """

  browser_data = {}
  for name in browsers:
    qvars = {'platform': platform, 'name': name}
    result = list(db.select(['browsers'], qvars,
      what='name, version, channel, id, build',
      where='platform=$platform AND name=$name',
      order='build desc'
      ))
    for i in range(0, len(result)):
      data = dict(result[i])
      id = data['id']
      del data['id']
      browser_data[id] = data

  return browser_data

def get_runs_data(db, benchmark, browsers, client=None):
  """
  Read all test runs for the given browsers from the database.
  """

  runs_data = {}
  for browser_id, browser_data in browsers.items():
    if browser_id not in runs_data:
      runs_data[browser_id] = {
        'runs': []
      }
    qvars = {'browser_id': browser_id, 'bench_name': benchmark}
    qwhere = ['browser_id=$browser_id', 'bench_name=$bench_name', 'complete=1']
    if client is not None:
      qvars['client'] = client
      qwhere.append('client=$client')
    result = list(db.select(['runs'], qvars,
      what='uuid, start_time',
      where=' AND '.join(qwhere)))
    for e in result:
      runs_data[browser_id]['runs'].append(dict(e))

  return runs_data;

def main(options):
  if DB_TYPE is 'sqlite':
      dbargs = { 'dbn': DB_TYPE, 'db': DB_NAME }
  else:
      dbargs = { 'dbn': DB_TYPE, 'db': DB_NAME, 'db': DB_NAME,
                 'host': DB_HOST, 'user': DB_USER, 'pw': DB_PASSWD }
  db = web.database(**dbargs)
  db.printing = False

  browser_data = get_browser_data(db, options.platform, options.browsers)
  runs_data = get_runs_data(db, options.benchmark, browser_data, options.client)

  last_run = {
  }
  for browser_id, data in runs_data.items():
    for run in data['runs']:
      browser = browser_data[browser_id]

      name = browser['name']
      channel = str(browser['channel'])
      if not name in last_run:
        last_run[name] = {}
      if not channel in last_run[name]:
        last_run[name][channel] = None

      if last_run[name][channel] is None or \
         run['start_time'] > last_run[name][channel]['start_time']:
        run['build'] = browser['build']
        last_run[name][channel] = run

  for name, channels in last_run.items():
    channel_ids = channels.keys()
    channel_ids.sort()
    for channel in channel_ids:
      channel_name = channel_names[name][channel]
      run = channels[channel]
      elapsed = datetime.now() - run['start_time']
      print "%s %s (build %s): %s" % (name, channel_name, run['build'], str(elapsed).split(',')[0])

if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument('-B', '--benchmark', dest='benchmark', action='store', default=None,
                      help='benchmark name', required=True)
  parser.add_argument('-p', '--platform', dest='platform', action='store', default=None,
                      help='platform name', required=True, choices=['Windows 7', 'OSX', 'Linux', 'Android', 'FirefoxOS'])
  parser.add_argument('-b', '--browser', dest='browsers', action='store', default=None,
                      help='browser name', required=True, nargs='+')
  parser.add_argument('-c', '--client', dest='client', action='store', default=None,
                      help='report on a specific client', required=False)
  options = parser.parse_args()

  main(options)