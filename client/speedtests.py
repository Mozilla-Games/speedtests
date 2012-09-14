# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

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
import traceback
import urllib
import urllib2
import zipfile

from get_latest import GetLatestTinderbox
from mozdevice import DroidADB, DroidSUT, DroidConnectByHWID

if platform.system() == 'Windows':
    import _winreg
    import ie_reg

import fxinstall
import results

try:
    import jwt
except ImportError:
    pass

class Config(object):
    DEFAULT_CONF_FILE = 'speedtests.conf'
    
    def __init__(self):
        self.cfg = None
        self.sixtyfour_bit = False
        self.local_port = 8111
        self.server_html_url = 'http://brasstacks.mozilla.com/speedtests'
        self.server_api_url = 'http://brasstacks.mozilla.com/speedtests/api'
        self.local_test_base_path = ''
        self.ignore = False
        self.platform = platform.system()

    @property
    def local_test_base_url(self):
        #return self.server_html_url + self.local_test_base_path
        # IE has issues loading pages from localhost, so we'll use the
        # external IP.
        return 'http://%s:%d%s' % (self.local_ip, self.local_port, self.local_test_base_path)

    def read(self, testmode=False, noresults=False, ignore=False,
             conf_file=None):
        self.testmode = testmode
        self.noresults = noresults
        self.ignore = ignore
        if not conf_file:
            conf_file = Config.DEFAULT_CONF_FILE
        self.cfg = ConfigParser.ConfigParser()
        self.cfg.read(conf_file)

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            self.local_ip = s.getsockname()[0]
            s.close()
        except:
            raise Exception("Couldn't find local IP!")

        try:
            self.sixtyfour_bit = self.cfg.getboolean('speedtests', '64bit')
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            pass
        
        try:
            self.local_port = self.cfg.getint('speedtests', 'local_port')
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            pass
        
        try:
            self.server_html_url = self.cfg.get('speedtests', 'test_base_url').rstrip('/').replace("SELF_IP", self.local_ip)
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            pass

        try:
            self.server_api_url = self.cfg.get('speedtests', 'server_url').rstrip('/').replace("SELF_IP", self.local_ip)
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            self.server_api_url = self.server_html_url + '/api'

        try:
            self.server_results_url = self.cfg.get('speedtests', 'server_results_url').rstrip('/').replace("SELF_IP", self.local_ip) + '/'
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            self.server_results_url = self.server_api_url + '/testresults/'

        try:
            self.platform = self.cfg.get('speedtests', 'platform')
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            pass

        self.client = self.get_str('speedtests', 'client')
        if self.client is None:
            self.client = self.local_ip

    def get_str(self, section, param, default=None):
        try:
            val = self.cfg.get(section, param)
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            val = default
        return val

config = Config()

