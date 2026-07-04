#!/bin/bash

RootPath=$1       # /data/c1/NamespaceBattleServer
Namespace=$2      # dlx

# kill
apps=`ps -ef | grep -e '--root' -e '--script' | grep -e $Namespace"_battle_server_1" | grep -v grep | awk '{ printf $2 "\n" }'`
if [ -n "$apps" ];
then
    echo $apps | xargs kill -9
fi


# clean
cd $RootPath
rm -rf $Namespace
exit 0