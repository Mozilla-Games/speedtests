/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

var gCurrentScoreDisplay = null;

// if we're being asked to just display as an inline graph
var gAsInlineGraph = false;

function ScoreDisplay(testname, records, browsers) {
  this.records = records;
  this.browsers = browsers;
  this.resultsTable = null;
}

ScoreDisplay.prototype.destroy = function() {
  $('#results').hide();
  $('#tooltip').remove();
  $('#results .graph').html('');
  if (this.resultsTable) {
    this.resultsTable.fnDestroy();
    this.resultsTable = null;
    $('#results .data').html('');
  }
};

ScoreDisplay.prototype.display = function() {
  $('#results').show();
  var points = this.getPoints();

  $('#results .data').html("");
  if (!gAsInlineGraph)
    $('#disptable').show();

  if (!points.length) {
    this.points = null;
    $('#title').text('no results');
  } else {
    this.points = points;
    $('#title').text(this.title);
    this.displayGraph(points);
  }
};

ScoreDisplay.prototype.getTestRuns = function() {
  var testRuns = [];
  var byTestStart = {};
  var testStart;
  //console.log("records:", this.records);

  for (var i = 0; i < this.records.length; i++) {
    var record = this.records[i];
    testStart = this.records[i].teststart;
    if (!(testStart in byTestStart)) {
      byTestStart[testStart] = [];
    }

    byTestStart[testStart].push(record);
  }
  for (testStart in byTestStart) {
    for (var i = 0; i < byTestStart[testStart].length; ++i)
      testRuns.push([testStart, [ byTestStart[testStart][i]] ]);
  }
  testRuns.sort(function(a, b) { return a[0] - b[0]; });

  return testRuns;
};

ScoreDisplay.prototype.getPoints = function() {
  if (!this.records) {
    return [];
  }
  var testRuns = this.getTestRuns();
  var byBrowser = {};
  var byBrowserExtra = {};
  var browserNames = [];
  var browserId, browser, browserName, browserExtra, score;
  for (var i = 0; i < testRuns.length; i++) {
    var runResult = testRuns[i][1];
    browserId = runResult[0].browser_id;
    browser = this.browsers[browserId];
    score = this.getScore(runResult);
    browserName = browser.browsername + ' ' + browser.browserversion;
    browserExtra = [testRuns[i][0]];
    if (browser.browsername.indexOf('Firefox') != -1) {
      browserExtra.push(browser.buildid);
      browserExtra.push(browser.sourcestamp);
    }

    if (!(browserName in byBrowser)) {
      byBrowser[browserName] = [];
      byBrowserExtra[browserName] = [];
      browserNames.push(browserName);
    }

    var testtime = new Date(testRuns[i][0]).getTime();
    byBrowser[browserName].push([testtime, score]);
    byBrowserExtra[browserName].push(browserExtra);
  }
  browserNames.sort();

  var points = [];
  for (i = 0; i < browserNames.length; i++) {
    var name = browserNames[i];
    points.push({ data: byBrowser[name],
                  extraData: byBrowserExtra[name],
                  label: name });
  }
  return points;
};

ScoreDisplay.prototype.displayGraph = function(points) {
  var graphDiv = $('#results .graph');
  var plot = $.plot(graphDiv, points, {
    grid: {
      hoverable: true
    },
    series: {
      lines: { show: true },
      points: { show: gAsInlineGraph ? false : true }
    },
    xaxis: {
      mode: 'time'
    },
    yaxis: {
      axisLabel: this.scoreName
    },
    legend: {
      position: 'nw',
      hideable: true
    },
    zoom: { interactive: true },
    pan: { interactive: true }
  });

  function plotHoverFunc() {
    var prevPoint = null;
    return function (event, pos, item) {
      if (item) {
        if (prevPoint != item.datapoint) {
          $('#tooltip').remove();
          prevPoint = item.datapoint;
          var tooltip = $('<div id="tooltip"></div>');
          tooltip.css({
            left: item.pageX + 5,
            top: item.pageY + 5
          });

          var tooltipHtml = '<b>' + item.series.label + '</b>: ' + item.datapoint[1] + '<br>';
          for (var i = 0; i < gCurrentScoreDisplay.points.length; ++i) {
            var points = gCurrentScoreDisplay.points[i];
            if (item.series.label != points.label)
              continue;

            // find this point; this sucks a little (a lot)
            var dataIndex = -1;
            for (var j = 0; j < points.data.length; ++j) {
              if (points.data[j][0] == item.datapoint[0] &&
                  points.data[j][1] == item.datapoint[1])
              {
                if (points.extraData[j].length > 2) {
                  var extra = points.extraData[j];

                  tooltipHtml += "<tt>" + extra[1] + "-" + extra[2] + "</tt>";
                }
                break;
              }
            }

            break;
          }

          tooltip.html(tooltipHtml);
          $('body').append(tooltip);
        }
      } else {
        $('#tooltip').remove();
        prevPoint = null;
      }
    };
  }
  graphDiv.bind('plothover', plotHoverFunc());
};

