CREATE TABLE SpeedReading (
    id INT AUTO_INCREMENT,
    PRIMARY KEY (id),
    browser_id INT,
    FOREIGN KEY (browser_id) REFERENCES browser(id),
    browser_height INT,
    browser_width INT,
    fps INT,
    totaldraws INT,
    avgduration INT,
    lastduration INT,
    etms INT,
    teststart TIMESTAMP
);
