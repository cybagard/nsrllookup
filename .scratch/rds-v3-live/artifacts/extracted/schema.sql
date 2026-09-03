CREATE TABLE FILE (
 sha256     VARCHAR NOT NULL,
 sha1       VARCHAR NOT NULL,
 md5        VARCHAR NOT NULL,
 crc32      VARCHAR NOT NULL,
 file_name  VARCHAR NOT NULL,
 file_size  INTEGER NOT NULL,
 package_id INTEGER NOT NULL,
 CONSTRAINT PK_FILE__FILE PRIMARY KEY (sha256, sha1, md5, crc32, file_name, file_size, package_id)
);
CREATE TABLE MFG (
 manufacturer_id INTEGER NOT NULL,
 name            VARCHAR NOT NULL,
 CONSTRAINT PK_MFG__MFG_ID PRIMARY KEY (manufacturer_id)
);
CREATE TABLE OS (
 operating_system_id INTEGER NOT NULL,
 name                VARCHAR NOT NULL,	
 version             VARCHAR NOT NULL,
 manufacturer_id     INTEGER NOT NULL,
 CONSTRAINT PK_OS__OS_ID PRIMARY KEY (operating_system_id, manufacturer_id)
);
CREATE TABLE PKG (
 package_id          INTEGER NOT NULL,
 name                VARCHAR NOT NULL,
 version             VARCHAR NOT NULL,
 operating_system_id INTEGER NOT NULL,
 manufacturer_id     INTEGER NOT NULL,
 language            VARCHAR NOT NULL,
 application_type    VARCHAR NOT NULL,
 CONSTRAINT PK_PGK__PKG_ID PRIMARY KEY (package_id, operating_system_id, manufacturer_id, language, application_type)
);
CREATE TABLE VERSION (
 version      VARCHAR UNIQUE NOT NULL,
 build_set    VARCHAR NOT NULL,
 build_date   TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
 release_date TIMESTAMP NOT NULL,
 description  VARCHAR NOT NULL,
 CONSTRAINT PK_VERSION__VERSION PRIMARY KEY (version)
);
CREATE VIEW DISTINCT_HASH AS
 SELECT DISTINCT
  sha256,
  sha1,
  md5,
  crc32
 FROM
  FILE
;