ScoreDisplay.prototype.displayTable = function(points) {
  $('#disptable').hide();

  var table = $('#templates .resultsdata').clone();
  $('#results .data').html(table);

  var tablePoints = [];
  for (var i = 0; i < points.length; ++i) {
    var bname = points[i].label;
    var pdata = points[i].data;
    var pextra = points[i].extraData;
    for (var j = 0; j < pdata.length; ++j) {
      tablePoints.push([pextra[j][0], bname + (pextra[j].length > 2 ? ("&nbsp;<span style='font-size: small'>" + pextra[j][1] + "-" + pextra[j][2] + "</span>") : ""), pdata[j][1]]);
    }
  }

  tablePoints.sort(function(a, b) {
    if (a[0] < b[0]) return -1;
    if (a[0] > b[0]) return 1;
    if (a[1] < b[1]) return -1;
    if (a[1] > b[1]) return 1;
    return 0;
  });

  this.resultsTable = table.find('table').dataTable({
    aaData: tablePoints,
    aoColumns: [
      { sTitle: 'test start', sType: 'date' },
      { sTitle: 'browser' },
      { sTitle: this.scoreName, sType: 'number', sClass: 'textleft',
        sWidth: '20%' }
    ],
    bJQueryUI: true,
    bPaginate: false,
    sDom: 'tir'
  });
};

// override this
ScoreDisplay.prototype.getScore = function(testRunRecords) {
  return 0;
};


FpsScoreDisplay.prototype = new ScoreDisplay();
FpsScoreDisplay.prototype.constructor = FpsScoreDisplay;
function FpsScoreDisplay(testname, records, browsers) {
  ScoreDisplay.prototype.constructor.call(this, testname, records, browsers);
  this.title = testname + ' test runs, measured in FPS (higher is better)';
  this.scoreName = 'median FPS';
}

// Assuming 'records' is a series of records in the same test, find the
// median.
FpsScoreDisplay.prototype.getScore = function(testRunRecords) {
  var median = 0;
  var scores = testRunRecords.map(function(x) { return x.fps; });
  scores.sort();
  if (scores.length > 0) {
    if (scores.length % 2 == 0) {
      median = (scores[scores.length / 2 - 1] + scores[scores.length / 2]) / 2;
    } else {
      median = scores[Math.floor(scores.length / 2)];
    }
  }
  return median;
};

GenericScoreDisplay.prototype = new ScoreDisplay();
GenericScoreDisplay.prototype.constructor = GenericScoreDisplay;
function GenericScoreDisplay(testname, records, browsers) {
  ScoreDisplay.prototype.constructor.call(this, testname, records, browsers);
  this.title = testname + ' test runs';
  this.scoreName = ' ';
}

GenericScoreDisplay.prototype.getScore = function(testRunRecords) {
  return testRunRecords[0].result_value;
};

PsychBrowsingScoreDisplay.prototype = new ScoreDisplay();
PsychBrowsingScoreDisplay.prototype.constructor = PsychBrowsingScoreDisplay;
function PsychBrowsingScoreDisplay(testname, records, browsers) {
  ScoreDisplay.prototype.constructor.call(this, testname, records, browsers);
  this.title = testname + ' test runs, measured in total RPMs (higher is better)';
  this.scoreName = 'total RPMs of both tests';
}

