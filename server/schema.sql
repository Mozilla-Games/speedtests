
DROP TABLE IF EXISTS browsers;
CREATE TABLE browsers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    name TEXT,
    version TEXT,
    platform TEXT,
    geckoversion TEXT,
    buildid TEXT,
    sourcestamp TEXT,

    screenwidth INTEGER,
    screenheight INTEGER
);

DROP TABLE IF EXISTS results;
CREATE TABLE results (
    id INTEGER AUTO_INCREMENT PRIMARY KEY,

    -- the id of the browser that ran this, above
    browser_id INTEGER REFERENCES browser(id),
    -- the client name that executed this test
    client VARCHAR(128),

    -- window dimensions (innerWidth & innerHeight)
    window_width INTEGER,
    window_height INTEGER,

    -- when the test was started
    testtime TIMESTAMP,

    -- the test name
    testname VARCHAR(128),

    -- the final value for this test
    result_value FLOAT,

    -- any extra result data for this test
    extra_data TEXT,

    -- did this run report an error, even though
    -- it reported a value?
    error BOOLEAN
);
