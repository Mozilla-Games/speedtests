/* -*- Mode: js; js-indent-level: 2; indent-tabs-mode: nil; tab-width: 40; -*- */

/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this file,
 * You can obtain one at http://mozilla.org/MPL/2.0/. */

var SpeedTests = function() {

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
    config: null,    // _benchconfig from query, or null
    name: null,      // the test, as passed to init

    results: [],     // the results
    periodicValues: [], // accumulated periodic values

    init: function(name) {
      if (obj.name != null)
        console.warning("speedtests: test '" + obj.name + "' already called init()! [new name given: '" + name + "']");

      obj.name = testname;
      obj.startTime = new Date();
    },


    // Record a result from this test suite; the subname should
    // be the name of the sub-test.  'extra' is a JSON object of extra
    // values to be stored along with this data.
    recordSubResult: function(subname, value, extra) {
      var r = { name: subname, value: value };
      if (extra)
        r.extra = extra;
      results.push(r);
    },

    // Helper for the result for the entire test suite.
    // Uses the test suite name as the result name.
    recordResult: function(value, extra) {
      return obj.recordSubResult(obj.name, value, extra);
    },

    // Special helper -- if the test produces a periodic value, e.g.
    // a framerate, record a value.  record[Sub]PeriodicResult() must be
    // called to actually commit it, and to reset the periodic values.
    periodicResultValue: function(value) {
      obj.periodicValues.push(value);
    },

    recordSubPeriodicResult: function(subname, extra) {
      if (obj.periodicValues.length == 0) {
        console.error("recordPeriodicResult: no periodicResultValue calls!");
        obj.periodicValues = [];
        return;
      }

      // simple median; in the future we can introduce some different mechanisms for this
      var value = obj.periodicValues[Math.floor(obj.periodicValues.length / 2)];
      var r = { name: subname, value: value, raw: obj.periodicValues };
      obj.periodicValues = [];
      if (extra)
        r.extra = extra;
      results.push(r);
    },

    recordPeriodicResult: function(method) {
      return obj.recordSubPeriodicResult(obj.name, extra);
    },

    finish: function() {
      if (obj.name == null) {
        console.error("speedtests: test called finish(), but never called init!");
        return;
      }

      
    },
  };

  obj.loadTime = new Date();
  if ('_benchconfig' in urlParams)
    obj.config = JSON.parse(decode_base64('_benchconfig'));

  return obj;
}();

var SpeedTestsOld = function() {

  var loadingNextTest = false;
  var all_results = [];
  var hasError = true;
  var startTime = new Date();
  var lastReportTime = null;
  
  var isoDateTime = function (d) {
    function pad(n) { return n < 10 ? '0' + n : n; }
    return d.getUTCFullYear() + '-'
         + pad(d.getUTCMonth()+1) + '-'
         + pad(d.getUTCDate()) + ' '
         + pad(d.getUTCHours()) + ':'
         + pad(d.getUTCMinutes()) + ':'
         + pad(d.getUTCSeconds());
  };

  var recordResults = function (testname, results) {
    if (startTime == null) {
      alert("startTime is null -- SpeedTests.init was not called");
    }

    results.browser_width = window.innerWidth;
    results.browser_height = window.innerHeight;
    results.teststart = isoDateTime(startTime);
    if (results['error'])
      hasError = true;
    all_results.push(results);
  };

  var getSearchParams = function() {
    var params = document.location.search.slice(1).split("&");
    var args = new Object();
    for (var p = 0; p < params.length; p++) {
      var l = params[p].split("=");
      for (var i = 0; i < l.length; i++) {
        l[i] = decodeURIComponent(l[i]);
      }
      if (l.length != 2)
        continue;
      args[l[0]] = l[1];
    }
    return args;
  };
  
  return {
    init: function() {
      startTime = new Date();
      hasError = false;
    },
    getSearchParams: getSearchParams,
    isoDateTime: isoDateTime,
    recordResults: recordResults,
    periodicRecordResults: function (testname, resultFunc) {
      var now = new Date();
      var etms = now - startTime;
      if (lastReportTime == null || now - lastReportTime > 5000) {
        lastReportTime = now;
        var results = resultFunc();
        results.etms = etms;
        recordResults(testname, results);
      }
      return etms;
    },
    nextTest: function (testname) {
      if (loadingNextTest) {
        return;
      }
      loadingNextTest = true;
      var searchParams = getSearchParams();
      if (!searchParams.ip) {
        alert("Can't submit test results: no local IP provided.");
        return;
      }
      if (!searchParams.port) {
        alert("Can't submit test results: no local port provided.");
        return;
      }
      var bodyobj = { testname: testname,
                      ip: searchParams.ip,
                      client: searchParams.client,
                      results: all_results,
                      test_skipped: all_results.length == 0 || all_results[0].test_skipped == true,
                      ua: navigator.userAgent,
                      error: hasError };
      if (searchParams.buildid)
        bodyobj.buildid = searchParams.buildid;
      if (searchParams.geckoversion)
        bodyobj.geckoversion = searchParams.geckoversion;
      var body = JSON.stringify(bodyobj);
      var req = new XMLHttpRequest();
      req.open("POST", "http://" + searchParams.ip + ":" + searchParams.port + "/", false);
      req.setRequestHeader("Content-type", "application/x-www-form-urlencoded");
      req.setRequestHeader("Content-length", body.length);
      req.setRequestHeader("Connection", "close");
      req.send(body);
    }
  };
}();

