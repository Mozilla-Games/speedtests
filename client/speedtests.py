import BaseHTTPServer
import cgi
import collections
import ConfigParser
import datetime
import errno
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib2
import zipfile

if platform.system() == 'Windows':
    import _winreg
    import ie_reg

import fxinstall
import results

class Config(object):
    DEFAULT_CONF_FILE = 'speedtests.conf'
    
    def __init__(self):
        self.cfg = None
        self.local_port = 8111
        self.server_html_url = 'http://brasstacks.mozilla.com/speedtests'
        self.server_api_url = 'http://brasstacks.mozilla.com/speedtests/api'
        self.cfg = None
        self.local_test_base_path = '/speedtests'

    @property
    def local_test_base_url(self):
        # IE has issues loading pages from localhost, so we'll use the
        # external IP.
        return 'http://%s:%d%s' % (self.local_ip, self.local_port,
                                   self.local_test_base_path)

    def read(self, testmode=False, noresults=False, conf_file=None):
        self.testmode = testmode
        self.noresults = noresults
        if not conf_file:
            conf_file = Config.DEFAULT_CONF_FILE
        self.cfg = ConfigParser.ConfigParser()
        self.cfg.read(conf_file)
        
        try:
            self.local_port = self.cfg.getint('speedtests', 'local_port')
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            pass
        
        try:
            self.server_html_url = self.cfg.get('speedtests', 'test_base_url').rstrip('/')
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            pass

        try:
            self.server_api_url = self.cfg.get('speedtests', 'server_url').rstrip('/')
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            pass            

        try:
            self.server_results_url = self.cfg.get('speedtests', 'server_results_url').rstrip('/') + '/'
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            self.server_results_url = self.server_api_url + '/testresults/'

        # We can also find out the address like this, supposedly more reliable:
        #s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        #s.connect((<TEST_HOST>, 80))
        #local_ip = s.getsockname()
        self.local_ip = socket.gethostbyname(socket.gethostname())


config = Config()


class BrowserController(object):
    
    def __init__(self, os_name, browser_name, profiles, cmd, args_tuple=()):
        self.os_name = os_name
        self.browser_name = browser_name
        self.profiles = []
        if type(profiles) != list:
            profiles = [profiles]
        for p in profiles:
            if type(p) == str:
                self.profiles.append({'path': p})
            else:
                self.profiles.append(p)
        self.cmd = cmd
        self.args_tuple = args_tuple
        self.proc = None
        self.launch_time = None
        try:
            self.cmd = config.cfg.get(os_name, browser_name)
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            pass

    def set_test_urls(self, tests):
        self.test_url_iter = iter(tests)
        self.current_test_url = None

    def next_test(self):
        try:
            self.current_test_url = self.test_url_iter.next()
        except StopIteration:
            return False
        if self.running():
            self.terminate()
        self.launch(self.current_test_url)
        return True

    def init_browser(self):
        pass
            
    def cmd_line(self, url):
        return (self.cmd,) + self.args_tuple + (url,)

    def browser_exists(self):
        return os.path.exists(self.cmd)
    
    def get_profile_archive_path(self, profile):
        archive = profile.get('archive', '%s.zip' % self.os_name)
        return os.path.join('profiles', self.browser_name, archive)
    
    def archive_current_profiles(self):
        if not self.browser_exists() or not self.profiles:
            return
        for p in self.profiles:
            if not os.path.exists(p['path']):
                continue
            profile_archive = self.get_profile_archive_path(p)
            profile_zip = zipfile.ZipFile(profile_archive, 'w')
            for (dirpath, dirnames, filenames) in os.walk(p['path']):
                for f in filenames:
                    filepath = os.path.join(dirpath, f)
                    arcpath = filepath[len(p['path']):]
                    profile_zip.write(filepath, arcpath)
            profile_zip.close()

    def retry_file_op(self, func, args):
        success = False
        attempts = 0
        while attempts < 3:
            attempts += 1
            try:
                func(*args)
            except (IOError, OSError):
                pass
            else:
                success = True
                break
            time.sleep(2)
        return success

    def copy_profiles(self):
        if not self.browser_exists():
            return False
        for p in self.profiles:
            profile_archive = self.get_profile_archive_path(p)
            if not os.path.exists(profile_archive):
                return
            if os.path.exists(p['path']):
                t = tempfile.mkdtemp()
                def f(path, tmp):
                    shutil.rmtree(tmp)
                    shutil.move(path, tmp)
                if not self.retry_file_op(f, [p['path'], t]):
                    print 'Failed to copy profile 3 times; giving up.'
                    return False
                p['previous_profile'] = os.path.join(t, os.path.basename(p['path']))
            else:
                p['previous_profile'] = ''
            try:
                os.mkdir(p['path'])
            except OSError:
                pass
            profile_zip = zipfile.ZipFile(profile_archive, 'r')
            profile_zip.extractall(p['path'])
        return True
    
    def clean_up(self):
        if not self.profiles:
            return
        for p in self.profiles:
            if not p['previous_profile']:
                continue
            def f(p):
                shutil.rmtree(p['path'])
                shutil.move(p['previous_profile'], p['path'])
                os.rmdir(os.path.dirname(p['previous_profile']))

            if not self.retry_file_op(f, [p]):
                print 'Failed to restore profile 3 times; giving up.'

    def launch(self, url=None):
        if not self.copy_profiles():
            print 'Failed to copy profiles'
            return False
        if not url:
            url = config.test_url
        cl = self.cmd_line(url)
        print 'Launching %s...' % ' '.join(cl)
        self.launch_time = datetime.datetime.now()
        self.proc = subprocess.Popen(cl)
        return True

    def running(self):
        if not self.proc:
            return False
        running = self.proc.poll()
        if running != None:
            self.proc = None
        return running == None
	
    def execution_time(self):
        return datetime.datetime.now() - self.launch_time

    def terminate(self):
        if self.proc:
            print 'Terminating process...'
            try:
                self.proc.terminate()
            except:  #FIXME
                pass
            for i in range(0, 5):
                print 'Polling...'
                if self.proc.poll() != None:
                    self.proc = None
                    break
                time.sleep(2)
            if self.proc:
                print 'Killing process...'
                try:
                    self.proc.kill()
                except:
                    pass
                print 'Waiting for process to die...'
                self.proc.wait()  # or poll and error out if still running?
                self.proc = None
            print 'Process is dead.'
            time.sleep(5)
        self.clean_up()


