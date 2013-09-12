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
from versions import current

channel_names = {
  'Firefox': {
    0: 'Release',
    1: 'Beta',
    2: 'Aurora',
    3: 'Nightly'
  },
  'Chrome': {
    0: 'Stable',
    1: 'Beta',
    2: 'Dev'
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
  for name, versions in browsers.items():
    for version in versions:
      qvars = {'platform': platform, 'name': name, 'version': version}
      result = list(db.select(['browsers'], qvars,
        what='id, build',
        where='platform=$platform AND name=$name AND version=$version',
        order='build desc',
        limit=1))
      if 0 < len(result):
        if name not in browser_data:
          browser_data[name] = {}
        browser_data[name][version] = dict(result[0])

  return browser_data

def get_runs_data(db, benchmark, browsers, client=None):
  """
  Read all test runs for the given browsers from the database.
  """

  runs_data = {}
  for name, versions in browsers.items():
    runs_data[name] = {}
    for version, browser_data in versions.items():
      runs_data[name][version] = {'runs':[]}
      qvars = {'browser_id': browser_data['id'], 'bench_name': benchmark}
      qwhere = ['browser_id=$browser_id', 'bench_name=$bench_name', 'complete=1']
      if client is not None:
        qvars['client'] = client
        qwhere.append('client=$client')
      result = list(db.select(['runs'], qvars,
        what='uuid, start_time',
        where=' AND '.join(qwhere)))
      for e in result:
        runs_data[name][version]['runs'].append(dict(e))

  return runs_data;

def get_run_scores(db, run_uuid):
  """
  Get all the scores associated with a run, indexed by test name.
  """

  scores_data = {}
  iterations = list(db.select(['iterations'], {'run_uuid':run_uuid},
    what='id',
    where='run_uuid=$run_uuid'))
  for iteration in iterations:
    scores = list(db.select(['scores'], {'iteration_id':iteration['id']},
      what='test_name, score',
      where='iteration_id=$iteration_id'))
    for score in scores:
      test_name = str(score.test_name)
      if test_name not in scores_data:
        scores_data[test_name] = []
      scores_data[test_name].append(score['score'])

  return scores_data

def compute_z_value(data, confidence=0.95):
    a = 1.0*numpy.array(data)
    n = len(a)
    m, se = numpy.mean(a), scipy.stats.sem(a)
    z = se * scipy.stats.t._ppf((1+confidence)/2., n-1)
    return z

class Report:
  def __init__(self):
    self.tests = {}
    self.dates = {}

  def add_result(self, timestamp, browser_name, browser_version, browser_build, test_name, mean, mean_z_95, mean_std_err):
    if 'Firefox' in browser_name:
      browser_name = 'Firefox'
    elif 'Chrome' in browser_name:
      browser_name = 'Chrome'
    browser = "%s:%s" % (browser_name, browser_version)
    if test_name not in self.tests.keys():
      self.tests[test_name] = {}
      self.dates[test_name] = set()
    if browser not in self.tests[test_name].keys():
      self.tests[test_name][browser] = {}

    date = timestamp.strftime('%Y-%m-%d')
    self.dates[test_name].add(date)

    if date in self.tests[test_name][browser]:
      existing = self.tests[test_name][browser][date]
      if timestamp < existing['timestamp']:
        return

    self.tests[test_name][browser][date] = {
      'mean': '{0:.2f}'.format(mean),
      'mean_z_95': '{0:.2f}'.format(mean_z_95),
      'mean_std_err': '{0:.2f}'.format(mean_std_err),
      'build': str(browser_build),
      'timestamp': timestamp
    }

  def write(self, wb, file_name):
    test_names = self.tests.keys()
    test_names.sort()
    headers = ['mean', 'mean_z_95', 'mean_std_err', 'build']

    offset = 1
    stride = 4
    for test_name in test_names:
      sheet = wb.add_sheet(test_name)

      dates = list(self.dates[test_name])
      dates.sort()
      # dates.reverse()

      browsers = self.tests[test_name].keys()
      browsers.sort()

      row = 0
      for row in range(0, len(dates)):
        sheet.write(2 + row, 0, dates[row])

      col_widths = {
        0: guess_width(10)
      }
      for browser, runs in self.tests[test_name].items():
        i = browsers.index(browser)
        name, version = browser.split(':')
        channel_offset = int(version) - current[name]
        channel_name = channel_names[name][channel_offset]
        sheet.write_merge(0, 0, offset + i*stride, offset + (i+1)*stride - 1, "%s %s" % (name, channel_name))
        for j in range(0, len(headers)):
          col = offset + i*stride + j
          hdr = headers[j]
          sheet.write(1, offset + i*stride + j, hdr)
          col_widths[col] = guess_width(len(hdr))
        for date, run in runs.items():
          row = 2 + dates.index(date)
          for j in range(0, len(headers)):
            col = offset + i*stride + j
            val = run[headers[j]]
            sheet.write(row, col, val)
            col_widths[col]= max(col_widths[col], guess_width(len(val)))

      for col, width in col_widths.items():
        sheet.col(col).width = width

    wb.save(file_name)

def build_spreadsheet(platform, browser_data, benchmark, data):
  report = Report()

  for name, versions in data.items():
    for version, run_data in versions.items():
      build = browser_data[name][version]['build']
      runs = run_data['runs']
      if len(runs) < 1:
        print "Error: no run data for %s %s" % (name, version)
      for run in runs:
        scores = run['scores']
        for test_name, score_list in scores.items():
          mean = numpy.average(score_list)
          mean_z_95 = compute_z_value(score_list)
          mean_std_err = scipy.stats.sem(score_list)
          report.add_result(run['start_time'], name, version, build, test_name, mean, mean_z_95, mean_std_err)

  wb = xlwt.Workbook()
  file_name = '%s-%s-%s.xls' % (platform, benchmark, datetime.now().strftime('%Y%m%d'))
  report.write(wb, file_name)

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

  for name, versions in runs_data.items():
    for version, data in versions.items():
      for run in data['runs']:
        run['scores'] = get_run_scores(db, run['uuid'])
        # run['start_time'] = run['start_time'].strftime('%Y-%m-%d')

  build_spreadsheet(options.platform, browser_data, options.benchmark, runs_data)

class BrowserAction(argparse.Action):
  """
  Argparse class for handling browser name and version options.
  """

  def __call__(self, parser, namespace, values, option_string=None):
    if not getattr(namespace, self.dest):
      setattr(namespace, self.dest, {})
    dest = getattr(namespace, self.dest)
    name = values.pop(0)
    if name not in dest:
      dest[name] = []
    dest[name] = [x for x in set(dest[name]) | set(parse_range(values))]
    dest[name].sort()

if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  #parser.add_argument('-i', '--in', dest='infile', action='store', default=None,
  #                    help='input file name', required=True)
  #parser.add_argument('-o', '--out', dest='outfile', action='store', default=None,
  #                    help='output file name', required=False)
  parser.add_argument('-B', '--benchmark', dest='benchmark', action='store', default=None,
                      help='benchmark name', required=True)
  parser.add_argument('-p', '--platform', dest='platform', action='store', default=None,
                      help='platform name', required=True, choices=['Windows 7', 'OSX', 'Linux', 'Android', 'FirefoxOS'])
  parser.add_argument('-b', '--browser', dest='browsers', action=BrowserAction, default=None,
                      help='browser name and version', required=True, nargs='+')
  parser.add_argument('-c', '--client', dest='client', action='store', default=None,
                      help='report on a specific client', required=False)
  options = parser.parse_args()

  main(options)