class BrowserController(object):

    AppVersion = None
    AppBuildID = None
    AppSourceRepository = None
    AppSourceStamp = None
    NameExtra = None
    
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
        self.cmd_args = tuple()
        self.args_tuple = args_tuple
        self.proc = None
        self.launch_time = None
        try:
            self.cmd = config.cfg.get(os_name, browser_name)
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            pass

        args = config.get_str(os_name, browser_name + "_args")
        if args is not None:
            self.cmd_args = tuple(args.split())

        self.NameExtra = config.get_str(os_name, browser_name + "_suffix")

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
        return (self.cmd,) + self.cmd_args + self.args_tuple + (url,)

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
            if not os.path.exists(os.path.dirname(profile_archive)):
                os.makedirs(os.path.dirname(profile_archive))
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
                print 'Warning: no archived profile'
                return True
            if os.path.exists(p['path']):
                attempts = 0
                while attempts < 3:
                    if attempts > 0:
                        time.sleep(5)
                    try:
                        shutil.rmtree(p['path'])
                    except (OSError, WindowsError):
                        print 'Failed to remove profile:'
                        traceback.print_exc()
                        attempts += 1
                    else:
                        break
                if attempts == 3:
                    print 'Couldn\'t remove profile; giving up.'
                    return False
            try:
                os.mkdir(p['path'])
            except OSError:
                pass
            profile_zip = zipfile.ZipFile(profile_archive, 'r')
            print 'Copying profile to %s...' % p['path']
            profile_zip.extractall(p['path'])
        return True
    
    def clean_up(self):
        pass

    def launch(self, url=None):
        if not self.copy_profiles():
            print 'Failed to copy profiles'
            return False
        if not url:
            url = config.test_url
        cl = self.cmd_line(url)
        print '  command line: %s...' % ' '.join(cl)
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
        if self.launch_time:
            return datetime.datetime.now() - self.launch_time
        return MAX_TEST_TIME * 2

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

    def parse_app_ini(self, appini):
        ini = ConfigParser.ConfigParser()
        ini.read(appini)

        self.AppVersion = ini.get('App', 'Version')
        self.AppBuildID = ini.get('App', 'BuildID')
        self.AppSourceRepository = ini.get('App', 'SourceRepository')
        self.AppSourceStamp = ini.get('App', 'SourceStamp')

class AndroidBrowserController(BrowserController):
    def __init__(self, os_name, browser_name, package='org.mozilla.fennec', activity='.App', hwid=None):
        super(AndroidBrowserController, self).__init__(os_name, browser_name, "default", None)
        self.browserPackage = config.get_str('android', browser_name + '_package', package)
        self.browserActivity = config.get_str('android', browser_name + '_activity', activity)
        if hwid is None:
            hwid = os.getenv("DM_HWID")
        if hwid is None:
            self.dm = DroidADB(packageName=package, skipRoot=True)
        else:
            self.dm = DroidConnectByHWID(hwid, packageName=package, skipRoot=True)

    def cmd_line(self, url):
        pass

    def init_browser(self):
        pass

    def browser_exists(self):
        # XXX fixme to check
        return True

    def get_profile_archive_path(self, profile):
        raise Exception("Can't get profile archive for Android fennec browser")

    def archive_current_profiles(self):
        raise Exception("Can't get profile archive for Android fennec browser")

    def copy_profiles(self):
        print "Skipping profile copy on Android"
        return True

    def launch(self, url=None):
        try:
            # simulate a press of the HOME button, to wake screen up if necessary
            self.dm.shell(["input", "keyevent", "3"], None)

            if url is None:
                url = "about:blank"
            
            #print "ADB Launch command line: %s" % (cmdline)
            self.launch_time = datetime.datetime.now()
            return self.dm.launchApplication(self.browserPackage, self.browserActivity, "android.intent.action.VIEW", url=url)
        except:
            traceback.print_exc()
            return False

    def getBrowserPid(self):
        result = self.dm.processExist(self.browserPackage)
        if result is not None:
            return result
        return -1

    def running(self):
        return self.getBrowserPid() > 0

    def terminate(self):
        print "Trying to terminate browser..."
        pid = self.getBrowserPid()
        if pid < 0:
            return

        # the killProcess implementaiton is not ideal; requires root or run-as
        #self.dm.killProcess(self.browserPackage, forceKill=True)

        needRoot = False
        if type(self.dm) is DroidSUT:
            needRoot = True

        self.dm.shell(["am", "force-stop", self.browserPackage], None, root=needRoot)
        time.sleep(1)
        self.dm.shell(["am", "kill", self.browserPackage], None, root=needRoot)

        pid = self.getBrowserPid()
        count = 0
        while pid > 0:
            time.sleep(2)
            pid = self.getBrowserPid()
            count += 1
            if count == 20:
                raise Exception("Waited too long for browser to die!")
        self.clean_up()

