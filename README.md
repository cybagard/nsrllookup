# nsrllookup

nsrllookup is a Web API built with Python and Flask. It exposes a route to lookup 
a single MD5 hash and returns "known" or "unkown". 

This docker service is based on [nsrlsvr](https://github.com/rjhansen/nsrlsvr) & 
[nsrllookup-python](https://github.com/rjhansen/nsrllookup-python) by [rjhansen](https://github.com/rjhansen).

##How to use

###Build your own version
You can use ```docker-compose.test.yml``` and ```docker-compose.prod.yml``` to build, 
test and run your own nsrllookup service.

###Use the official docker images (no need to build them)

1. Prepare the environment. (**do this before running any other services**)

    ```
    docker-compose -f docker-compose.hub.yml up svr-prepare && 
    docker-compose -f docker-compose.hub.yml rm -fsv
    ```
   Follow the container log.
   
2. Run it!

    ```
    docker-compose -f docker-compose.hub.yml up -d api
    ```
   
3. Wait for the services to become available.

   The nsrllookup-svr service takes some time to load the NSRL RDS hash set. The API service 
   uses docker-compose-wait to wait for nsrllookup-svr to be fully available. It exposes port
   5000 once it is finished.

