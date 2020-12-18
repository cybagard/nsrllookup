# nsrllookup
nsrllookup is a Web API built with Python and Flask. It exposes a route to lookup 
a single MD5 hash and returns "known" or "unkown". 

| Service | main | 
|---------|------|
| Quality | [![Codacy Badge](https://app.codacy.com/project/badge/Grade/f5b1705369794e52b5b46ec11261d46d)](https://www.codacy.com/gh/cybagard/nsrllookup/dashboard?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=cybagard/nsrllookup&amp;utm_campaign=Badge_Grade) | 
| API     | ![Docker Pulls](https://img.shields.io/docker/pulls/cybagard/nsrllookup-api) |
|         | ![Docker Cloud Build Status](https://img.shields.io/docker/cloud/build/cybagard/nsrllookup-api) |
| SVR     | ![Docker Pulls](https://img.shields.io/docker/pulls/cybagard/nsrllookup-svr) |
|         | ![Docker Cloud Build Status](https://img.shields.io/docker/cloud/build/cybagard/nsrllookup-svr) |

This docker service is based on [nsrlsvr](https://github.com/rjhansen/nsrlsvr) & 
[nsrllookup-python](https://github.com/rjhansen/nsrllookup-python) by [rjhansen](https://github.com/rjhansen).

## How to use

### Build your own version
You can use ```docker-compose.build.yml``` to build, test and run your own nsrllookup service.

1.  Build API and run tests

    ```shell script
    docker-compose -f docker-compose.build.yml up --build api-test && 
    docker-compose -f docker-compose.build.yml rm -fsv
    ```

2.  Prepare the environment. (**do this before running any other services**)

    ```shell script
    docker-compose -f docker-compose.build.yml up svr-prepare && 
    docker-compose -f docker-compose.build.yml rm -fsv
    ```
    Follow the container log.

3.  Run it!

    ```shell script
    docker-compose -f docker-compose.build.yml up -d api
    ```
    
### Use the official docker images (no need to build them)

1.  Prepare the environment. (**do this before running any other services**)

    ```shell script
    docker-compose -f docker-compose.prod.yml up svr-prepare && 
    docker-compose -f docker-compose.prod.yml rm -fsv
    ```
    Follow the container log.
   
2.  Run it!

    ```shell script
    docker-compose -f docker-compose.prod.yml up -d api
    ```
   
3.  Wait for the services to become available.

    The nsrllookup-svr service takes some time to load the NSRL RDS hash set. The API service 
    uses docker-compose-wait to wait for nsrllookup-svr to be fully up and running. It exposes port
    5000 once finished.
    
### API Route

Send your MD5 hash to `http://hostname:3000/check/<hash_value>`
