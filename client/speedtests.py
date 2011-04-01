import BaseHTTPServer
import ConfigParser
import errno
import os
import platform
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import _winreg
import zipfile

import ie_reg


DEFAULT_CONF_FILE = 'speedtests.conf'
cfg = ConfigParser.ConfigParser()
cfg.read(DEFAULT_CONF_FILE)
try:
    TEST_URL = cfg.get('speedtests', 'server_url').rstrip('/') + \
               '/start/?auto=true'
except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
    TEST_URL = 'http://brasstacks.mozilla.com/speedtestssvr/start/?auto=true'

# We can also find out the address like this, supposedly more reliable:
#s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#s.connect((<TEST_HOST>, 80))
#local_ip = s.getsockname()
local_ip = socket.gethostbyname(socket.gethostname())
if TEST_URL.find('?') == -1:
    TEST_URL += '?'
else:
    TEST_URL += '&'
TEST_URL += 'ip=%s' % local_ip


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
            self.profiles.append(p)
        self.cmd = cmd
        self.args_tuple = args_tuple
        self.proc = None
        try:
            self.cmd = cfg.get(os_name, browser_name)
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            pass

    def cmd_line(self, url=TEST_URL):
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

    def launch(self):
        self.copy_profiles()
        cl = self.cmd_line()
        print 'Launching %s...' % ' '.join(cl)
        self.proc = subprocess.Popen(cl)

    def running(self):
        running = self.proc and self.proc.poll()
        if running != None:
            self.proc = None
        return running == None

    def terminate(self):
        if self.proc:
            print 'terminating process'
            self.proc.terminate()
            for i in range(0, 5):
                print 'polling'
                if self.proc.poll() != None:
                    self.proc = None
                    break
                time.sleep(2)
            if self.proc:
                print 'killing process'
                self.proc.kill()
                print 'waiting for process to die'
                self.proc.wait()  # or poll and error out if still running?
                self.proc = None
            print 'process is dead'
        self.clean_up()


class IEController(BrowserController):

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
    
    def cmd_line(self, url=TEST_URL):
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

    def __init__(self, evt):
        self.evt = evt
        try:
            self.browsers = BrowserRunner.browsers_by_os(platform.system())
        except KeyError:
            sys.stderr.write('Unknown platform "%s".\n' % platform.system())
            sys.exit(errno.EOPNOTSUPP)
        self.browser_iter = iter(self.browsers)
        self.current_launcher = None
        self.proc = None
        self.lock = threading.Lock()
    
    def archive_current_profiles(self, browsername):
        for b in self.browsers:
            if b.browser_name == browsername:
                b.archive_current_profiles()
                return
        print 'Unknown browser "%s".' % browsername
    
    def browser_running(self):
        self.lock.acquire()
        running = self.current_launcher.running()
        self.lock.release()
        return running

    def launch_next_browser(self):
        self.lock.acquire()
        if self.current_launcher:
            self.current_launcher.terminate()

        while True:
            try:
                self.current_launcher = self.browser_iter.next()
            except StopIteration:
                self.evt.set()
                self.lock.release()
                return
            if self.current_launcher.browser_exists():
                break

        self.proc = self.current_launcher.launch()
        self.lock.release()


class TestRunnerHTTPServer(BaseHTTPServer.HTTPServer):
    
    def __init__(self, server_address, RequestHandlerClass, browser_runner):
        BaseHTTPServer.HTTPServer.__init__(self, server_address, RequestHandlerClass)
        self.browser_runner = browser_runner


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


def main():
    evt = threading.Event()
    br = BrowserRunner(evt)
    if len(sys.argv) > 1 and sys.argv[1] == 'archive':
        try:
            browser = sys.argv[2]
        except IndexError:
            print 'Specify a browser.'
            sys.exit(errno.EINVAL)
        br.archive_current_profiles(browser)
        sys.exit(0)
            
    trs = TestRunnerHTTPServer(('', 8111), TestRunnerRequestHandler, br)
    server_thread = threading.Thread(target=trs.serve_forever)
    server_thread.start()
    br.launch_next_browser()
    while not evt.is_set():
        if not br.browser_running():
            print 'browser isn\'t running!'
            br.launch_next_browser()
        evt.wait(5)
    trs.shutdown()
    server_thread.join()
    print 'Done!'


if __name__ == '__main__':
    main()
