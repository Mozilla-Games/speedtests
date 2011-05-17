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
import zipfile

if platform.system() == 'Windows':
    import _winreg
    import ie_reg

import fxinstall
#import results

class Config(object):
    DEFAULT_CONF_FILE = 'speedtests.conf'
    
    def __init__(self):
        self.cfg = None
        self.local_port = 8111
        self.test_url = 'http://brasstacks.mozilla.com/speedtestssvr/start/?auto=true'
        self.cfg = None

    def read(self, testmode=False, conf_file=None):
        if not conf_file:
            conf_file = Config.DEFAULT_CONF_FILE
        self.cfg = ConfigParser.ConfigParser()
        self.cfg.read(conf_file)
        
        try:
            self.local_port = self.cfg.getint('speedtests', 'local_port')
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            pass
        
        try:
            self.test_url = self.cfg.get('speedtests', 'server_url').rstrip('/') + \
                                    '/start/?auto=true'
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            pass

        # We can also find out the address like this, supposedly more reliable:
        #s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        #s.connect((<TEST_HOST>, 80))
        #local_ip = s.getsockname()
        local_ip = socket.gethostbyname(socket.gethostname())
        if self.test_url.find('?') == -1:
            self.test_url += '?'
        else:
            self.test_url += '&'
        self.test_url += 'ip=%s&port=%d' % (local_ip, self.local_port)
        if testmode:
            self.test_url += '&test=true'


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
    
    def copy_profiles(self):
        if not self.browser_exists() or not self.profiles:
            return
        for p in self.profiles:
            profile_archive = self.get_profile_archive_path(p)
            if not os.path.exists(profile_archive):
                return
            if os.path.exists(p['path']):
                t = tempfile.mkdtemp()
                shutil.move(p['path'], t)
                p['previous_profile'] = os.path.join(t, os.path.basename(p['path']))
            else:
                p['previous_profile'] = ''
            try:
                os.mkdir(p['path'])
            except OSError:
                pass
            profile_zip = zipfile.ZipFile(profile_archive, 'r')
            profile_zip.extractall(p['path'])
    
    def clean_up(self):
        if not self.profiles:
            return
        for p in self.profiles:
            if not p['previous_profile']:
                continue
            shutil.rmtree(p['path'])
            shutil.move(p['previous_profile'], p['path'])
            os.rmdir(os.path.dirname(p['previous_profile']))

    def launch(self, url=None):
        self.copy_profiles()
        if not url:
            url = config.test_url
        cl = self.cmd_line(url)
        print 'Launching %s...' % ' '.join(cl)
        self.launch_time = datetime.datetime.now()
        self.proc = subprocess.Popen(cl)

    def running(self):
        running = self.proc and self.proc.poll()
        if running != None:
            self.proc = None
        return running == None
	
    def execution_time(self):
        return datetime.datetime.now() - self.launch_time

    def terminate(self):
        if self.proc:
            print 'terminating process'
            try:
                self.proc.terminate()
            except:  #FIXME
                pass
            for i in range(0, 5):
                print 'polling'
                if self.proc.poll() != None:
                    self.proc = None
                    break
                time.sleep(2)
            if self.proc:
                print 'killing process'
                try:
                    self.proc.kill()
                except:
                    pass
                print 'waiting for process to die'
                self.proc.wait()  # or poll and error out if still running?
                self.proc = None
            print 'process is dead'
        self.clean_up()


