DYNAMIC_SERVER_URL = "http://" + window.location.hostname + ":8080";

function isoDateTime(d) {
    function pad(n) { return n < 10 ? '0' + n : n }
    return d.getUTCFullYear() + '-'
         + pad(d.getUTCMonth()+1) + '-'
         + pad(d.getUTCDate()) + ' '
         + pad(d.getUTCHours()) + ':'
         + pad(d.getUTCMinutes()) + ':'
         + pad(d.getUTCSeconds());
}

function reportResults(testname, results) {
    results.browser_width = window.innerWidth;
    results.browser_height = window.innerHeight;
    var body = JSON.stringify({ testname: testname, results: results, ua: navigator.userAgent });
    var req = new XMLHttpRequest();
    alert('reporting to ' + DYNAMIC_SERVER_URL + "/testresults/");
    req.open("POST", DYNAMIC_SERVER_URL + "/testresults/", true);
    req.setRequestHeader("Content-type", "application/x-www-form-urlencoded");
    req.setRequestHeader("Content-length", body.length);
    req.setRequestHeader("Connection", "close");
    alert('sending');
    req.send(body);
    alert('sent');
}

function nextTest(testname) {
    var url = DYNAMIC_SERVER_URL + "/nexttest/" + testname;
    //console.log('loading next test at ' + url);
    window.location.assign(url);
}
