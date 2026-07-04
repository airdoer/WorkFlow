# region common
# 因为各个对象存储一般是在线上环境，而在内网的云开发机环境下需要访问，需要配置代理
# 云开发机代理见：https://docs.corp.kuaishou.com/k/home/VFJEZSX6_GTk/fcADIyegUd8U9y93Sa2-Pv84S#section=h.bof1uqpq1qpj
USE_PROXY = True
PROXIES = {
    'http': '10.52.57.90:11080',
    'https': '10.52.57.90:11080'
}

TEST_BUCKET_NAME = "ksgame-c1-test-env"

REPLAY_BUCKET_NAME = "ksgame-c1-test-env"

DEFAULT_BUCKET_NAME = TEST_BUCKET_NAME

OBJECT_C1_REPLAY = "cos-c1-replay-"

OBJECT_C1_VIDEO = "cos-c1-video-"

OBJECT_C1_PICTURE = "cos-c1-picture-"

OBJECT_C1_DESIGNER = "cos-c1-designer-"

# endregion


# region cos

# 用户的 SecretId，建议使用子账号密钥，授权遵循最小权限指引，降低使用风险。子账号密钥获取可参见 https://cloud.tencent.com/document/product/598/37140
COS_SECRET_ID = ""

# 用户的 SecretKey，建议使用子账号密钥，授权遵循最小权限指引，降低使用风险。子账号密钥获取可参见 https://cloud.tencent.com/document/product/598/37140
COS_SECRET_KEY = ""
# 替换为用户的 region，已创建桶归属的 region 可以在控制台查看，https://console.cloud.tencent.com/cos5/bucket
# COS 支持的所有 region 列表参见 https://cloud.tencent.com/document/product/436/6224
COS_REGION = 'ap-shanghai'
# 默认域名:<BucketName-APPID>.cos.ap-shanghai.myqcloud.com

# 如果使用永久密钥不需要填入 token，如果使用临时密钥需要填入，临时密钥生成和使用指引参见 https://cloud.tencent.com/document/product/436/14048
COS_TOKEN = None
# 指定使用 http/https 协议来访问 COS，默认为 https，可不填
COS_SCHEMA = 'https'

COS_APP_ID = "1251911170"

# endregion
