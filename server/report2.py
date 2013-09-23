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

def compute_z_value(data, confidence=0.95):
    a = 1.0*numpy.array(data)
    n = len(a)
    m, se = numpy.mean(a), scipy.stats.sem(a)
    z = se * scipy.stats.t._ppf((1+confidence)/2., n-1)
    return z

def get_browser_data(db):
  """
  Read browser ids from the database, along with some other data.
  """

  browser_data = {}
  result = list(db.select(['browsers'], {},
    what='platform, name, version, channel, id, build'
    ))
  for i in range(0, len(result)):
    data = dict(result[i])
    id = data['id']
    browser_data[id] = data

  return browser_data

def get_run_data(db):
  run_data = {}
  results = list(db.query('select * from runs where complete=1 and uuid not in (select run_uuid from reports)'))
  for i in range(0, len(results)):
    result = dict(results[i])
    run_uuid = result['uuid']
    run_data[run_uuid] = result

  return run_data

def get_iteration_data(db, run_uuid):
  iteration_data = []
  results = list(db.query('select * from iterations where run_uuid="%s"' % (run_uuid)))
  for i in range(0, len(results)):
    iteration_data.append(dict(results[i]))

  return iteration_data;

def get_score_data(db, iteration_id):
  score_data = []
  results = list(db.query('select * from scores where iteration_id=%s' % iteration_id))
  for i in range(0, len(results)):
    score_data.append(dict(results[i]))

  return score_data

def get_unpublished_reports(db):
  reports = []
  results = list(db.query('select * from reports where published=0'))
  for i in range(0, len(results)):
    reports.append(dict(results[i]))
  return reports

DEFAULT_CONF_FILE = 'speedtests_server.conf'
cfg = DefaultConfigParser()

cfg.read(DEFAULT_CONF_FILE)
DB_TYPE = cfg.get_default('server', 'db_type', 'sqlite')
DB_NAME = cfg.get_default('server', 'db_name', 'speedtests.sqlite')
DB_HOST = cfg.get_default('server', 'db_host', 'localhost')
DB_USER = cfg.get_default('server', 'db_user', 'speedtests')
DB_PASSWD = cfg.get_default('server', 'db_passwd', 'speedtests')

cfg.read(DEFAULT_CONF_FILE)
RDS_TYPE = cfg.get_default('rds', 'db_type', 'mysql')
RDSB_NAME = cfg.get_default('rds', 'db_name')
RDS_HOST = cfg.get_default('rds', 'db_host')
RDS_USER = cfg.get_default('rds', 'db_user')
RDS_PASSWD = cfg.get_default('rds', 'db_passwd')

def main(options):
  if DB_TYPE == 'sqlite':
      dbargs = { 'dbn': DB_TYPE, 'db': DB_NAME }
  else:
      dbargs = { 'dbn': DB_TYPE, 'db': DB_NAME, 'db': DB_NAME,
                 'host': DB_HOST, 'user': DB_USER, 'pw': DB_PASSWD }
  db = web.database(**dbargs)
  db.printing = False

  rdsargs = { 'dbn': RDS_TYPE, 'db': RDS_NAME,
              'host': RDS_HOST, 'user': RDS_USER, 'pw': RDS_PASSWD }
  rds = web.database(**rdsargs)
  rds.printing = False

  browser_data = get_browser_data(db)
  run_data = get_run_data(db)

  print "%d records to insert" % len(run_data.keys())
  for run_uuid, run in run_data.items():
    bench_name = run['bench_name']
    start_time = run['start_time']
    browser_id = run['browser_id']
    browser = browser_data[browser_id]
    browser_name = browser['name']
    browser_channel = str(browser['channel'])
    browser_version = browser['version']
    browser_build = browser['build']
    browser_platform = browser['platform']
    scores = {}
    iteration_data = get_iteration_data(db, run_uuid)
    for iteration in iteration_data:
      score_data = get_score_data(db, iteration['id'])
      for score in score_data:
        test_name = score['test_name']
        score = score['score']
        if not test_name in scores.keys():
          scores[test_name] = []
        scores[test_name].append(score)

    for test_name, stats in scores.items():
      mean = numpy.average(stats)
      mean_z_95 = compute_z_value(stats)
      mean_std_err = scipy.stats.sem(stats)
      record = {
        'run_uuid': run_uuid,
        'bench_name': bench_name,
        'test_name': test_name,
        'start_time': start_time,
        'browser_name': browser_name,
        'browser_channel': channel_names[browser_name][browser_channel],
        'browser_version': browser_version,
        'browser_build': browser_build,
        'browser_platform': browser_platform,
        'mean': mean,
        'mean_z_95': mean_z_95,
        'mean_std_err': mean_std_err,
        'published': 0
      }

      try:
        rds.insert('reports', **record)
        record['published'] = 1
      except e:
        print "rds insert failed: %s, %s" % (record, e)

      try:
        db.insert('reports', **record)
      except e:
        print "db insert failed: %s, %s" % (record, e)

  unpublished_reports = get_unpublished_reports(db);
  print "%d unpublished records to send" % len(unpublished_reports)

  for record in unpublished_reports:
    try:
      rds.insert('reports', **record)
      db.query("update reports set published=1 where run_uuid='%s' and bench_name='%s' and test_name'%s'" % (record['run_uuid'], record['bench_name'], record['test_name']))

    except e:
      print "rds insert failed: %s, %s" % (record, e)

if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  #parser.add_argument('-i', '--in', dest='infile', action='store', default=None,
  #                    help='input file name', required=True)
  #parser.add_argument('-o', '--out', dest='outfile', action='store', default=None,
  #                    help='output file name', required=False)
  #parser.add_argument('-B', '--benchmark', dest='benchmark', action='store', default=None,
  #                    help='benchmark name', required=True)
  #parser.add_argument('-p', '--platform', dest='platform', action='store', default=None,
  #                    help='platform name', required=True, choices=['Windows 7', 'OSX', 'Linux', 'Android', 'FirefoxOS'])
  #parser.add_argument('-b', '--browser', dest='browsers', action='store', default=None,
  #                    help='browser name', required=True, nargs='+')
  #parser.add_argument('-c', '--client', dest='client', action='store', default=None,
  #                    help='report on a specific client', required=False)
  options = parser.parse_args()

  main(options)