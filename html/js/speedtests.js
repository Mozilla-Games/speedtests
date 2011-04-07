DYNAMIC_SERVER_URL = "http://" + window.location.hostname;

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

//  var crossDomainPost = function NetUtils_crossDomainPost(url, values, callback) {
//    if (!arguments.callee.c)
//      arguments.callee.c = 1;
//    var iframeName = "iframe" + arguments.callee.c++;
//    var iframe = $("<iframe></iframe>").hide().attr("name", iframeName).appendTo("body");
//    var form = $("<form></form>").hide().attr({ action: url, method: "post", target: iframeName }).appendTo("body");
//    for (var i in values) {
//      $("<input type='hidden'>").attr({ name: i, value: values[i]}).appendTo(form);
//    }
//    form.get(0).submit();
//    form.remove();
//    iframe.get(0).onload = function crossDomainIframeLoaded() {
//      callback();
//      setTimeout(function () { iframe.remove(); }, 0);
//    }
//  };

  var getSearchParams = function() {
    var params = document.location.search.slice(1).split("&");
    var args = new Object();
    for (p in params) {
      var l = params[p].split("=").map(function(x)
          { return decodeURIComponent(x); });
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
      var body = JSON.stringify({ testname: testname, results: all_results,
                                  ua: navigator.userAgent });
      var req = new XMLHttpRequest();
      req.open("POST", DYNAMIC_SERVER_URL + "/testresults/", false);
      req.setRequestHeader("Content-type", "application/x-www-form-urlencoded");
      req.setRequestHeader("Content-length", body.length);
      req.setRequestHeader("Connection", "close");
      req.send(body);

      var local_url = 'http://' + searchParams.ip + ':' + searchParams.port + '/';
      var url = DYNAMIC_SERVER_URL + "/nexttest/" + testname + "/" +
                document.location.search;
      window.location.assign(url);
//      crossDomainPost(local_url, {body: body}, function () {
//        var url = DYNAMIC_SERVER_URL + "/nexttest/" + testname + "/" +
//                  document.location.search;
//        window.location.assign(url);
//      });
    }
  };
}();
