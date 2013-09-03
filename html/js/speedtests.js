/* -*- Mode: js; js-indent-level: 2; indent-tabs-mode: nil; tab-width: 40; -*- */

/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this file,
 * You can obtain one at http://mozilla.org/MPL/2.0/. */

var SpeedTests = function() {
  // wait at most this many seconds for server submissions to complete
  var SERVER_SUBMIT_TIMEOUT_SECONDS = 30;

  // helper -- use built-in atob if it exists, otherwise use the js.
  var decode_base64 = window.atob || function js_decode_base64(s) {
    var e={},i,k,v=[],r='',w=String.fromCharCode;
    var n=[[65,91],[97,123],[48,58],[43,44],[47,48]];

    for(z in n){for(i=n[z][0];i<n[z][1];i++){v.push(w(i));}}
    for(i=0;i<64;i++){e[v[i]]=i;}

    for(i=0;i<s.length;i+=72){
      var b=0,c,x,l=0,o=s.substring(i,i+72);
      for(x=0;x<o.length;x++){
        c=e[o.charAt(x)];b=(b<<6)+c;l+=6;
        while(l>=8){r+=w((b>>>(l-=8))%256);}
      }
    }
    return r;
  };

  var encode_base64 = window.btoa || function js_encode_base64(data) {
    var b64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=";
    var o1, o2, o3, h1, h2, h3, h4, bits, i = 0, ac = 0, enc = "", tmp_arr = [];
    if (!data) return data;

    do { // pack three octets into four hexets
      o1 = data.charCodeAt(i++);
      o2 = data.charCodeAt(i++);
      o3 = data.charCodeAt(i++);

      bits = o1 << 16 | o2 << 8 | o3;

      h1 = bits >> 18 & 0x3f;
      h2 = bits >> 12 & 0x3f;
      h3 = bits >> 6 & 0x3f;
      h4 = bits & 0x3f;

      // use hexets to index into b64, and append result to encoded string
      tmp_arr[ac++] = b64.charAt(h1) + b64.charAt(h2) + b64.charAt(h3) + b64.charAt(h4);
    } while (i < data.length);

    enc = tmp_arr.join('');
    var r = data.length % 3;
    return (r ? enc.slice(0, r - 3) : enc) + '==='.slice(r || 3);
  };

  var ISODateString = function(d) {
    d = d || new Date();
    function pad(n) {return n<10 ? '0'+n : n}
    return d.getUTCFullYear()+'-'
      + pad(d.getUTCMonth()+1)+'-'
      + pad(d.getUTCDate())+'T'
      + pad(d.getUTCHours())+':'
      + pad(d.getUTCMinutes())+':'
      + pad(d.getUTCSeconds())+'Z'
  };

  // grab the URL params so that we have them handy; we'll only really care
  // about the _benchconfig param
  var urlParams = {};
  (function () {
    var match,
    pl     = /\+/g,  // Regex for replacing addition symbol with a space
    search = /([^&=]+)=?([^&]*)/g,
    decode = function (s) { return decodeURIComponent(s.replace(pl, " ")); },
    query  = window.location.search.substring(1);

    while ((match = search.exec(query)) != null)
      urlParams[decode(match[1])] = decode(match[2]);
  })();

  var obj = {
    loadTime: null,  // when the script was loaded
    startTime: null, // when init() was called
    config: {},      // _benchconfig from query
    name: null,      // the test, as passed to init
    finished: false, // are we all done? if so, none of the calls do anything

    results: [],     // the results
    periodicValues: [], // accumulated periodic values

    // Clear all recorded results.
    resetResults: function() {
        obj.results = [];
    },

    init: function(name, config) {
      if (obj.name != null)
        console.warning("speedtests: test '" + obj.name + "' already called init()! [new name given: '" + name + "']");

      // for testing
      if (config)
        setConfig(config);

      if (!('_benchchild' in urlParams)) {
      }


      window.moveTo(0, 0);
      window.resizeTo(obj.config.testWidth, obj.config.testHeight);

      obj.name = name;
      obj.startTime = new Date();
    },

    setConfig: function(config) {
      obj.config = config;
      console.log("setConfig:", config);
      if (!('clientName' in obj.config)) {
        console.log.error("benchconfig missing clientName!");
        obj.config = {};
      }

      // some defaults
      var defaults = {
        'testWidth': 1024,
        'testHeight': 768
      };

      for (var n in defaults) {
        if (!(n in obj.config))
          obj.config[n] = defaults[n];
      }
    },

    // Record a result from this test suite; the subname should
    // be the name of the sub-test.  'extra' is a JSON object of extra
    // values to be stored along with this data.
    recordSubResult: function(subname, value, extra) {
      if (obj.finished) return;

      var r = { name: subname,
                value: value,
                width: window.innerWidth,
                height: window.innerHeight };
      if (extra)
        r.extra = extra;
      obj.results.push(r);
    },

    // Helper for the result for the entire test suite.
    // Uses the test suite name as the result name.
    recordResult: function(value, extra) {
      if (obj.finished) return;

      return obj.recordSubResult(obj.name, value, extra);
    },

    // Special helper -- if the test produces a periodic value, e.g.
    // a framerate, record a value.  record[Sub]PeriodicResult() must be
    // called to actually commit it, and to reset the periodic values.
    periodicResultValue: function(value) {
      if (obj.finished) return;

      obj.periodicValues.push(value);
    },

    recordSubPeriodicResult: function(subname, extra) {
      if (obj.finished) return;

      if (obj.periodicValues.length == 0) {
        console.error("recordPeriodicResult: no periodicResultValue calls!");
        obj.periodicValues = [];
        return;
      }

      // simple median; in the future we can introduce some different mechanisms for this
      var pv = obj.periodicValues;
      pv.sort(function(a,b) { if (a<b) return -1; if (a>b) return 1; return 0; });

      // take the average as the value, but provide min/max/median
      var avg = 0;
      for (var i = 0; i < pv.length; ++i)
        avg += pv[i];
      avg = avg / pv.length;

      var r = { name: subname,
                value: avg,
                min: pv[0],
                max: pv[pv.length-1],
                median: pv[Math.floor(pv.length / 2)],
                width: window.innerWidth,
                height: window.innerHeight };
      obj.periodicValues = [];
      if (extra)
        r.extra = extra;
      results.push(r);
    },

    recordPeriodicResult: function(method) {
      return obj.recordSubPeriodicResult(obj.name, extra);
    },

    recordError: function(name, message) {
      name = name || obj.name;
      var r = { name: name,
                error: true };
      if (message)
        r.message = message;
      obj.results.push(r);
    },

    // Called when the test is finished running.
    // Argument indicates if this is the final run.
    // Usage:  SpeedTests.finish([isFinal], [callback]);
    finish: function() {
      var isFinal;
      var callback;
      if (arguments.length == 0) {
        isFinal = true;
      } else if (arguments.length == 1) {
        if (typeof(arguments[0]) == 'function') {
          isFinal = true;
          callback = arguments[0];
        } else {
          isFinal = arguments[0];
        }
      } else if (arguments.length >= 2) {
        isFinal = arguments[0];
        callback = arguments[1];
      }

      if (obj.finished) return;

      if (obj.name == null) {
        console.error("speedtests: test called finish(), but never called init!");
        return;
      }

      obj.finishTime = new Date();

      // if we're just testing, don't post anything
      if (obj.config.testing)
        return;

      // we're done with this test.  We need to a) send the results to the results server;
      // and b) send the client runner a "test done" notification

      var resultServerObject = {
        browserInfo: {
          ua: navigator.userAgent,
          build: navigator.buildID || 0,
          screenWidth: window.screen.width,
          screenHeight: window.screen.height
        },
        client: obj.config.clientName,
        browser: obj.config.browser,
        loadTime: obj.loadTime.getTime(),
        startTime: obj.startTime.getTime(),
        finishTime: obj.finishTime.getTime(),
        complete: urlParams['_final']
      };

      var extraBrowserInfo = ["browserNameExtra", "browserSourceStamp", "browserBuildID"];
      var extraBrowserTarget = ["nameExtra", "sourceStamp", "buildID"];
      for (var i = 0; i < extraBrowserInfo.length; ++i) {
        if (extraBrowserInfo[i] in obj.config)
          resultServerObject.browserInfo[extraBrowserTarget[i]] = obj.config[extraBrowserInfo[i]];
      }

      // We want to send a few extra things to the non-cube destinations;
      // since we don't need/want these in mongodb.  Create their json string
      // up front.
      resultServerObject.config = obj.config;
      resultServerObject.results = obj.results;
      var resultsStr = encode_base64(JSON.stringify(resultServerObject));
      delete resultServerObject.results;
      delete resultServerObject.config;

      function sendResults(server, resultTarget) {
        if (!server) {
          if (resultTarget)
            SpeedTests[resultTarget + "Done"] = true;
          return;
        }

        // We're not going to do XHR, because we want to cross-origin our way
        // to victory (and to not caring about servers or CORS support).
        // So, JSONP time.
        var script = document.createElement("script");
        var src = server + "?";
        if (resultTarget)
          src += "target=" + resultTarget + "&";
        src += "data=" + resultsStr;

        if (obj.config.debug)
          console.log("sendResults: " + src);
        script.setAttribute("type", "text/javascript");
        script.setAttribute("src", src);
        document.body.appendChild(script);

        // not used
        if (false) {
          var req = new XMLHttpRequest();
          req.open("GET", "http://" + server + "/api/post-results", false);
          req.onreadystatechange = function() {
            if (req.readyState != 4) return;
            if (resultTarget) {
              SpeedTests[resultTarget + "Done"] = true;
              if (req.status != 200)
                SpeedTests[resultTarget + "Error"] = req.status + " -- " + req.responseText;
            }
          };
          req.send(resultsStr);
        }
      }

      // send the results to the server
      if (obj.config) {
        var waitBeforeSendResults = 0;
        if (obj.config.debug) {
            waitBeforeSendResults = 10000;
            console.log("Sending results: " + JSON.stringify(obj.results));
        }
        setTimeout(function () {
            sendResults(obj.config.resultServer, "serverSend");
        }, waitBeforeSendResults);

        // for cube, we split up each individual result in its own notification
        SpeedTests["cubeSendDone"] = false;
        if (obj.config.cubeServer && "WebSocket" in window) {
          var cubeResult = {
            "type": "result",
            "time": ISODateString(obj.finishTime)
          };

          var ws = new WebSocket(obj.config.cubeServer);
          ws.onopen = function() {
            // prep for cube results
            for (var i = 0; i < obj.results.length; ++i) {
              var r = obj.results[i];
              for (var prop in r)
                resultServerObject[prop] = r[prop];
              cubeResult.data = resultServerObject;

              ws.send(JSON.stringify(cubeResult));

              for (var prop in r)
                delete resultServerObject[prop];
            }

            ws.close();
          };
          ws.onclose = function() {
            SpeedTests["cubeSendDone"] = true;
          };
          ws.onerror = function(error) {
            console.log("ws error", error);
          };
        } else {
          SpeedTests["cubeSendDone"] = true;
        }
      }

      var count = 0;
      var waitForRunnerSend = false;
      function waitForResults() {
        var done = SpeedTests["serverSendDone"] && SpeedTests["cubeSendDone"] && (waitForRunnerSend ? SpeedTests["runnerSendDone"] : true);
        var error = false;

        if (++count > 20) {
          done = true;
          error = true;
        }

        if (done && isFinal && !waitForRunnerSend) {
          sendResults(obj.config.runnerServer, "runnerSend");
          waitForRunnerSend = true;
        } else if (done) {
          if (!isFinal) {
            console.log("Finished iteration.");
            if (callback)
              callback();
            return;
          }
          console.log("Finished run.");

          // finished
          document.location = "about:blank";
          // if we can; might exit the browser, which would be nice.
          // XXX hack for Chrome to maximize our chances of closing this window/tab
          setTimeout(function() {
            window.open('', '_self', '');
            window.close();
          }, 0);

          if (error) {
            alert("SpeedTests: failed to send results to server, waited 10 seconds for response!");
          }

          return;
        }

        setTimeout(waitForResults, 500);
      }

      setTimeout(waitForResults, 500);
    }
  };

  obj.loadTime = new Date();
  if ('_benchconfig' in urlParams) {
    obj.setConfig(JSON.parse(decode_base64(urlParams['_benchconfig'])));
    obj.config.token = urlParams['_benchtoken'];
    obj.config.run_uuid = urlParams['_run_uuid'];
    obj.config.bench_name = urlParams['_bench_name'];
  } else {
    obj.setConfig({ clientName: 'test', testing: true });
  }

  // This is a hack; on desktop browsers, we want to open a popup so we can
  // control the size.  But on Android & FFOS, we don't want to do this because
  // the browser window will be full screen anyway, and we don't want to have
  // to allow popups since it's more complicated there.
  if (!obj.config.testing &&
      (obj.config.platform != 'android' && obj.config.platform != 'ffos') &&
      !('_benchchild' in urlParams))
  {
    window.open(window.location + "&_benchchild=1", '_blank', 'titlebar,close,location');
    window.location = "about:blank";
    return;
  }

  return obj;
}();
