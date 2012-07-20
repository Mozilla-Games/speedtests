/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this file,
 * You can obtain one at http://mozilla.org/MPL/2.0/. */

var SpeedTests = function() {

  var loadingNextTest = false;
  var all_results = [];
  var startTime = null;
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
    results.browser_width = window.innerWidth;
    results.browser_height = window.innerHeight;
    results.teststart = isoDateTime(startTime);
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
                      ua: navigator.userAgent };
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

