SpeedTests
==========

SpeedTests is a (slightly misnamed) framework for cross-browser comparisons.
See the [wiki page](https://wiki.mozilla.org/Auto-tools/Projects/SpeedTests)
for details about the project.

This document will only concern the installation of the framework.


Requirements
------------

The client has no strict requirements other than Python 2.5+.  Highly
suggested is the [jwt module] (https://github.com/markrcote/jwt) if you need
to validate results with the server.

The server requires [templeton] (https://github.com/markrcote/templeton),
which in turn requires [web.py] (http://webpy.org/).  The server also
optionally supports jwt.


Installation
------------

### Server ###

The server is made of two components: a tests server and a results server.
The former serves the tests to the client.  By not bundling the tests with
the clients, it is easy to add new tests.  The latter accepts results from
the clients and provides a simple web UI to view them.  They can be combined
into a single server or separated onto two machines.  Furthermore, a server
can be configured to proxy results onto another results server.

The server is configured by the file speedtests_server.conf, which should be
placed into the server directory (speedtests/server/).

The [speedtests] section can contain the following options:

* html_dir: For serving tests, this is the location of the tests' html
            directory.  It defaults to ../html/.
* proxy: Indicates that results should be proxied onto the given server and
         not stored locally.  Defaults to None (no proxying).
* db_host: Hostname of the server storing the results database.  Defaults to
           localhost.
* db_name: Name of the results database.  Defaults to "speedtests".
* db_user: Username to access the results database.  Defaults to "speedtests".
* db_passwd: Password to access the results database.  Defaults to
             "speedtests".

Database table name is not configurable, since one table is used per test and
is named according to the test.  You should create these tables on the 
results server by loading the SQL files found in
speedtests/server/speedtests/*/ (FIXME: automate this!)

The [clients] section, which must be present on a results server, should list
all clients in the form <IP address> = <displayed name>.  This is used for
the "Machine" drop down on the results web UI.

The [client keys] section should contain options in the form
<client IP> = <key>.  This is used to authenticate clients' requests.  The
jwt module is required if this section exists and has entries.

There is no strict separation of the functionality of the tests and results
server; rather, if tests exist in the html directory, they are served as
requested.  Similarly, if the results db exists, the server will attempt to
store results if sent and serve results if requested.

To run a development version of the server, cd into the server directory and
run "python server.py [port]", where port is optional and defaults to 8080.
The tests' static HTML files (if they exist) will be served as
http://0.0.0.0:8080/.  The results are available at
http://0.0.0.0:8080/results.html.  The dynamic API (tests list, results
server) is served under http://0.0.0.0:8080/api/.  See the "urls" tuple in 
server/handlers.py for the available APIs.

For production, a real web server, such as nginx, should be configured to
serve the html directory at a particular path (e.g. /speedtests/) and
speedtests_server.fcgi served under that path as api/ (e.g. /speedtests/api/).


### Clients ###

The main client program is client/speedtests.py.  It is configured with the
file speedtests.conf, which should be placed into the client/ directory.

The main settings in speedtests.conf are in the [speedtests] section:

* 64bit: Instructs the Nightly downloader to grab the 64-bit version.
* local_port: The port the local server should run under. Defaults to 8111.
* test_base_url: The URL of the static test files on the tests server.
* server_url: The URL of the tests server web API (for getting the list of
              available tests).
* server_results_url: The URL of the results server web API (for submitting
                      results).

Optionally, the config file may also contain a section for the current OS
("osx", "linux", or "windows"), which in turn can contain an option for any
or all browsers ("firefox", "safari", "internet explorer", "opera").  The
option value is the path to that browser's main executable.  This can be used
if one or more browsers are installed to nonstandard locations.  There is no
"nightly" option because Nightly is always downloaded freshly.

Without any options, the client will attempt to run all browsers (Firefox,
Opera, IE, Safari, Chrome) that it finds.  It will also attempt to download
the latest Nightly.

You can also provide a list of browser names, and only those will be executed
(using the same strings as in the config file described above).  You can also
provide the -t or --test option one or more times to list the only tests that
should be run.  Note that in this case the client does not get a list of tests
from the server, so the relative URL to the main test page should be given
(e.g. -t csstest/index.html -t jstest/index.html ...).

Giving the -n or --noresults option indicates that the results should not be
sent to the server.  They will still be printed to the console.

The --testmode option can be used to test a browser's settings using a no-op
test.  No results are sent (i.e. -n is implied).

The -s or --sign option can be given with a path to a file containing a key
that will be used to sign the results via JSON Web Signature.  The server
must have the same key defined in its config file with the client's IP
address (see above), or the results will be discarded.  The jwt module is
required for this option.


#### Configuring client browsers ####

If present, before executing each test, the client copies the appropriate
stored profile over top of the browser's current profile.  No profiles are
packaged with speedtests, so the browsers must be configured properly and
their profiles stored before automated runs can be started.

All browsers must be able to (a) open pages on localhost and (b) open pop-ups,
at least from localhost.  Additionally, the cache and history should be
empty.

The pop-ups setting is necessary because the client opens all tests in a new
window of a set size.

It is suggested that each browser be opened manually and the necessary settings
applied.  Then the special command "archive" can be given, e.g.
"python speedtests.py archive opera" to store Opera's current profile.  After
this, the stored profile will be used each time, ensuring that the browser's
configuration is always the same.  The --testmode option can be given to
verify that the browser is configured properly without having to execute a
test.