class AndroidAdbBrowserController(BrowserController):
    def __init__(self, os_name, browser_name, package='org.mozilla.fennec'):
        super(AndroidAdbBrowserController, self).__init__(os_name, browser_name, "default", None)
        self.browserPackage = config.get_str('android', browser_name + '_package', package)

    def cmd_line(self, url):
        pass

    def init_browser(self):
        pass

    def browser_exists(self):
        # XXX fixme to check
        return True

    def get_profile_archive_path(self, profile):
        raise Exception("Can't get profile archive for Android fennec browser")

    def archive_current_profiles(self):
        raise Exception("Can't get profile archive for Android fennec browser")

    def copy_profiles(self):
        print "Skipping profile copy on Android"
        return True

    def launch(self, url=None):
        try:
            # simulate a press of the HOME button, to wake screen up if necessary
            subprocess.check_call("adb shell input keyevent 3", shell=True)

            if url is None:
                url = "about:blank"
            cmdline = "adb shell am start -a android.intent.action.VIEW -d '\"%s\"' %s" % (url, self.browserPackage)
            #print "ADB Launch command line: %s" % (cmdline)
            self.launch_time = datetime.datetime.now()
            subprocess.check_call(cmdline, shell=True)
            return True
        except:
            traceback.print_exc()
            return False

    def getBrowserPid(self):
        try:
            # grep -v is for chrome
            result = subprocess.check_output("adb shell ps | grep %s | grep -v sandbox | tail -1" % self.browserPackage, shell=True)
            result = result.split()
            if result[0] == "USER":
                return -1
            return int(result[1])
        except:
            traceback.print_exc()
            return -1

    def running(self):
        return self.getBrowserPid() > 0

    def terminate(self):
        pid = self.getBrowserPid()
        if pid < 0:
            return

        subprocess.call("adb shell am force-stop %s" % (self.browserPackage), shell=True)
        time.sleep(1)
        subprocess.call("adb shell am kill %s" % (self.browserPackage), shell=True)

        pid = self.getBrowserPid()
        count = 0
        while pid > 0:
            time.sleep(2)
            pid = self.getBrowserPid()
            count += 1
            if count == 20:
                raise Exception("Waited too long for browser to die!")
        self.clean_up()

class LatestFxBrowserController(BrowserController):
    
    """ Specialization to download latest nightly before launching. """

    # FIXME: if we fail to contact ftp.mozilla.org, recover gracefully
    
    INSTALL_SUBDIR = 'speedtests_firefox_nightly'

    # override these
    ARCHIVE_FX_PATH = ''
    INSTALLER_CLASS = None

    def __init__(self, os_name, browser_name, profiles, base_install_dir):
        self.base_install_dir = os.path.join(base_install_dir, config.client)
        cmd = os.path.join(self.base_install_dir,
                           LatestFxBrowserController.INSTALL_SUBDIR,
                           self.ARCHIVE_FX_PATH)
        super(LatestFxBrowserController, self).__init__(os_name, browser_name, profiles, cmd)

    def init_browser(self):
        install_path = os.path.join(self.base_install_dir,
                                    LatestFxBrowserController.INSTALL_SUBDIR)
        installer = self.INSTALLER_CLASS(install_path, config.sixtyfour_bit)
        print 'Getting firefox nightly...'
        if not installer.get_install():
            print 'Failed to get firefox nightly.'
            return False
        try:
            self.parse_app_ini(os.path.join(install_path, 'firefox', 'application.ini'))
        except:
            pass
        return True

