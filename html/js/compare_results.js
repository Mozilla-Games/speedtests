
var router = null;

function routerFactory() {
  router = Router({
    '/([^\/]*)': {
      on: loadFromRoute
    }
  }).init();
  if (document.location.hash == '' || document.location.hash == '#') {
    router.setRoute('/');
  }
  return router;
}

function showResults(data) {
  var tests = {};
  var keys_to_index = { };
  var index = 0;
  for (var key in data) {
    var this_index = index;
    keys_to_index[key] = index++;
    for (var testindex in data[key].result_data) {
      var test = data[key].result_data[testindex];
      var tdesc = test['testDescription'];
      tests[tdesc] = tests[tdesc] || [];
      tests[tdesc][this_index] = test['testResult'];
    }
  }

  var max_index = index;

  $("#results-body").empty();
  for (var test in tests) {
    var tr = $("<tr>");
    tr.append($("<td>" + test + "</td>"));

    var results = tests[test];
    for (var i = 0; i < max_index; ++i) {
      tr.append($("<td>" + results[i] + "</td>"));
    }

    $("#compare-results-body").append(tr);
  }
}

function loadFromRoute(ids) {
  // Populate select boxes.
  $.ajax({
    type: 'GET',
    url: 'api/testdetails/?testids=' + ids,
    success: function(data) {
      showResults(data);
    }
  });
}

$(document).ready(function() {
  router = routerFactory();
});

