DYNAMIC_SERVER_URL = "http://" + window.location.hostname + ":8080";

var speedtests = function() {

  var all_results = [];
  
  return {
    isoDateTime: function (d) {
      function pad(n) { return n < 10 ? '0' + n : n }
      return d.getUTCFullYear() + '-'
           + pad(d.getUTCMonth()+1) + '-'
           + pad(d.getUTCDate()) + ' '
           + pad(d.getUTCHours()) + ':'
           + pad(d.getUTCMinutes()) + ':'
           + pad(d.getUTCSeconds());
    },
    recordResults: function (testname, results) {
      results.browser_width = window.innerWidth;
      results.browser_height = window.innerHeight;
      all_results.push(results);
    },
    nextTest: function (testname) {
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