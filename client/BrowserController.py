import datetime
import os
import sys
import platform
import ConfigParser
import subprocess
import time

from Config import config

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

    def init_browser(self):
        return True
            
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
                #print 'Warning: no archived profile'
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

    def launch(self, url):
        if not self.copy_profiles():
            print 'Failed to copy profiles'
            return False
        cl = self.cmd_line(url)
        if config.verbose:
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
            if config.verbose:
                print "controller.terminate(), trying.."
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