PsychBrowsingScoreDisplay.prototype.getScore = function(testRunRecords) {
  return testRunRecords[0].checkerboard + testRunRecords[0].colorwheel;
};


DurationScoreDisplay.prototype = new ScoreDisplay();
DurationScoreDisplay.prototype.constructor = DurationScoreDisplay;
function DurationScoreDisplay(testname, records, browsers) {
  ScoreDisplay.prototype.constructor.call(this, testname, records, browsers);
  this.title = testname + ' test runs, durations in milliseconds (lower is better)';
  this.scoreName = 'duration (ms)';
}

DurationScoreDisplay.prototype.getScore = function(testRunRecords) {
  return testRunRecords[0].duration;
};


TestsPassedScoreDisplay.prototype = new ScoreDisplay();
TestsPassedScoreDisplay.prototype.constructor = TestsPassedScoreDisplay;
function TestsPassedScoreDisplay(testname, records, browsers) {
  ScoreDisplay.prototype.constructor.call(this, testname, records, browsers);
  this.title = testname + ' test runs, number of tests passed (higher is better)';
  this.scoreName = 'tests passed';
}

TestsPassedScoreDisplay.prototype.getScore = function(testRunRecords) {
  return testRunRecords[0].score;
};


GeometricMeanScoreDisplay.prototype = new ScoreDisplay();
GeometricMeanScoreDisplay.prototype.constructor = GeometricMeanScoreDisplay;
function GeometricMeanScoreDisplay(testname, records, browsers) {
  ScoreDisplay.prototype.constructor.call(this, testname, records, browsers);
  this.title = testname + ' test runs, geometric mean of test scores (higher is better)';
  this.scoreName = 'geometric mean score';
}

GeometricMeanScoreDisplay.prototype.getScore = function(testRunRecords) {
  return testRunRecords[0].score;
};


function scoreDisplayFactory(testname, records, browsers) {
  var scoreDisplayClass = null;
  switch (testname) {
    case 'PsychedelicBrowsing':
        scoreDisplayClass = PsychBrowsingScoreDisplay;
        break;
    case 'MazeSolver':
    case 'Kraken':
        scoreDisplayClass = DurationScoreDisplay;
        break;
    case 'test262':
        scoreDisplayClass = TestsPassedScoreDisplay;
        break;
    case 'V8':
        scoreDisplayClass = GeometricMeanScoreDisplay;
        break;
    case 'fishtank':
    case 'MrPotatoGun':
    case 'SantasWorkshop':
    case 'SpeedReading':
        scoreDisplayClass = FpsScoreDisplay;
        break;
    // all the 'generic' tests
    default:
        scoreDisplayClass = GenericScoreDisplay;
        break;
  }
  return new scoreDisplayClass(testname, records, browsers);
}


// FIXME: Make an object or something out of this stuff.
var router = null;
var scoreDisplay = null;

function routerFactory() {
  router = Router({
    '/([^\/]*)': {
      on: loadFromRoute,
      '/([^\/]*)': {
        on: loadFromRoute,
        '/([^\/]*)': {
          on: loadFromRoute,
          '/([^\/]*)': {
            on: loadFromRoute,
            '/([^\/]*)': {
              on: loadFromRoute
            }
          }
        }
      }
    },
    '/': {
      on: loadFromRoute
    }
  }).init();
  // Work around SugarSkull double-load-on-init problem.
  if (document.location.hash == '' || document.location.hash == '#') {
    router.setRoute('/');
  }
  return router;
}

/**
 * Set controls to given parameters or use and set defaults, then load
 * appropriate view.  Setting the controls may be redundant if they were
 * used to load this route in the first place, but it ensures that the
 * route always matches the controls and vice versa, no matter if we come
 * here via the controls or directly via URL.
 */
