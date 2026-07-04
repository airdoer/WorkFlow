#!/bin/bash

if [ -n "$1" -a "$1" = 'down' ]
then
    docker compose -f ./redis.yml down
else
    docker compose -f ./redis.yml up -d
fi