class LatestTinderboxFxBrowserController(BrowserController):
    
    """ Specialization to download latest tinderbox build before launching. """

    # FIXME: if we fail to contact ftp.mozilla.org, recover gracefully
    
    INSTALL_SUBDIR = 'speedtests_firefox_tb'

    # override these
    ARCHIVE_FX_PATH = None
    PLATFORM = None

    # maybe override these
    BUILDTYPE = None   # "debug", "pgo", ...

    # filled out from application.ini
    AppVersion = None
    AppBuildID = None
    AppSourceRepository = None
    AppSourceStamp = None

    def __init__(self, os_name, browser_name, profiles, base_install_dir, branch='mozilla-central'):
        self.base_install_dir = os.path.join(base_install_dir, config.client)
        self.branch = branch
        cmd = os.path.join(self.base_install_dir,
                           self.INSTALL_SUBDIR,
                           self.ARCHIVE_FX_PATH)
        super(LatestTinderboxFxBrowserController, self).__init__(os_name, browser_name, profiles, cmd)

    def init_browser(self):
        install_path = os.path.join(self.base_install_dir, self.INSTALL_SUBDIR)
        latest = GetLatestTinderbox(self.branch, self.PLATFORM, buildtype=self.BUILDTYPE, app='firefox', app_short='firefox')
        latest_url = latest.latest_build_url()
        basename = latest_url[latest_url.rfind("/")+1:]

        try:
            shutil.rmtree(install_path)
        except:
            pass

        os.makedirs(install_path)

        try:
            print "Fetching " + latest_url + "..."
            urllib.urlretrieve(latest_url, os.path.join(install_path, basename))
        except Exception as e:
            print 'Failed to get latest tinderbox build'
            print e
            return False

        appini = self.prepare_archived_build(install_path, os.path.join(install_path, basename))
        if appini is None:
            return False

        self.parse_app_ini(appini)
        return True

class LinuxLatestTinderboxFxBrowserController(LatestTinderboxFxBrowserController):
    ARCHIVE_FX_PATH = 'firefox/firefox'
    PLATFORM = 'linux'
    BUILDTYPE = 'pgo'

    def __init__(self, os_name, browser_name, profiles, base_install_dir, branch='mozilla-central'):
        super(LinuxLatestTinderboxFxBrowserController, self).__init__(os_name, browser_name, profiles, base_install_dir, branch)

    def prepare_archived_build(self, install_path, buildpath):
        # on linux, this is a bz2 file
        try:
            subprocess.check_call("cd '" + install_path + "' && tar xjf '" + buildpath + "'", shell=True)
            return os.path.join(install_path, "firefox", "application.ini")
        except Exception as e:
            print "Failed to unpack:"
            print e
            return None

class WinLatestTinderboxFxBrowserController(LatestTinderboxFxBrowserController):
    ARCHIVE_FX_PATH = 'firefox\\firefox.exe'
    PLATFORM = 'win32'
    BUILDTYPE = 'pgo'

    def __init__(self, os_name, browser_name, profiles, base_install_dir, branch='mozilla-central'):
        super(WinLatestTinderboxFxBrowserController, self).__init__(os_name, browser_name, profiles, base_install_dir, branch)

    def prepare_archived_build(self, install_path, buildpath):
        # on windows, this is a zip file
        cwd = os.getcwd()
        try:
            fn = os.path.basename(buildpath)
            os.chdir(install_path)
            print "chdir to " + install_path + " cwd now " + os.getcwd()
            subprocess.check_call("unzip -q \"%s\"" % (fn), shell=True)
            return os.path.join(install_path, "firefox", "application.ini")
        except Exception as e:
            print "Failed to unpack:"
            print e
            return None
        finally:
            os.chdir(cwd)

