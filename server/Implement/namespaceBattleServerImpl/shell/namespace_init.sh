#!/bin/bash

# 用于建立给定NameSpace的文件夹, 拉取给定svn版本BattleServer, 并将TargetAddress等信息写入

RootPath=$1       # /data/c1/NamespaceBattleServer
SvnVersion=$2     # 472397
Namespace=$3      # dlx
TargetAddress=$4  # 172.28.205.44:30000
ExternalPort=$5   # 40000+
NeedReExport=$6   # False
Index=$7          # 1

HOST_NAME=$(hostname -I | awk '{print $1}')


# kill
apps=`ps -ef | grep -e '--root' -e '--script' | grep -e $Namespace"_battle_server_1" | grep -v grep | awk '{ printf $2 "\n" }'`
if [ -n "$apps" ];
then
    echo $apps | xargs kill -9
fi


# clean
mkdir $RootPath/$Namespace
cd $RootPath/$Namespace
if [ $? -ne 0 ]; then
  echo "Failed to change directory to $RootPath/$Namespace"
  exit 1
fi

if [ "$NeedReExport" = "True" ]; then
    rm -rf BattleServer

    # svn
    svn export svn://172.20.6.1/c1/trunk/DedicatedServer/linux-x64 BattleServer --username c1_packer --password Hzks6666 -r $SvnVersion
    echo $SvnVersion > svnInfo.txt
fi


# config
cd BattleServer/shell/battleServer/namespaceInfo

cat > config.env << EOF
ADDRESS="$TargetAddress"
NAMESPACE="$Namespace"
EOF

battleServerPName=$Namespace"_battle_server_1"
cat > conf.json << EOF
{
    "$battleServerPName": {
        "compressEnabled": true,
        "encryptEnabled": false,
        "encryptCipher": "",
        "rsaPrivateKey": "",

        "ip": "127.0.0.1",
        "port": 40001,
        "external_ip": "$HOST_NAME",
        "external_port":  $ExternalPort
    }
}
EOF

cat > managerConfig.json << EOF
{
    "SvnVersion": "$SvnVersion",
    "Namespace": "$Namespace",
    "TargetAddress": "$TargetAddress",
    "ExternalPort": "$ExternalPort",
    "index": "$Index"
}
EOF


# start
cd ..
bash namespace_server.sh