DYNAMIC_SERVER_URL = "http://" + window.location.hostname + ":8080";

var SpeedTests = function() {

  var loadingNextTest = false;
  var all_results = [];
  var startTime = null;
  var lastReportTime = null;
  
  var isoDateTime = function (d) {
    function pad(n) { return n < 10 ? '0' + n : n }
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

  return {
    init: function() {
      startTime = new Date();
    },
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
      var body = JSON.stringify({ testname: testname, results: all_results, ua: navigator.userAgent });
      var req = new XMLHttpRequest();
      req.open("POST", DYNAMIC_SERVER_URL + "/testresults/", false);
      req.setRequestHeader("Content-type", "application/x-www-form-urlencoded");
      req.setRequestHeader("Content-length", body.length);
      req.setRequestHeader("Connection", "close");
      req.send(body);

      var url = DYNAMIC_SERVER_URL + "/nexttest/" + testname + "/" + document.location.search;
      window.location.assign(url);
    }
  };
}();