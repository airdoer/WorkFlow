export P4CONFIG=/app/p4/.p4config
if [ -z "$P4PASSWD" ]; then
	echo "P4PASSWD 环境变量未设置，无法登录 p4" >&2
	exit 1
fi
echo "$P4PASSWD" | p4 login