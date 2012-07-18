#!/usr/bin/env python

# ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
# 
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
# 
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
# 
# The Original Code is mozilla.org code.
# 
# The Initial Developer of the Original Code is
# Mozilla.org.
# Portions created by the Initial Developer are Copyright (C) 2010
# the Initial Developer. All Rights Reserved.
# 
# Contributor(s):
#     Jeff Hammel <jhammel@mozilla.com>     (Original author)
# 
# Alternatively, the contents of this file may be used under the terms of
# either of the GNU General Public License Version 2 or later (the "GPL"),
# or the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
# 
# ***** END LICENSE BLOCK *****

import lxml.html
import re
import sys
import time
from dateutil.parser import parse
from datetime import datetime

### platform information
# XXX this should really go in its out package
# see: https://bugzilla.mozilla.org/show_bug.cgi?id=603019

platforms = ['linux',
             'linux64',
             'win32',
             'macosx',
             'macosx64',
             'android']

def platform():
  """returns string of platform, as displayed for buildbot builds"""
  # XXX this should use the same code as buildbot
  # and in fact the same code should be used in all Mozilla python code
  # that does this sort of thing
  if sys.platform == 'linux2':
    return 'linux'
  elif sys.platform == 'win32':
    return 'win32'
  elif sys.platform == 'darwin':
    return 'macosx64'
  raise NotImplementedError

###

def str2ssepoch(string):
  """converts a string to seconds since epoch"""
  try:
    # see if this is already in seconds
    return int(string)
  except ValueError:
    date = parse(string)
    return int(time.mktime(date.timetuple()))

class NotFoundException(Exception):
  """exception for a resource not being found (e.g. no logs)"""
  def __init__(self, message, url):
    self.url = url
    Exception.__init__(self, message + ': ' + url)

# TODO: fetch symbols from http://symbols.mozilla.org/firefox/ ?

class GetLatestTinderbox(object):

  # class data
  DEFAULT_APP = 'firefox'
  DEFAULT_APP_SHORT = 'firefox'
  BASE_URL = 'http://stage.mozilla.org/pub/mozilla.org/%(APP)s/tinderbox-builds/'
  BASE_REGEX = r'%(APP_SHORT)s-.*\.%(LOCALE)s\.%(PLATFORM)s'

  def __init__(self, branch='mozilla-central',
               platform=platform(),
               debug=False, locale='en-US',
               app=DEFAULT_APP, app_short=DEFAULT_APP_SHORT):
    # build the base URL
    self.branch = branch
    self.platform = platform
    self.base_url = self.BASE_URL % { 'APP': app }
    self.base_url += branch + '-' + platform
    if debug:
      self.base_url += '-debug'
    self.base_url += '/'
    regex = self.BASE_REGEX % { 'LOCALE': locale,
                                'PLATFORM': self.platform_regex(),
                                'APP_SHORT': app_short }
    self.regex = regex

  ### regular expressions

  def platform_regex(self):
    """return the platform part of the regex"""
    regex = {'linux': 'linux-i686',
             'linux64': 'linux-x86_64',
             'win32': 'win32',
             'win64': 'win64-x86_64',
             'macosx': 'mac',
             'macosx64': 'mac',
             'android': 'android-arm'
             }
    return regex[self.platform]

  def build_regex(self):
    """the full regex for a build"""
    regex = {'linux': r'\.tar\.bz',
             'linux64': r'\.tar\.bz',
             'win32': r'\.zip',
             'win64': r'\.zip',
             'macosx': r'\.dmg',
             'macosx64': r'\.dmg',
             'android': r'\.apk'
             }
    return self.regex + regex[self.platform]

  def tests_regex(self):
    return self.regex + r'\.tests\.zip'

  def symbols_regex(self):
    return self.regex + r'\.crashreporter-symbols.*\.zip'

  def log_regex(self):
    """regular expression for all logs"""
    return r'%s_.*_test-(.*)-build[0-9]+.txt.gz' % self.branch

  ### methods to obtain URLs

  def builds(self, url=None, timestamp=0):
    """returns dictionary of buildid -> url"""
    
    timestamp = timestamp or 0
    url = url or self.base_url
    try:
      element = lxml.html.parse(url)
    except IOError:
      raise NotFoundException("No builds found at %s" % url, url)
    links = element.xpath('//a[@href]')
    builds = {}
    url = url.rstrip('/')
    for link in links:
      target = link.get('href').strip('/')
      name = link.text.strip('/')
      if name != target:
        continue
      try:
        build_id = int(name)
      except ValueError:
        continue
      if build_id > timestamp:
        builds[build_id] = '%s/%s/' % (url, name)
    return builds

  def latest_url(self, regex=None, url=None):
    if isinstance(regex, basestring):
      regex = re.compile(regex)
    if url is None:
      _builds = self.builds(url)
    else:
      _builds = {url: url}
    for latest in sorted(_builds.keys(), reverse=True):
      build_info = _builds[latest]
      if regex is None:
        return build_info
      element = lxml.html.parse(build_info)
      links = element.xpath('//a[@href]')
      for link in links:
        href = link.get('href')
        if regex.match(href):
          return '%s/%s' % (build_info.rstrip('/'), href)    

  def latest_build_url(self, url=None):
    return self.latest_url(self.build_regex(), url)

  def latest_tests_url(self, url=None):
    return self.latest_url(self.tests_regex(), url)

  def latest_symbols_url(self, url=None):
    return self.latest_url(self.symbols_regex(), url)    

  ### functions to return logs

  def logs(self, url=None):
    if url is None:
      _builds = self.builds(url)
      url = _builds[sorted(_builds.keys(), reverse=True)[0]]
    try:
      element = lxml.html.parse(url)
    except IOError:
      raise NotFoundException("url %s not found" % url, url)
    links = element.xpath('//a[@href]')
    logs = {}
    regex = re.compile(self.log_regex())
    for link in links:
      href = link.get('href')
      match = regex.match(href)
      if match:
        logs[match.group(1)] = '%s/%s' % (url.rstrip('/'), match.group(0))
    if logs:
      return logs
    else:
      raise NotFoundException("No logs found", url)

  @classmethod
  def all_logs(cls, branches=('mozilla-central',), platforms=None, debug=(False, True), tests=None, timestamp=0, logger=None):
    """yield all the tests currently found"""

    # determine the platforms
    if not platforms:
      platforms = globals()['platforms'][:]

    for branch in branches:
      for _debug in debug:
        for platform in platforms:

          # get your scraper
          latest = cls(branch=branch, platform=platform, debug=_debug)

          # find the builds
          try:
            builds = latest.builds(timestamp=timestamp)
          except NotFoundException:
            if logger:
              logger.warn('No builds found for %s %s %s' % (branch,
                                                            platform,
                                                            _debug))
            continue

          for build, url in builds.items():

            # find the logs
            try:
              logs = latest.logs(url)
            except NotFoundException:
              if logger:
                logger.warn('No logs found at %s' % url)
              continue

            # determine which test logs to download
            if tests:
              logs = dict([(test, value) for test, value in logs.items()
                           if test in tests])

            if logger:
              logger.info('%d logs' % len(logs))

            # yield the test URL and metadata
            for test, value in logs.items():
              yield value, dict(branch=branch,
                                platform=platform,
                                debug=_debug,
                                timestamp=build,
                                test=test)
              

