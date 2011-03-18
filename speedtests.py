# when last page is loaded, browser will ping server
# server kills current process, starts next
import BaseHTTPServer
import ConfigParser
import errno
import os
import platform
import socket
import subprocess
import sys
import tempfile
import threading
import time

DEFAULT_CONF_FILE = 'speedtests.conf'
cfg = ConfigParser.ConfigParser()
cfg.read(DEFAULT_CONF_FILE)
try:
    TEST_URL = cfg.get('speedtests', 'server_url').rstrip('/') + \
               '/start/?auto=true'
except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
    TEST_URL = 'http://brasstacks.mozilla.com/speedtestssvr/start/?auto=true'


class TestsFinishedException(Exception):
    
    def __str__(self):
        return 'Browser SpeedTests finished!'


class BrowserLauncher(object):
    
    def __init__(self, cmd_tuple):
        self.cmd_tuple = cmd_tuple

    def cmd_line(self, url=TEST_URL):
        return self.cmd_tuple + (url,)

    def browser_exists(self):
        return os.path.exists(self.cmd_tuple[0])


class BrowserLauncherRedirFile(BrowserLauncher):
    
    def __init__(self, cmd_tuple):
        self.cmd_tuple = cmd_tuple
        self.redir_file = None
    
    def cmd_line(self, url=TEST_URL):
        self.redir_file = tempfile.NamedTemporaryFile(suffix='.html')
        self.redir_file.write('<html><head><meta HTTP-EQUIV="REFRESH" content="0; url=%s"></head></html>\n' % url)
        self.redir_file.flush()
        return super(BrowserLauncherRedirFile, self).cmd_line(self.redir_file.name)
        

class BrowserRunner(object):

    @classmethod
    def browsers_by_os(cls, os_str):
        if os_str == 'Darwin':
            return [
                   BrowserLauncher(('/Applications/Firefox.app/Contents/MacOS/firefox', '-private')),
                   BrowserLauncherRedirFile(('/Applications/Safari.app/Contents/MacOS/Safari',)),
                   BrowserLauncher(('/Applications/Opera.app/Contents/MacOS/Opera',)),
                   BrowserLauncher(('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',)),
                   ]
        elif os_str == 'Linux':
            return []
        elif os_str == 'Windows':
            return [
                   BrowserLauncher(('\\Program Files\\Mozilla Firefox 4.0 Beta 12\\firefox.exe', '-private')),
                   BrowserLauncher(('\\Program Files\\Internet Explorer\\iexplore.exe',)),
                   BrowserLauncher(('\\Program Files\\Safari\\Safari.exe',)),
                   BrowserLauncher(('\\Program Files\\Opera\\opera.exe',)),
                   BrowserLauncher((os.path.join(os.getenv('USERPROFILE'), 'Local Settings\\Application Data\\Google\\Chrome\\Application\\chrome.exe'),)),
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
    
    def browser_running(self):
        self.lock.acquire()
        running = self.proc and self.proc.poll()
        if running != None:
            self.proc = None
        self.lock.release()
        return running == None

    def launch_next_browser(self):
        self.lock.acquire()
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

        while True:
            try:
                self.current_launcher = self.browser_iter.next()
            except StopIteration:
                self.evt.set()
                self.lock.release()
                return
            if self.current_launcher.browser_exists():
                break

        cl = self.current_launcher.cmd_line()
        print 'Launching %s...' % ' '.join(cl)
        self.proc = subprocess.Popen(cl)
        self.lock.release()


br = None


class TestRunner(BaseHTTPServer.BaseHTTPRequestHandler):
    
    def do_GET(self):
        print 'got pingback'
        global br
        br.launch_next_browser()
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
    global br
    evt = threading.Event()
    br = BrowserRunner(evt)
    trs = BaseHTTPServer.HTTPServer(('', 8111), TestRunner)
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