class AndroidTinderboxFxBrowserController(AndroidBrowserController):
    INSTALL_SUBDIR = 'speedtests_fennec_tb'

    def __init__(self, os_name, browser_name, branch='mozilla-central'):
        # explicitly not using super()
        AndroidBrowserController.__init__(self, os_name, browser_name)

        # stuff from LatestTinderboxFxBrowserController.__init__
        self.base_install_dir = os.path.join("/tmp", config.client)
        self.branch = branch

    def init_browser(self):
        install_path = os.path.join(self.base_install_dir, self.INSTALL_SUBDIR)

        try:
            shutil.rmtree(install_path)
        except:
            pass
        os.makedirs(install_path)

        latest = GetLatestTinderbox(self.branch, "android", app='mobile', app_short='fennec')
        latest_url = latest.latest_build_url()
        basename = latest_url[latest_url.rfind("/")+1:]

        apkpath = os.path.join(install_path, basename)

        try:
            print "Fetching " + latest_url + "..."
            urllib.urlretrieve(latest_url, apkpath)
        except Exception as e:
            print 'Failed to get latest tinderbox build'
            print e
            return False

        # pull out app.ini and parse it
        zip = zipfile.ZipFile(apkpath, 'r')
        zip.extract("application.ini", install_path)
        self.parse_app_ini(os.path.join(install_path, "application.ini"))

        # now install the apk
        return self.dm.installLocalApp(apkpath)

    def clean_up(self):
        # leave the browser on there for easier testing.  no reason to nuke it, especially since
        # we're keeping the prefs.
        # XXX and especially since SUT forces a reboot on uninstall
        # self.dm.uninstallAppAndReboot(self.browserPackage)
        return True

class LinuxLatestFxBrowserController(LatestFxBrowserController):

    ARCHIVE_FX_PATH = 'firefox/firefox'
    INSTALLER_CLASS = fxinstall.FirefoxLinuxInstaller

class WinLatestFxBrowserController(LatestFxBrowserController):

    ARCHIVE_FX_PATH = 'firefox\\firefox.exe'
    INSTALLER_CLASS = fxinstall.FirefoxWinInstaller


