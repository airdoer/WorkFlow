#!/bin/bash
set -e

# 使用 .p4config 自动配置

# export P4CONFIG=/app/p4/.p4config
# 登录
if [ -z "$P4PASSWD" ]; then
	echo "P4PASSWD 环境变量未设置，无法登录 p4" >&2
	exit 1
fi
echo "$P4PASSWD" | p4 login

# Stream + Sparse Sync / LimitView：创建两个 stream workspace 并限制视图到 Hotfix 目录
create_or_update_stream_workspace() {
	local ws_name="$1"
	local stream_name="$2"
	local ws_root="$3"
	local limit1="$4"
	local limit2="$5"

	mkdir -p "$ws_root"

	echo "准备 P4 workspace '$ws_name' (Stream: $stream_name)"

	local base_spec=""
	if p4 clients -e "$ws_name" 2>/dev/null | grep -q "Client $ws_name "; then
		base_spec="$(p4 client -o "$ws_name")"
	else
		base_spec="$(p4 client -S "$stream_name" -o "$ws_name")"
	fi

	local spec_with_limit=""
	spec_with_limit="$(
		printf "%s\n" "$base_spec" | awk -v root="$ws_root" -v stream="$stream_name" -v l1="$limit1" -v l2="$limit2" '
			BEGIN { skipBlock=0; printedLimit=0 }
			function printLimit() {
				print "LimitView:"
				print "\t" l1
				print "\t" l2
				printedLimit=1
			}
			{
				if (skipBlock==1) {
					if ($0 ~ /^\t/) { next }
					skipBlock=0
				}

				if ($0 ~ /^Root:/) { print "Root:\t" root; next }
				if ($0 ~ /^Host:/) { print "Host:"; next }
				if ($0 ~ /^Stream:/) { print "Stream:\t" stream; next }
				if ($0 ~ /^Options:/) { print "Options:\tnoallwrite noclobber nocompress unlocked nomodtime normdir"; next }
				if ($0 ~ /^SubmitOptions:/) { print "SubmitOptions:\tsubmitunchanged"; next }
				if ($0 ~ /^LineEnd:/) { print "LineEnd:\tlocal"; next }

				if ($0 ~ /^LimitView:/) { printLimit(); skipBlock=1; next }

				if ($0 ~ /^View:/ && printedLimit==0) { printLimit() } 
				print
			}
			END { if (printedLimit==0) { printLimit() } }
		'
	)"

	if printf "%s\n" "$spec_with_limit" | p4 client -i; then
		echo "P4 workspace '$ws_name' 已就绪（包含 LimitView）"
	elif printf "%s\n" "$spec_with_limit" | p4 client -f -i; then
		echo "P4 workspace '$ws_name' 已就绪（包含 LimitView，强制更新）"
	else
		echo "P4 workspace '$ws_name' 设置 LimitView 失败，回退为不设置 LimitView"
		printf "%s\n" "$base_spec" | awk -v root="$ws_root" -v stream="$stream_name" '
			BEGIN { skipBlock=0 }
			{
				if (skipBlock==1) {
					if ($0 ~ /^\t/) { next }
					skipBlock=0
				}
				if ($0 ~ /^Root:/) { print "Root:\t" root; next }
				if ($0 ~ /^Host:/) { print "Host:"; next }
				if ($0 ~ /^Stream:/) { print "Stream:\t" stream; next }
				if ($0 ~ /^Options:/) { print "Options:\tnoallwrite noclobber nocompress unlocked nomodtime normdir"; next }
				if ($0 ~ /^SubmitOptions:/) { print "SubmitOptions:\tsubmitunchanged"; next }
				if ($0 ~ /^LineEnd:/) { print "LineEnd:\tlocal"; next }
				if ($0 ~ /^LimitView:/) { skipBlock=1; next }
				print
			}
		' | p4 client -i && echo "P4 workspace '$ws_name' 已就绪（不含 LimitView）" || {
			printf "%s\n" "$base_spec" | awk -v root="$ws_root" -v stream="$stream_name" '
				BEGIN { skipBlock=0 }
				{
					if (skipBlock==1) {
						if ($0 ~ /^\t/) { next }
						skipBlock=0
					}
					if ($0 ~ /^Root:/) { print "Root:\t" root; next }
					if ($0 ~ /^Host:/) { print "Host:"; next }
					if ($0 ~ /^Stream:/) { print "Stream:\t" stream; next }
					if ($0 ~ /^Options:/) { print "Options:\tnoallwrite noclobber nocompress unlocked nomodtime normdir"; next }
					if ($0 ~ /^SubmitOptions:/) { print "SubmitOptions:\tsubmitunchanged"; next }
					if ($0 ~ /^LineEnd:/) { print "LineEnd:\tlocal"; next }
					if ($0 ~ /^LimitView:/) { skipBlock=1; next }
					print
				}
			' | p4 client -f -i
			echo "P4 workspace '$ws_name' 已就绪（不含 LimitView，强制更新）"
		}
	fi
}

# create_or_update_stream_workspace \
# 	"hotfix_mainline_mini_workspace" \
# 	"//C7/Development/Mainline" \
# 	"/app/p4MiniWorkSpace/Mainline" \
# 	"//C7/Development/Mainline/Server/hotfix/..."

# create_or_update_stream_workspace \
# 	"hotfix_weekly_mini_workspace" \
# 	"//C7/Development/Weekly" \
# 	"/app/p4MiniWorkSpace/Weekly" \
# 	"//C7/Development/Weekly/Server/hotfix/..."

# create_or_update_stream_workspace \
# 	"hotfix_preonline_mini_workspace" \
# 	"//C7/Release/Preonline" \
# 	"/app/p4MiniWorkSpace/Preonline" \
# 	"//C7/Release/Preonline/Server/hotfix/..."

p4 info

# 执行原始命令，例如 python app.py
exec "$@"