class LatestFxBrowserController(BrowserController):
    
    """ Specialization to download latest nightly before launching. """
    
    INSTALL_SUBDIR = 'speedtests_firefox_nightly'
    
    def launch(self):
        if self.os_name == 'windows':
            user_profile = os.getenv('USERPROFILE')
            fxins = fxinstall.FirefoxInstaller(user_profile)
            shutil.rmtree(os.path.join(user_profile, LatestFxBrowserController.INSTALL_SUBDIR), ignore_errors=True)
            print 'Getting firefox nightly...'
            if fxins.get_install():
                cmd = os.path.join(user_profile, LatestFxBrowserController.INSTALL_SUBDIR, 'firefox.exe')
                super(LatestFxBrowserController, self).launch()
            else:
                print 'Failed to get firefox nightly.'
        else:
            print 'Nightly not yet supported on OSs other than Windows.'


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

    def launch(self):
        self.backup_reg()
        self.setup_reg()
        super(IEController, self).launch()
        
            
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
                                   [{'path': os.path.join(app_data, 'Mozilla\\Firefox'), 'archive': 'windows.zip'}],
                                   os.path.join(program_files, 'Mozilla Firefox\\firefox.exe')),
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
                   
    def __init__(self, evt, browser_names, testmode=False):
        self.evt = evt
        self.testmode = testmode
        try:
            self.browsers = BrowserRunner.browsers_by_os(platform.system())
        except KeyError:
            sys.stderr.write('Unknown platform "%s".\n' % platform.system())
            sys.exit(errno.EOPNOTSUPP)
        self.browser_iter = BrowserRunner.BrowserControllerIter(self.browsers, browser_names)
        self.current_controller = None
        self.proc = None
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

    def launch_next_browser(self):
        self.lock.acquire()
        if self.current_controller:
            self.current_controller.terminate()
            print 'Test running time: %s' % self.current_controller.execution_time()

        while True:
            try:
                self.current_controller = self.browser_iter.next()
            except StopIteration:
                self.evt.set()
                self.lock.release()
                return
            if self.current_controller.browser_exists():
                break

        self.proc = self.current_controller.launch()
        self.lock.release()


class TestRunnerHTTPServer(BaseHTTPServer.HTTPServer):
    
    def __init__(self, server_address, RequestHandlerClass, browser_runner):
        BaseHTTPServer.HTTPServer.__init__(self, server_address, RequestHandlerClass)
        self.browser_runner = browser_runner
        self.results = collections.defaultdict(lambda: collections.defaultdict(list))


class TestRunnerRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    
    def do_GET(self):
        # Indicates that the tests on the current browser have finished.
        print 'got pingback'
        self.server.browser_runner.launch_next_browser()
        text = '<html><body>Done tests; launching next browser...</body></html>'
        try:
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.send_header('Content-Length', str(len(text)))
            self.end_headers()
            self.wfile.write(text)
        except socket.error:
            # Browser was probably closed before we could send the response
            pass

    def do_POST(self):
        # Parse the form data posted
        form = cgi.FieldStorage(
            fp=self.rfile, 
            headers=self.headers,
            environ={'REQUEST_METHOD':'POST',
                     'CONTENT_TYPE':self.headers['Content-Type'],
                     })

        # record results
        web_data = json.loads(form['body'].value)
        testname = web_data['testname']
        self.server.results[self.server.browser_runner.browser_name()][testname].append(web_data['results'])
        self.send_response(200)
        self.end_headers()
        self.wfile.write('<html></html>')

    def read_data(self):
        data = ''
        while True:
            buf = self.rfile.read()
            if buf == '':
                break
            data += buf
        return data


MAX_TEST_TIME = datetime.timedelta(seconds=60*10)
        
def main():
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option('-t', '--test', dest='testmode', action='store_true')
    (options, args) = parser.parse_args()
    config.read(options.testmode)
    
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
    br = BrowserRunner(evt, args)
    trs = TestRunnerHTTPServer(('', config.local_port), TestRunnerRequestHandler, br)
    server_thread = threading.Thread(target=trs.serve_forever)
    server_thread.start()
    br.launch_next_browser()
    while not evt.is_set():
        if br.browser_running():
            if br.execution_time() > MAX_TEST_TIME:
                print 'test has taken too long; starting next browser'
                br.launch_next_browser()
        else:
            print 'browser isn\'t running!'
            br.launch_next_browser()
        evt.wait(5)
    trs.shutdown()
    server_thread.join()
    print 'Done!'
    #report = results.SpeedTestReport(trs.results)
    #print 'Test results:'
    #print ''
    #print report.report()


if __name__ == '__main__':
    main()
