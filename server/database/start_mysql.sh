#!/bin/bash

if [ -n "$1" -a "$1" = 'down' ]
then
    docker compose -f ./mysql.yml down
else
    docker compose -f ./mysql.yml up -d
fi
