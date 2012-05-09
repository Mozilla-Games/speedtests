CREATE TABLE V8 (
    id INT AUTO_INCREMENT,
    PRIMARY KEY (id),
    browser_id INT,
    FOREIGN KEY (browser_id) REFERENCES browser(id),
    browser_height INT,
    browser_width INT,
    score INT,
    Richards INT,
    DeltaBlue INT,
    Crypto INT,
    RayTrace INT,
    EarleyBoyer INT,
    RegExp_ INT,
    Splay INT,
    NavierStokes INT,
    teststart TIMESTAMP,
    ip VARCHAR(15) COLLATE utf8_bin
);
