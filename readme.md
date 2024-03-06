# River Level
Docker based webserver that serves prometheus metrics of Environment Agency river level API data.

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
- name guages using api information