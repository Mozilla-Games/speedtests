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

date_style = xlwt.XFStyle()
date_style.num_format_str = 'YYY-MM-DD'

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

def get_browser_data(db, platforms, browsers):
  """
  Read browser ids from the database, along with some other data.
  """

  browser_data = {}
  for platform in platforms:
    for name in browsers:
      qvars = {'platform': platform, 'name': name}
      result = list(db.select(['browsers'], qvars,
        what='name, version, channel, id, build, platform',
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
  def __init__(self, platform):
    self.platform = platform
    self.tests = {}
    self.dates = {}

  def add_result(self, timestamp, browser, test_name, mean, mean_z_95, mean_std_err):
    browser_string = "%s:%s:%s" % (browser['platform'], browser['name'], browser['channel'])
    if test_name not in self.tests.keys():
      self.tests[test_name] = {}
      self.dates[test_name] = set()
    if browser_string not in self.tests[test_name].keys():
      self.tests[test_name][browser_string] = {}

    # date = timestamp.strftime('%Y-%m-%d')
    date = timestamp
    self.dates[test_name].add(date)

    if date in self.tests[test_name][browser_string]:
      existing = self.tests[test_name][browser_string][date]
      if timestamp < existing['timestamp']:
        return

    self.tests[test_name][browser_string][date] = {
      'mean': '{0:.2f}'.format(mean),
      'mean_z_95': '{0:.2f}'.format(mean_z_95),
      'mean_std_err': '{0:.2f}'.format(mean_std_err),
      'version': browser['version'],
      'build': browser['build'],
      'timestamp': timestamp
    }

  def write(self, wb, file_name):
    test_names = self.tests.keys()
    test_names.sort()
    HEADERS = ['version', 'mean', 'mean_z_95', 'mean_std_err', 'build']
    PLATFORM_ROW = 0
    CHANNEL_ROW = 0
    HEADER_ROW = CHANNEL_ROW + 1
    DATE_START_ROW = HEADER_ROW + 1

    offset = 1
    stride = len(HEADERS)
    for test_name in test_names:
      sheet = wb.add_sheet(test_name[0:31])

      dates = list(self.dates[test_name])
      dates.sort()
      # dates.reverse()

      browsers = self.tests[test_name].keys()
      browsers.sort()

      row = 0
      for row in range(0, len(dates)):
        sheet.write(DATE_START_ROW + row, 0, dates[row], date_style)

      col_widths = {
        0: guess_width(10)
      }
      # sheet.write_merge(PLATFORM_ROW, PLATFORM_ROW, 1, len(self.tests[test_name].keys()) * len(HEADERS), self.platform)
      for browser, runs in self.tests[test_name].items():
        i = browsers.index(browser)
        platform, name, channel = browser.split(':')
        channel_name = channel_names[name][channel]
        sheet.write_merge(CHANNEL_ROW, CHANNEL_ROW, offset + i*stride, offset + (i+1)*stride - 1, "%s/%s/%s" % (platform, name, channel_name))
        for j in range(0, len(HEADERS)):
          col = offset + i*stride + j
          hdr = HEADERS[j]
          sheet.write(HEADER_ROW, offset + i*stride + j, hdr)
          col_widths[col] = guess_width(len(hdr))
        for date, run in runs.items():
          row = DATE_START_ROW + dates.index(date)
          for j in range(0, len(HEADERS)):
            col = offset + i*stride + j
            val = run[HEADERS[j]]
            sheet.write(row, col, val)
            col_widths[col]= max(col_widths[col], guess_width(len(val)))

      for col, width in col_widths.items():
        sheet.col(col).width = width

    if not os.path.isdir('reports'):
      os.mkdir('reports')
    wb.save('reports/%s' % file_name)

def build_spreadsheet(platforms, browser_data, benchmark, runs_data):
  report = Report(platforms)

  for browser_id, run_data in runs_data.items():
    browser = browser_data[browser_id]
    runs = run_data['runs']
    for run in runs:
      scores = run['scores']
      for test_name, score_list in scores.items():
        mean = numpy.average(score_list)
        mean_z_95 = compute_z_value(score_list)
        mean_std_err = scipy.stats.sem(score_list)
        report.add_result(run['start_time'], browser, test_name, mean, mean_z_95, mean_std_err)

  wb = xlwt.Workbook()
  file_name = '[%s]-%s-%s.xls' % (','.join(platforms), benchmark, datetime.now().strftime('%Y%m%d'))
  report.write(wb, file_name)

def main(options):
  if DB_TYPE == 'sqlite':
      dbargs = { 'dbn': DB_TYPE, 'db': DB_NAME }
  else:
      dbargs = { 'dbn': DB_TYPE, 'db': DB_NAME, 'db': DB_NAME,
                 'host': DB_HOST, 'user': DB_USER, 'pw': DB_PASSWD }
  db = web.database(**dbargs)
  db.printing = False

  browser_data = get_browser_data(db, options.platforms, options.browsers)
  runs_data = get_runs_data(db, options.benchmark, browser_data, options.client)

  for browser_id, data in runs_data.items():
    for run in data['runs']:
      run['scores'] = get_run_scores(db, run['uuid'])
      # run['start_time'] = run['start_time'].strftime('%Y-%m-%d')

  build_spreadsheet(options.platforms, browser_data, options.benchmark, runs_data)

if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  #parser.add_argument('-i', '--in', dest='infile', action='store', default=None,
  #                    help='input file name', required=True)
  #parser.add_argument('-o', '--out', dest='outfile', action='store', default=None,
  #                    help='output file name', required=False)
  parser.add_argument('-B', '--benchmark', dest='benchmark', action='store', default=None,
                      help='benchmark name', required=True)
  parser.add_argument('-p', '--platform', dest='platforms', action='store', default=None,
                      help='platform name', required=True, choices=['Windows 7', 'OSX', 'Linux', 'Android', 'Firefox OS'],
                      nargs='+')
  parser.add_argument('-b', '--browser', dest='browsers', action='store', default=None,
                      help='browser name', required=True, nargs='+')
  parser.add_argument('-c', '--client', dest='client', action='store', default=None,
                      help='report on a specific client', required=False)
  options = parser.parse_args()

  main(options)