function loadFromRoute(testname, client, start, end, extraFlags) {
  if (!testname) {
    testname = $($('#testselect option')[0]).val();
  }
  $('#testselect').selectOptions(testname);
  if (!client) {
    client = $($('#clientselect option')[0]).val();
  }
  $('#clientselect').selectOptions(client);
  var startDate, endDate;
  if (end) {
    endDate = new Date(end);
  } else {
    endDate = new Date();
    end = ISODateString(endDate);
  }
  if (start) {
    startDate = new Date(start);
  } else {
    startDate = new Date(endDate);
    startDate.setDate(startDate.getDate() - 28);
    start = ISODateString(startDate);
  }
  $('#startentry').val(start);
  $('#endentry').val(end);

  if (extraFlags) {
    extraFlags = extraFlags.split(",");
    if (extraFlags.indexOf("inlineGraph") != -1)
      setInlineGraph();
  }

  loadView(testname, client, start, end);
}

function setInlineGraph() {
  gAsInlineGraph = true;

  // hide a whole pile of stuff
  $("#disptable, #controls").hide();
}

function loading(display) {
  if (display || display === undefined) {
    $('#loading').show();
  } else {
    $('#loading').hide();
  }
}

function getTestData(testname, client, start, end, success, error) {
  var url = 'api/testresults/?testname=' + testname;
  if (client && client != "undefined") {
    url += '&client=' + client;
  }
  if (start && start != "undefined") {
    url += '&start=' + start;
  }
  if (end && end != "undefined") {
    url += '&end=' + end;
  }
  $.ajax({
    type: 'GET',
    url: url,
    success: success,
    error: error
  });
}

function controlFormSubmit() {
  var testname = $('#testselect').selectedValues()[0];
  var client = $('#clientselect').selectedValues()[0];
  var start = $('#startentry').val();
  var end = $('#endentry').val();
  var route = '/' + testname + '/' + client + '/' + start + '/' + end;
  router.setRoute(route);
}

function loadView(testname, client, start, end) {
  loading();
  if (scoreDisplay) {
    scoreDisplay.destroy();
  }

  if (!testname) {
    loading(false);
    $('#title').text('No results to show.');
    $('#results').show();
    return;
  }

  getTestData(testname, client, start, end, function(data) {
    //console.log(data);
    gCurrentScoreDisplay = scoreDisplayFactory(testname, data.results[testname],
                                               data.browsers);
    loading(false);
    gCurrentScoreDisplay.display();
  }, function() {
    loading(false);
    $('#title').text('Error connecting to results server.');
    $('#results').show();
  });
}


function ISODateString(d) {
  function pad(n) { return n < 10 ? '0' + n : n; }
  return d.getUTCFullYear() + '-'
         + pad(d.getUTCMonth() + 1) + '-'
         + pad(d.getUTCDate());
}

$(window).resize(function() {
  if (gAsInlineGraph) {
    // there's padding (20) on the results, so we need to account for it in the width
    // and the height.  We also need to account for the margin on body (10).  The - 5
    // is to avoid a 1px rounding error.
    $(".graph").height(window.innerHeight - 60 - $("#title").height() - 5);
  } else {
    $("#results").width(1100);
    $(".graph").height(600);
  }
});

$(document).ready(function() {
  if (document.location.hash.indexOf("inlineGraph") != -1)
    gAsInlineGraph = true;

  $(window).resize();

  // Configure date controls.
  $.datepicker.setDefaults({
    showOn: "button",
    buttonImage: "images/calendar.png",
    buttonImageOnly: true,
    dateFormat: 'yy-mm-dd'
  });
  $('#startentry').datepicker();
  $('#endentry').datepicker();

  // Populate select boxes.
  $.ajax({
    type: 'GET',
    url: 'api/params/',
    success: function(data) {
      //console.log(data);
      for (var i = 0; i < data.testnames.length; i++) {
        $('#testselect').addOption(data.testnames[i], data.testnames[i],
                                   i == 0);
      }
      for (i = 0; i < data.clients.length; i++) {
        $('#clientselect').addOption(data.clients[i], data.clients[i], 
                                      i == 0);
      }
      $('#controlsform').submit(function() {
        controlFormSubmit();
        return false;
      });
      loading(false);
      $('#controls').show();
      var router = routerFactory();
    },
    error: function() {
      $('#title').text('Error connecting to results server.');
    }
  });
});