def main(args=sys.argv[1:]):

  # parse options
  from optparse import OptionParser
  parser = OptionParser()
  parser.add_option('-d', '--debug', dest='debug', 
                    action='store_true', default=False,
                    help="get a debug build")
  try:
    client_platform = platform()
  except NotImplementedError:
    client_platform = None
  platform_help = 'platform (%s)' % ', '.join(platforms)
  if client_platform:
    platform_help += ' [DEFAULT: %s]' % client_platform
  parser.add_option('-p', '--platform', dest='platform',
                    default=client_platform, help=platform_help)
  parser.add_option('--product', dest='product', default='mozilla-central',
                    help="product [DEFAULT: mozilla-central]")
  parser.add_option('--app', dest='app', default='firefox',
                    help="app (e.g. mobile) [DEFAULT: firefox]")
  parser.add_option('--appshort', dest='appshort', default='firefox',
                    help="appshort (e.g. fennec) [DEFAULT: firefox]")
  parser.add_option('--tests', dest='tests', action='store_true', default=False,
                    help='output URL to tests')
  parser.add_option('--symbols', dest='symbols', action='store_true', default=False,
                    help='output URL to symbols')
  parser.add_option('--logs', dest='logs', action='store_true', default=False,
                    help='list test logs')
  parser.add_option('--log', '-l', dest='log',
                    help='print the URL of a specific log file')
  parser.add_option('--all-logs', dest='print_all_logs',
                    action='store_true', default=False,
                    help='print all logs in the world')
  parser.add_option('--url', '-u', dest='url',
                    help="get builds from a specific url")
  parser.add_option('--latest', dest='latest', action='store_true', default=False,
                    help='print the URL of the latest build')
  parser.add_option('--builds', dest='builds', action='store_true', default=False,
                    help="list builds found")
  parser.add_option('--datestamp', dest='datestamp',
                    help='date stamp format')
  parser.add_option('-s', '--start-date', dest='start',
                    help="don't scrape files older than this date")  
  options, args = parser.parse_args(args)

  # check parsed options
  if not options.platform:
    parser.error('Specify your platform')
  if options.symbols and options.tests:
    parser.error("Can't specify --tests and --symbols")
  if options.platform == 'macosx' and not options.debug:
    # universal binary
    parser.error("No more opt macosx builds; use the universal binary, macosx64, android")

  # fix timestamp for start-date
  if options.start:
    options.start = str2ssepoch(options.start)

  # print out all logs in the whole multiverse
  if options.print_all_logs:
    all_logs = GetLatestTinderbox.all_logs()
    for log in all_logs:
      print log[0]
    return
      
  # instantiate class
  latest_tinderbox = GetLatestTinderbox(options.product, options.platform, options.debug,
                                        app=options.app, app_short=options.appshort)

  # print latest URL
  if options.latest:
    print latest_tinderbox.latest_url()
    return

  # print out all builds currently in the tinderbox URL
  if options.builds:
    builds = latest_tinderbox.builds(options.url, timestamp=options.start)
    for key in sorted(builds.keys()):
      build = builds[key]
      if options.datestamp:
        key = datetime.fromtimestamp(key).strftime(options.datestamp)
      print '%s : %s' % (key, build)
    return

  # print out all logs found
  if options.logs:
    logs = latest_tinderbox.logs(options.url)
    try:
      for key in sorted(logs.keys()):
        print '%s: %s' % (key, logs[key])
      return
    except NotFoundException, e:
      import pdb; pdb.set_trace()

  # print out the URL for a specific log
  if options.log:
    logs = latest_tinderbox.logs(options.url)
    print logs[options.log]
    return

  if options.tests:
    latest = latest_tinderbox.latest_tests_url(options.url)
  elif options.symbols:
    latest = latest_tinderbox.latest_symbols_url(options.url)
  else:
    latest = latest_tinderbox.latest_build_url(options.url)
  if latest is None:
    sys.exit(1)
  print latest

if __name__ == '__main__':
  main()

