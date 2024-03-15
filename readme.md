# River Level
Docker based services that serves prometheus metrics of Environment Agency river level API data using the prometheus python client. 

Available in AMD, and ARM builds.
## Pre Reqs
- docker (including compose)

## Deploy
Either:
1. Copy docker-compose-example.yml to docker-compose.yml and update as required
1. cd to project folder
1. run `docker-compose up -d` 

## To Do
- set default values via build args
- describe guages using api information - DONE
- name guages using api information e.g. 'river_level' should be keynsham_rivermeads_river_level - DONE
- make the module detect the OS and if linux do the environment variables - DONE
- if the reading is 0m then skip updating gauge