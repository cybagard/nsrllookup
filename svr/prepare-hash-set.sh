#!/bin/bash

pwd
wget https://s3.amazonaws.com/rds.nsrl.nist.gov/RDS/current/rds_modernm.zip
unzip rds_modernm.zip
echo "nsrlupdate started"
nsrlupdate rds_modernm/NSRLFile.txt