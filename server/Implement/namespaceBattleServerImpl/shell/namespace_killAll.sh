#!/bin/bash

apps=`ps -ef | grep -e '--root' -e '--script' | grep -e "_battle_server_1" | grep -v grep | awk '{ printf $2 "\n" }'`
if [ -n "$apps" ];
then
    echo $apps | xargs kill -9
fi