class LatestFxBrowserController(BrowserController):
    
    """ Specialization to download latest nightly before launching. """
    
    INSTALL_SUBDIR = 'speedtests_firefox_nightly'

    def __init__(self, os_name, browser_name, profiles):
        cmd = os.path.join(os.getenv('USERPROFILE'), LatestFxBrowserController.INSTALL_SUBDIR, 'firefox', 'firefox.exe')
        super(LatestFxBrowserController, self).__init__(os_name, browser_name, profiles, cmd)

    def init_browser(self):
        if self.os_name == 'windows':
            user_profile = os.getenv('USERPROFILE')
            install_path = os.path.join(user_profile, LatestFxBrowserController.INSTALL_SUBDIR)
            shutil.rmtree(install_path, ignore_errors=True)
            fxins = fxinstall.FirefoxInstaller(install_path)
            print 'Getting firefox nightly...'
            if not fxins.get_install():
                print 'Failed to get firefox nightly.'
        
    def launch(self, url=None):
        if self.os_name == 'windows':
            return super(LatestFxBrowserController, self).launch(url)
			
        print 'Nightly not yet supported on OSs other than Windows.'
        return False


class IEController(BrowserController):

    """ Specialization to deal with IE's registry settings. """

    def __init__(self, os_name, browser_name, cmd, args_tuple=()):
        super(IEController, self).__init__(os_name, browser_name, [], cmd, args_tuple)
        self.reg_backup = []
        self.key = _winreg.HKEY_CURRENT_USER
        self.subkey = 'Software\\Microsoft\\Internet Explorer\\Main'
        
    def backup_reg(self):
        hdl = _winreg.OpenKey(self.key, self.subkey)
        count = 0
        while True:
            try:
                self.reg_backup.append(_winreg.EnumValue(hdl, count))
            except WindowsError:
                break
            count += 1
        _winreg.CloseKey(hdl)

    def setup_reg(self):
        self.load_reg(ie_reg.registry_vals)
        new_win_path = 'Software\\Microsoft\\Internet Explorer\\New Windows'
        new_win_allow_path = new_win_path + '\\Allow'
        try:
            hdl = _winreg.OpenKey(self.key, new_win_allow_path, 0, _winreg.KEY_WRITE)
        except WindowsError:
            _winreg.CreateKey(self.key, new_win_allow_path)
            hdl = _winreg.OpenKey(self.key, new_win_allow_path, 0, _winreg.KEY_WRITE)
        _winreg.SetValueEx(hdl, 'brasstacks.mozilla.com', 0, 3, None)
        _winreg.CloseKey(hdl)
        
    def restore_reg(self):
        self.load_reg(self.reg_backup)
    
    def load_reg(self, keyvals):
        hdl = _winreg.OpenKey(self.key, self.subkey, 0, _winreg.KEY_WRITE)
        for i in keyvals:
            #print 'setting %s' % str(i)
            _winreg.SetValueEx(hdl, i[0], 0, i[2], i[1])
        _winreg.CloseKey(hdl)

    def terminate(self):
        super(IEController, self).terminate()
        self.restore_reg()

    def launch(self, url=None):
        self.backup_reg()
        self.setup_reg()
        return BrowserController.launch(self, url)
        
            
