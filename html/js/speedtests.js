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

  // grab the URL params so that we have them handy; we'll only really care
  // about the _benchconfig param
  var urlParams = {};
  (function () {
    var match,
    pl     = /\+/g,  // Regex for replacing addition symbol with a space
    search = /([^&=]+)=?([^&]*)/g,
    decode = function (s) { return decodeURIComponent(s.replace(pl, " ")); },
    query  = window.location.search.substring(1);

    while (match = search.exec(query))
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
      var value = obj.periodicValues[Math.floor(obj.periodicValues.length / 2)];
      var r = { name: subname,
                value: value,
                raw: obj.periodicValues,
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

    // Called when the test is finished running.
    finish: function() {
      if (obj.finished) return;

      if (obj.name == null) {
        console.error("speedtests: test called finish(), but never called init!");
        return;
      }

      obj.finishTime = new Date();

      // we're done with this test.  We need to a) send the results to the results server;
      // and b) send the client runner a "test done" notification

      var resultServerObject = {
        browserInfo: {
          ua: navigator.userAgent,
          screenWidth: window.screen.width,
          screenHeight: window.screen.height
        },
        config: obj.config,
        loadTime: obj.loadTime.getTime(),
        startTime: obj.startTime.getTime(),
        finishTime: obj.finishTime.getTime(),

        results: obj.results
      };

      var extraBrowserInfo = ["browserNameExtra", "browserSourceStamp", "browserBuildID"];
      for (var i = 0; i < extraBrowserInfo.length; ++i) {
        if (extraBrowserInfo[i] in obj.config)
          resultServerObject.browserInfo[extraBrowserInfo[i]] = obj.config[extraBrowserInfo[i]];
      }

      var resultsStr = encode_base64(JSON.stringify(resultServerObject));

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

      // send the results to the server and the runner
      if (obj.config) {
        sendResults(obj.config.resultServer, "serverSend");
        sendResults(obj.config.runnerServer, "runnerSend");
      }

      var count = 0;
      function waitForResults() {
        var done = SpeedTests["serverSendDone"] && SpeedTests["runnerSendDone"];
        var error = false;

        if (++count > 20) {
          done = true;
          error = true;
        }

        if (done) {
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
  }

  // This is a hack; on desktop browsers, we want to open a popup so we can
  // control the size.  But on Android & FFOS, we don't want to do this because
  // the browser window will be full screen anyway, and we don't want to have
  // to allow popups since it's more complicated there.
  if ((obj.config.platform != 'android' && obj.config.platform != 'ffos') &&
      !('_benchchild' in urlParams))
  {
    window.open(window.location + "&_benchchild=1", '_blank', 'titlebar,close,location');
    window.location = "about:blank";
    return;
  }

  return obj;
}();