class MacLatestFxBrowserController(LatestFxBrowserController):

    ARCHIVE_FX_PATH = 'FirefoxNightly.app/Contents/MacOS/firefox'
    INSTALLER_CLASS = fxinstall.FirefoxMacInstaller

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
                   BrowserController(os_name, 'firefox',
                                     os.path.join(app_supp_path, 'Firefox'),
                                     '/Applications/Firefox.app/Contents/MacOS/firefox'),
                   MacLatestFxBrowserController(os_name, 'nightly',
                                                os.path.join(app_supp_path, 'Firefox'),
                                                os.getenv('HOME')),
                   BrowserControllerRedirFile(os_name, 'safari',
                                              os.path.join(lib_path, 'Safari'),
                                              '/Applications/Safari.app/Contents/MacOS/Safari'),
                   BrowserController(os_name, 'opera', 
                                     [{'path': os.path.join(app_supp_path, 'Opera'), 'archive': 'osx_app_supp.zip'},
                                      {'path': os.path.join(lib_path, 'Opera'), 'archive': 'osx_lib.zip'}],
                                     '/Applications/Opera.app/Contents/MacOS/Opera'),
                   BrowserController(os_name, 'chrome',
                                     os.path.join(app_supp_path, 'Google', 
                                                  'Chrome'),
                                   '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
                   ]
        elif os_str == 'Linux':
            os_name = 'linux'
            return [
                   BrowserController(os_name, 'firefox', os.path.join(os.getenv('HOME'), '.mozilla', 'firefox'),
                                   '/usr/bin/firefox'),
                   LinuxLatestFxBrowserController(os_name, 'nightly', os.path.join(os.getenv('HOME'), '.mozilla', 'firefox'), '/tmp'),
                   BrowserController(os_name, 'opera', os.path.join(os.getenv('HOME'), '.opera'),
                                   '/usr/bin/opera'),
                   BrowserController(os_name, 'chrome', os.path.join(os.getenv('HOME'), '.config', 'google-chrome'),
                                   '/usr/bin/google-chrome'),
                   LinuxLatestTinderboxFxBrowserController(os_name, 'tinderbox',
                                                           os.path.join(os.getenv('HOME'), '.mozilla'),
                                                           "/tmp", "mozilla-central")
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
                   WinLatestFxBrowserController(os_name, 'nightly',
                                   [{'path': os.path.join(app_data, 'Mozilla\\Firefox'), 'archive': 'windows.zip'}], user_profile),
                   WinLatestTinderboxFxBrowserController(os_name, 'tinderbox',
                                                         [{'path': os.path.join(app_data, 'Mozilla\\Firefox'), 'archive': 'windows.zip'}],
                                                         os.getenv('TEMP'), "mozilla-central"),
                   BrowserController(os_name, 'chrome',
                                   [{'path': os.path.join(local_app_data, 'Google\\Chrome\\User Data'), 'archive': 'windows.zip'}],
                                   os.path.join(user_profile, 'Local Settings\\Application Data\\Google\\Chrome\\Application\\chrome.exe'))

                   # don't care about these
                   # BrowserController(os_name, 'safari',
                   #                [{'path': os.path.join(local_app_data, 'Apple Computer\\Safari'), 'archive': 'windows\\local.zip'},
                   #                 {'path': os.path.join(app_data, 'Apple Computer\\Safari'), 'archive': 'windows\\roaming.zip'}],
                   #                 os.path.join(program_files, 'Safari\\Safari.exe')),
                   # BrowserController(os_name, 'opera',
                   #                [{'path': os.path.join(local_app_data, 'Opera\\Opera'), 'archive': 'windows\\local.zip'},
                   #                 {'path': os.path.join(app_data, 'Opera\\Opera'), 'archive': 'windows\\roaming.zip'}],
                   #                os.path.join(program_files, 'Opera\\opera.exe')),
                   # IEController(os_name, 'internet explorer', os.path.join(program_files, 'Internet Explorer\\iexplore.exe')),
                   ]
        elif os_str == 'android':
            return [
                AndroidBrowserController(os_str, 'firefox'),
                #AndroidLatestFxAdbBrowserController(os_str, 'nightly'),
                AndroidTinderboxFxBrowserController(os_str, 'tinderbox'),
                AndroidBrowserController(os_str, 'browser', 'com.google.android.browser'),
                AndroidBrowserController(os_str, 'chrome', 'com.android.chrome', activity='com.google.android.apps.chrome.Main')
                   ]
        else:
            raise Exception("Unrecognized platform '%s'" % (os_str))

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
                   
    def __init__(self, evt, browser_names=[], test_urls=[], platform_system=platform.system()):
        self.evt = evt
        self.test_urls = test_urls
        try:
            self.browsers = BrowserRunner.browsers_by_os(platform_system)
        except KeyError:
            sys.stderr.write('Unknown platform "%s".\n' % platform_system)
            sys.exit(errno.EOPNOTSUPP)
        self.browser_names = browser_names
        self.current_controller = None
        self.lock = threading.Lock()
        self.reset()

    def reset(self):
        self.lock.acquire()
        if self.current_controller:
            self.current_controller.terminate()
        self.current_controller = None
        self.browser_iter = BrowserRunner.BrowserControllerIter(self.browsers, self.browser_names)
        self.lock.release()

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
    
    def __init__(self, server_address, RequestHandlerClass, browser_runner,
                 signing_key=None):
        BaseHTTPServer.HTTPServer.__init__(self, server_address, RequestHandlerClass)
        self.browser_runner = browser_runner
        self.results = collections.defaultdict(lambda: collections.defaultdict(list))
        self.signer = None
        if signing_key:
            self.signer = jwt.jws.HmacSha(key=signing_key,
                                          key_id=config.local_ip)
    
    def standard_web_data(self):
        return {'ip': config.local_ip, 'client': config.client}

    def handle_error(self, request, client_address):
        print '-'*40
        print 'Exception happened during processing of request from', client_address
        traceback.print_exc() # XXX But this goes to stderr!
        print '-'*40

        # must use os._exit, otherwise this won't actually exit (sys.exit is
        # implemented by throwing an exception)
        os._exit(1)

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
            print "Invalid URL request: " + self.path
            self.send_response(404)

    def do_POST(self):
        length = int(self.headers.getheader('content-length'))
        web_data = json.loads(self.rfile.read(length))

        # if this was skipped, we've got nothing to do
        if 'test_skipped' in web_data and web_data['test_skipped']:
            print "Test was skipped."
            self.send_response(200)
            self.end_headers()
            self.wfile.write('<html></html>')
            self.server.browser_runner.next_test()
            return

        if config.ignore:
            web_data['ignore'] = True
        testname = web_data['testname']
        self.server.results[self.server.browser_runner.browser_name()][testname].extend(web_data['results'])
        if not config.testmode and not config.noresults:
            web_data.update(self.server.standard_web_data())
            if self.server.browser_runner.current_controller.AppSourceStamp:
                web_data['sourcestamp'] = self.server.browser_runner.current_controller.AppSourceStamp
            if self.server.browser_runner.current_controller.AppBuildID:
                web_data['buildid'] = self.server.browser_runner.current_controller.AppBuildID
            if self.server.browser_runner.current_controller.NameExtra:
                web_data['name_extra'] = self.server.browser_runner.current_controller.NameExtra

            if self.server.signer:
                raw_data = jwt.encode(web_data, signer=self.server.signer)
                content_type = 'application/jwt'
            else:
                raw_data = json.dumps(web_data)
                content_type = 'application/json; charset=utf-8'
            req = urllib2.Request(config.server_results_url, raw_data)
            req.add_header('Content-Type', content_type)
            req.add_header('Content-Length', len(raw_data))

            try:
                response = json.loads(urllib2.urlopen(req).read())
            except (urllib2.URLError, urllib2.HTTPError):
                print '**ERROR sending results to server:'
                traceback.print_exc()
                print
            else:
                if response['result'] == 'ok':
                    print 'Results submitted to server.'
                else:
                    print '**ERROR sending results to server: %s' % \
                        response['error']
        self.send_response(200)
        self.end_headers()
        self.wfile.write('<html></html>')
        self.server.browser_runner.next_test()

    def log_message(self, format, *args):
        """ Suppress log output. """
        return