class BrowserControllerRedirFile(BrowserController):
    
    def __init__(self, os_name, browser_name, profile_path, cmd, args_tuple=()):
        super(BrowserControllerRedirFile, self).__init__(os_name, browser_name, profile_path, cmd, args_tuple)
        self.redir_file = None
    
    def cmd_line(self, url):
        self.redir_file = tempfile.NamedTemporaryFile(suffix='.html')
        self.redir_file.write('<html><head><meta HTTP-EQUIV="REFRESH" content="0; url=%s"></head></html>\n' % url)
        self.redir_file.flush()
        return super(BrowserControllerRedirFile, self).cmd_line(self.redir_file.name)
        

class BrowserRunner(object):

    @classmethod
    def browsers_by_os(cls, os_str):
        if os_str == 'Darwin':
            from Carbon import Folder, Folders
            lib_path = Folder.FSFindFolder(Folders.kUserDomain,
                                           Folders.kDomainLibraryFolderType,
                                           Folders.kDontCreateFolder).FSRefMakePath()
            app_supp_path = Folder.FSFindFolder(Folders.kUserDomain,
                                                Folders.kApplicationSupportFolderType,
                                                Folders.kDontCreateFolder).FSRefMakePath()

            os_name = 'osx'
            return [
                   BrowserController(os_name, 'firefox', os.path.join(app_supp_path, 'Firefox'),
                                   '/Applications/Firefox.app/Contents/MacOS/firefox'),
                   BrowserControllerRedirFile(os_name, 'safari', os.path.join(lib_path, 'Safari'),
                                            '/Applications/Safari.app/Contents/MacOS/Safari'),
                   BrowserController(os_name, 'opera', os.path.join(app_supp_path, 'Opera'),
                                   '/Applications/Opera.app/Contents/MacOS/Opera'),
                   BrowserController(os_name, 'chrome', os.path.join(app_supp_path, 'Google', 'Chrome'),
                                   '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
                   ]
        elif os_str == 'Linux':
            os_name = 'linux'
            return [
                   BrowserController(os_name, 'firefox', os.path.join(os.getenv('HOME'), '.mozilla', 'firefox'),
                                   '/usr/bin/firefox'),
                   BrowserController(os_name, 'opera', os.path.join(os.getenv('HOME'), '.opera'),
                                   '/usr/bin/opera'),
                   BrowserController(os_name, 'chrome', os.path.join(os.getenv('HOME'), '.config', 'google-chrome'),
                                   '/usr/bin/google-chrome')
                   ]
        elif os_str == 'Windows':
            os_name = 'windows'
            user_profile = os.getenv('USERPROFILE')
            app_data = os.getenv('APPDATA')
            local_app_data = os.getenv('LOCALAPPDATA')
            program_files = os.getenv('PROGRAMFILES')
            return [
                   BrowserController(os_name, 'firefox',
                                   [{'path': os.path.join(app_data, 'Mozilla\\Firefox'), 'archive': 'windows.zip'}],
                                   os.path.join(program_files, 'Mozilla Firefox\\firefox.exe')),
                   LatestFxBrowserController(os_name, 'nightly',
                                   [{'path': os.path.join(app_data, 'Mozilla\\Firefox'), 'archive': 'windows.zip'}]),
                   IEController(os_name, 'internet explorer', os.path.join(program_files, 'Internet Explorer\\iexplore.exe')),
                   BrowserController(os_name, 'safari',
                                   [{'path': os.path.join(local_app_data, 'Apple Computer\\Safari'), 'archive': 'windows\\local.zip'},
                                    {'path': os.path.join(app_data, 'Apple Computer\\Safari'), 'archive': 'windows\\roaming.zip'}],
                                    os.path.join(program_files, 'Safari\\Safari.exe')),
                   BrowserController(os_name, 'opera',
                                   [{'path': os.path.join(local_app_data, 'Opera\\Opera'), 'archive': 'windows\\local.zip'},
                                    {'path': os.path.join(app_data, 'Opera\\Opera'), 'archive': 'windows\\roaming.zip'}],
                                   os.path.join(program_files, 'Opera\\opera.exe')),
                   BrowserController(os_name, 'chrome',
                                   [{'path': os.path.join(local_app_data, 'Google\\Chrome\\User Data'), 'archive': 'windows.zip'}],
                                   os.path.join(user_profile, 'Local Settings\\Application Data\\Google\\Chrome\\Application\\chrome.exe'))
                   ]

    class BrowserControllerIter(object):
        
        def __init__(self, controllers, browser_names=[]):
            self.controllers = controllers
            self.browser_names = browser_names
            self.iter = iter(self.controllers)
        
        def __iter__(self):
            return self
        
        def next(self):
            while True:
                try:
                    n = self.iter.next()
                except StopIteration:
                    raise
                if not self.browser_names or n.browser_name in self.browser_names:
                    return n
                   
    def __init__(self, evt, browser_names=[], test_urls=[]):
        self.evt = evt
        self.test_urls = test_urls
        try:
            self.browsers = BrowserRunner.browsers_by_os(platform.system())
        except KeyError:
            sys.stderr.write('Unknown platform "%s".\n' % platform.system())
            sys.exit(errno.EOPNOTSUPP)
        self.browser_iter = BrowserRunner.BrowserControllerIter(self.browsers, browser_names)
        self.current_controller = None
        self.lock = threading.Lock()

    def find_browser(self, browsername):
        for b in self.browsers:
            if b.browser_name == browsername:
                return b
        print 'Unknown browser "%s".' % browsername
        return None
        
    def archive_current_profiles(self, browsername):
        b = self.find_browser(browsername)
        if b:
            b.archive_current_profiles()

    def launch(self, browsername, url):
        b = self.find_browser(browsername)
        if b:
            b.launch(url)
            
    def browser_running(self):
        self.lock.acquire()
        running = self.current_controller.running()
        self.lock.release()
        return running
    
    def execution_time(self):
        self.lock.acquire()
        t = self.current_controller.execution_time()
        self.lock.release()
        return t

    def browser_name(self):
        self.lock.acquire()
        browser_name = self.current_controller.browser_name
        self.lock.release()
        return browser_name

    def next_test(self):
        self.lock.acquire()
        need_to_launch = not self.current_controller or not self.current_controller.next_test()
        self.lock.release()
        if need_to_launch:
            self.launch_next_browser()

    def launch_next_browser(self):
        self.lock.acquire()
        if self.current_controller:
            print 'Closing browser...'
            self.current_controller.terminate()
            print '%s test running time: %s' % (self.current_controller.browser_name, self.current_controller.execution_time())
        while True:
            try:
                self.current_controller = self.browser_iter.next()
            except StopIteration:
                self.evt.set()
                self.lock.release()
                return
            self.current_controller.set_test_urls(self.test_urls)
            self.current_controller.init_browser()
            if self.current_controller.browser_exists():
                print 'Launching %s...' % self.current_controller.browser_name
                if self.current_controller.next_test():
                    break
                else:
                    print 'Failed to launch browser.'
        self.lock.release()


class TestRunnerHTTPServer(BaseHTTPServer.HTTPServer):
    
    def __init__(self, server_address, RequestHandlerClass, browser_runner):
        BaseHTTPServer.HTTPServer.__init__(self, server_address, RequestHandlerClass)
        self.browser_runner = browser_runner
        self.results = collections.defaultdict(lambda: collections.defaultdict(list))
    
    def standard_web_data(self):
        return {'ip': config.local_ip}
        

class TestRunnerRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    
    def do_GET(self):
        if self.path.startswith(config.local_test_base_path):
            try:
                url = config.server_html_url + self.path[len(config.local_test_base_path):]
                u = urllib2.urlopen(url)
            except urllib2.HTTPError, e:
                self.send_response(e.getcode())
            else:
                data = u.read()
                self.send_response(200)
                for header, value in u.info().items():
                    self.send_header(header, value)
                self.end_headers()
                self.wfile.write(data)
        else:
            self.send_response(404)

    def do_POST(self):
        length = int(self.headers.getheader('content-length'))
        web_data = json.loads(self.rfile.read(length))
        testname = web_data['testname']
        self.server.results[self.server.browser_runner.browser_name()][testname].extend(web_data['results'])
        if not config.testmode and not config.noresults:
            web_data.update(self.server.standard_web_data())
            raw_data = json.dumps(web_data)
            req = urllib2.Request(config.server_results_url, raw_data)
            req.add_header('Content-Type', 'application/json; charset=utf-8')
            req.add_header('Content-Length', len(raw_data))
            try:
                urllib2.urlopen(req)
            except urllib2.HTTPError, e:
                print '**ERROR sending results to server: %s' % e
                print
        self.send_response(200)
        self.end_headers()
        self.wfile.write('<html></html>')
        self.server.browser_runner.next_test()

    def log_message(self, format, *args):
        """ Suppress log output. """
        return


MAX_TEST_TIME = datetime.timedelta(seconds=60*10)
        
def main():
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option('-t', '--test', dest='tests', action='append', default=[])
    parser.add_option('--testmode', dest='testmode', action='store_true')
    parser.add_option('-n', '--noresults', dest='noresults', action='store_true')
    (options, args) = parser.parse_args()
    config.read(options.testmode, options.noresults)
    
    def get_browser_arg():
        try:
            browser = args[1]
        except IndexError:
            print 'Specify a browser.'
            sys.exit(errno.EINVAL)
        return browser
    
    evt = threading.Event()
    if len(args) >= 1 and args[0] == 'archive':
        browser = get_browser_arg()
        BrowserRunner(evt).archive_current_profiles(browser)
        sys.exit(0)
    elif len(args) >= 1 and args[0] == 'load':
        browser = get_browser_arg()
        BrowserRunner(evt).launch(browser, 'http://google.ca')
        sys.exit(0)
    
    # start tests in specified browsers.  if none given, run all.
    url_prefix = config.local_test_base_url + '/start.html?ip=%s&port=%d' % (config.local_ip, config.local_port)
    if config.testmode:
        url_prefix += '&test=true'
    url_prefix += '&testUrl='
    if not options.tests:
        print 'Getting test list from server...'
        try:
            tests_url = config.server_api_url + '/tests/'
            print 'Getting test list from %s...' % tests_url
            options.tests = json.loads(urllib2.urlopen(tests_url).read())
        except urllib2.HTTPError, e:
            sys.stderr.write('Could not get test list: %s\n' % e)
            sys.exit(errno.EPERM)
        except urllib2.URLError, e:
            sys.stderr.write('Could not get test list: %s\n' % e.reason)
            sys.exit(e.reason.errno)

    test_urls = map(lambda x: url_prefix + x, options.tests)
    br = BrowserRunner(evt, args, test_urls)
    trs = TestRunnerHTTPServer(('', config.local_port), TestRunnerRequestHandler, br)
    server_thread = threading.Thread(target=trs.serve_forever)
    server_thread.start()
    start = datetime.datetime.now()
    br.launch_next_browser()
    while not evt.is_set():
        if br.browser_running():
            if evt.is_set():
                # evt may have been set while we were waiting for the lock in browser_running().
                break
            if br.execution_time() > MAX_TEST_TIME:
                print 'Test has taken too long; starting next browser'
                br.launch_next_browser()
        else:
            print 'Browser isn\'t running!'
            br.launch_next_browser()
        evt.wait(5)
    trs.shutdown()
    server_thread.join()
    end = datetime.datetime.now()
    print ''
    print 'Done!'

    if not config.testmode:
        report = results.SpeedTestReport(trs.results)
        print
        print 'Start: %s' % start
        print 'Duration: %s' % (end - start)
        print 'Client: %s' % config.local_ip
        print
        print report.report()


if __name__ == '__main__':
    main()
