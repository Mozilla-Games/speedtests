
DROP TABLE IF EXISTS browsers;
CREATE TABLE browsers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(128) NOT NULL,
    version VARCHAR(128) NOT NULL,
    channel INTEGER NOT NULL,
    platform VARCHAR(128) NOT NULL,
    arch VARCHAR(128),
    build VARCHAR(128)
);

-- Tests are organized as follows:
--   Each test run executes a single benchmark on a particular platform and browser.
--   Within each benchmark run, 1 or more iterations may be executed.
--   Each iteration contains a mapping from (testName => score)
DROP TABLE IF EXISTS runs;
CREATE TABLE runs (
    -- uuid for this test run.
    uuid VARCHAR(128) PRIMARY KEY,

    -- browser for this test run
    browser_id INTEGER NOT NULL,

    -- client (machine/device) that executed this test.
    client VARCHAR(128) NOT NULL,

    -- benchmark name
    bench_name VARCHAR(128) NOT NULL,

    -- when the run was started
    start_time TIMESTAMP,

    -- 1 if test run is complete, 0 otherwise
    complete INTEGER(1),

    -- any extra result data for this run
    extra_data TEXT,

    UNIQUE (uuid),
    UNIQUE (uuid),

    FOREIGN KEY (browser_id) REFERENCES browsers (id)
);

DROP TABLE IF EXISTS iterations;
CREATE TABLE iterations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- run id for this iteration
    run_uuid VARCHAR(128) NOT NULL,

    -- iteration number
    iter INTEGER NOT NULL,

    UNIQUE (run_uuid, iter),
    FOREIGN KEY (run_uuid) REFERENCES runs (uuid)
);

DROP TABLE IF EXISTS scores;
CREATE TABLE scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- iteration id for this score
    iteration_id INTEGER NOT NULL,

    -- name of the test
    test_name VARCHAR(128) NOT NULL,

    -- score for the test
    score FLOAT NOT NULL,

    -- window dimensions (innerWidth & innerHeight)
    window_width INTEGER NOT NULL,
    window_height INTEGER NOT NULL,

    -- any extra result data for iteration
    extra_data TEXT,

    UNIQUE (iteration_id, test_name),
    FOREIGN KEY (iteration_id) REFERENCES iterations (id)
);

DROP TABLE IF EXISTS reports;
CREATE TABLE reports (
    run_uuid VARCHAR(128) PRIMARY KEY,
    start_time TIMESTAMP NOT NULL,
    bench_name VARCHAR(128) NOT NULL,
    test_name VARCHAR(128) NOT NULL,
    browser_name VARCHAR(128) NOT NULL,
    browser_channel VARCHAR(128) NOT NULL,
    browser_version VARCHAR(128) NOT NULL,
    browser_build VARCHAR(128) NOT NULL,
    browser_platform VARCHAR(128) NOT NULL,
    mean FLOAT NOT NULL,
    mean_z_95 FLOAT NOT NULL,
    mean_std_err FLOAT NOT NULL,
    published INTEGER(1) DEFAULT 0,
    primary key(run_uuid, bench_name, test_name)
);