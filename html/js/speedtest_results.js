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
  if (!points[0].length) {
    $('#title').text('no results');
  } else {
    $('#title').text(this.title);
    this.displayGraph(points[0]);
    this.displayTable(points[1]);
  }
};

ScoreDisplay.prototype.getTestRuns = function() {
  var testRuns = [];
  var byTestStart = {};
  for (var i = 0; i < this.records.length; i++) {
    if (!(this.records[i].teststart in testRuns)) {
      byTestStart[this.records[i].teststart] = [];
    }
    byTestStart[this.records[i].teststart].push(this.records[i]);
  }
  for (var testStart in byTestStart) {
    testRuns.push([testStart, byTestStart[testStart]]);
  }
  testRuns.sort(function(a, b) { return a[0] - b[0]; });
  return testRuns;
};

ScoreDisplay.prototype.getPoints = function() {
  if (!this.records) {
    return [[], []];
  }
  var testRuns = this.getTestRuns();
  var tablePoints = [], graphPoints = [];
  var byBrowser = {};
  var browserNames = [];
  var browserId, browserName, longBrowserName, score;
  for (var i = 0; i < testRuns.length; i++) {
    browserId = testRuns[i][1][0].browser_id;
    score = this.getScore(testRuns[i][1]);
    browserName = this.browsers[browserId].browsername + ' '
                  + this.browsers[browserId].browserversion;
    longBrowserName = browserName;
    if (this.browsers[browserId].browsername == 'Firefox') {
      longBrowserName += ' (build ' + this.browsers[browserId].buildid + ')';
    }
    tablePoints.push([testRuns[i][0], longBrowserName, score]);
    if (!(browserName in byBrowser)) {
      byBrowser[browserName] = [];
      browserNames.push(browserName);
    }
    var testtime = new Date(testRuns[i][0]).getTime();
    byBrowser[browserName].push([testtime, score]);
  }
  browserNames.sort();
  for (i = 0; i < browserNames.length; i++) {
    graphPoints.push({ data: byBrowser[browserNames[i]],
                       label: browserNames[i] });
  }
  return [graphPoints, tablePoints];
};

ScoreDisplay.prototype.displayGraph = function(points) {
  var graphDiv = $('#results .graph');
  var plot = $.plot(graphDiv, points, {
    grid: {
      hoverable: true
    },
    series: {
      lines: { show: true },
      points: { show: true }
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
    }
  });

  function plotHoverFunc() {
    var prevPoint = null;
    return function (event, pos, item) {
      if (item) {
        if (prevPoint != item.datapoint) {
          $('#tooltip').remove();
          prevPoint = item.datapoint;
          var toolTip = $('<div id="tooltip"></div>');
          toolTip.css({
            left: item.pageX + 5,
            top: item.pageY + 5
          });
          toolTip.text(item.series.label + ': ' + item.datapoint[1]);
          $('body').append(toolTip);
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
  var table = $('#templates .resultsdata').clone();
  $('#results .data').html(table);
  this.resultsTable = table.find('table').dataTable({
    aaData: points,
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
    default:
        scoreDisplayClass = FpsScoreDisplay;
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
            on: loadFromRoute
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
function loadFromRoute(testname, machine, start, end) {
  if (!testname) {
    testname = $($('#testselect option')[0]).val();
  }
  $('#testselect').selectOptions(testname);
  if (!machine) {
    machine = $($('#machineselect option')[0]).val();
  }
  $('#machineselect').selectOptions(machine);
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
  loadView(testname, machine, start, end);
}

function loading(display) {
  if (display || display === undefined) {
    $('#loading').show();
  } else {
    $('#loading').hide();
  }
}

function getTestData(testname, machine, start, end, success, error) {
  var url = 'api/testresults/?testname=' + testname;
  if (machine) {
    url += '&ip=' + machine;
  }
  if (start) {
    url += '&start=' + start;
  }
  if (end) {
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
  var machine = $('#machineselect').selectedValues()[0];
  var start = $('#startentry').val();
  var end = $('#endentry').val();
  var route = '/' + testname + '/' + machine + '/' + start + '/' + end;
  router.setRoute(route);
}

function loadView(testname, machine, start, end) {
  loading();
  if (scoreDisplay) {
    scoreDisplay.destroy();
  }
  getTestData(testname, machine, start, end, function(data) {
    scoreDisplay = scoreDisplayFactory(testname, data.results[testname],
                                       data.browsers);
    loading(false);
    scoreDisplay.display();
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


$(document).ready(function() {
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
      for (var i = 0; i < data.testnames.length; i++) {
        $('#testselect').addOption(data.testnames[i], data.testnames[i],
                                   i == 0);
      }
      for (i = 0; i < data.clients.length; i++) {
        $('#machineselect').addOption(data.clients[i][0], data.clients[i][1], 
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