MAX_TEST_TIME = datetime.timedelta(seconds=60*15)
        
def main():
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option('-f', '--config', dest='config_file', type='string', action='store', default=None,
                      help='config file (default speedtests.conf)')
    parser.add_option('-t', '--test', dest='tests', action='append', default=[])
    parser.add_option('--testmode', dest='testmode', action='store_true')
    parser.add_option('-n', '--noresults', dest='noresults',
                      action='store_true')
    parser.add_option('-s', '--sign', dest='sign', type='string', action='store',
                      help='sign results with key in given file')
    parser.add_option('--ignore', dest='ignore', action='store_true',
                      help='instruct server to ignore results')
    parser.add_option('--client', dest='client', type='string', action='store',
                     help='override client name reported to server')
    parser.add_option('--platform', dest='platform', type='string', action='store',
                     help='override detected platform')
    parser.add_option('--port', dest='local_port', type='int', action='store',
                     help='override local_port')
    parser.add_option('--cycles', dest='cycles', type='int', default=1, action='store',
                      help='number of cycles to run, default 1, -1 to run forever')
    parser.add_option('--forever', dest='cycles', const=-1, action='store_const',
                      help='run forever')
    parser.add_option('--nap_after', dest='nap_after', type='int', default=0, action='store',
                      help='take a break after this many cycles (0=never)')
    parser.add_option('--nap_time', dest='nap_time', type='int', default=15*60, action='store',
                      help='duration of nap, in seconds')

    (options, args) = parser.parse_args()

    config.read(options.testmode, options.noresults, options.ignore, options.config_file)

    if options.client:
        config.client = options.client

    if options.local_port:
        config.local_port = options.local_port

    if not options.client and not config.get_str('speedtests', 'client'):
        print "--client must be specified on command line or in config (we don't support ip-based clients here)"
        sys.exit(errno.EINVAL)

    if options.platform:
        config.platform = options.platform
    
    def get_browser_arg():
        try:
            browser = args[1]
        except IndexError:
            print 'Specify a browser.'
            sys.exit(errno.EINVAL)
        return browser

    key = None
    if options.sign:
        try:
            import jwt
        except ImportError:
            print >>sys.stderr, 'jwt module required for signing'
            sys.exit(errno.EINVAL)
        try:
            key = file(options.sign, 'r').read().strip()
        except IOError, e:
            print >>sys.stderr, 'error reading key: %s' % e
            sys.exit(e.errno)

    evt = threading.Event()
    if len(args) >= 1 and args[0] == 'archive':
        browser = get_browser_arg()
        BrowserRunner(evt).archive_current_profiles(browser)
        sys.exit(0)
    
    # start tests in specified browsers.  if none given, run all.
    queryparams = []
    queryparams.append("ip=%s" % (config.local_ip))
    queryparams.append("port=%d" % (config.local_port))
    queryparams.append("client=%s" % (urllib2.quote(config.client, '')))

    if config.testmode:
        queryparams.append('test=true')

    url_prefix = config.local_test_base_url + '/start.html?' + "&".join(queryparams)
    url_prefix += '&testUrl='
    if not options.tests:
        print 'Getting test list from server...'
        try:
            tests_url = config.server_api_url + '/testpaths/'
            print 'Getting test list from %s...' % tests_url
            options.tests = json.loads(urllib2.urlopen(tests_url).read())
        except urllib2.HTTPError, e:
            sys.stderr.write('Could not get test list: %s\n' % e)
            sys.exit(errno.EPERM)
        except urllib2.URLError, e:
            sys.stderr.write('Could not get test list: %s\n' % e.reason)
            sys.exit(e.reason.errno)

    test_urls = map(lambda x: url_prefix + urllib2.quote(x.encode("utf-8")), options.tests)

    if len(args) >= 1 and args[0] == 'load' and len(test_urls) > 1:
        test_urls = test_urls[:1]

    browsers = args

    conf_browsers = config.get_str(config.platform, "browsers")
    if browsers is None or len(browsers) == 0 and conf_browsers is not None:
        browsers = conf_browsers.split()

    br = BrowserRunner(evt, browsers, test_urls, config.platform)
    print 'Starting HTTP server...'
    trs = TestRunnerHTTPServer(('', config.local_port),
                               TestRunnerRequestHandler, br, key)
    server_thread = threading.Thread(target=trs.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    cycle_count = 0

    while options.cycles == -1 or cycle_count < options.cycles:
        start = datetime.datetime.now()
        print '==== Starting test cycle %d ====' % (cycle_count+1)
        br.launch_next_browser()
        while not evt.is_set():
            if br.browser_running():
                if evt.is_set():
                    # evt may have been set while we were waiting for the lock in
                    # browser_running().
                    break
                if br.execution_time() > MAX_TEST_TIME:
                    print 'Test has taken too long; starting next test.'
                    br.next_test()
            else:
                print 'Browser isn\'t running!'
                br.next_test()
            evt.wait(5)
        end = datetime.datetime.now()
        br.reset()
        print ''
        print '==== Done! ===='

        if not config.testmode:
            report = results.SpeedTestReport(trs.results)
            print
            print 'Start: %s' % start
            print 'Duration: %s' % (end - start)
            print 'Client: %s' % config.local_ip
            print
            print report.report()

        cycle_count = cycle_count + 1

        if options.nap_after > 0 and cycle_count > 0 and cycle_count % options.nap_after == 0:
            print "Napping for %d seconds..." % (options.nap_time)
            time.sleep(options.nap_time)

    trs.shutdown()
    server_thread.join()

if __name__ == '__main__':
    main()
