import logging as logger
from typing import BinaryIO
from qcloud_cos import CosConfig
from qcloud_cos import CosS3Client
from qcloud_cos import cos_exception
from lib.object_storage.server import config

cos_client: CosS3Client = None

cos_exceptions = cos_exception.CosException

# --- 注意 cos封装的各个接口本质上是requests库调用的封装，是同步的！！


# 1. 设置用户属性, 包括 secret_id, secret_key, region等。Appid 已在 CosConfig 中移除，请在参数 Bucket 中带上 Appid。Bucket 由 BucketName-Appid 组成
def init_cos_client():
    global cos_client
    if cos_client is not None:
        return

    # 服务端发送的是使用永久密钥，所以Token为None
    # 一个进程对于一个region只需要生成一个CosS3Client实例，然后循环上传或下载对象，不能每次访问都生成 CosS3Client 实例，否则 python 进程会占用过多的连接和线程。
    proxies = None
    if config.USE_PROXY:
        proxies = config.PROXIES
    cos_config = CosConfig(Region=config.COS_REGION, SecretId=config.COS_SECRET_ID, SecretKey=config.COS_SECRET_KEY,
                           Token=config.COS_TOKEN, Scheme=config.COS_SCHEMA, Proxies=proxies)
    cos_client = CosS3Client(cos_config)
    return cos_client


# 创建存储桶
def create_bucket(bucket_name):
    full_bucket_name = bucket_name + '-' + config.COS_APP_ID
    response = cos_client.create_bucket(
        Bucket=full_bucket_name
    )
    logger.info(f"create_bucket {response = }")
    return response


# 查询存储桶列表
def list_bucket():
    response = cos_client.list_buckets()
    return response


def bucket_exists(bucket_name):
    full_bucket_name = bucket_name + '-' + config.COS_APP_ID
    return cos_client.bucket_exists(Bucket=full_bucket_name)


def object_exists(bucket_name, key):
    full_bucket_name = bucket_name + '-' + config.COS_APP_ID
    response = cos_client.object_exists(
        Bucket=full_bucket_name,
        Key=key)
    return response


# 查询对象元信息
def head_object(bucket_name, key):
    full_bucket_name = bucket_name + '-' + config.COS_APP_ID
    response = cos_client.head_object(
        Bucket=full_bucket_name,
        Key=key)
    return response


# 上传对象(bytes)
def upload_object_bytes(bucket_name: str, key: str, content: bytes):
    full_bucket_name = bucket_name + '-' + config.COS_APP_ID
    response = cos_client.put_object(
        Bucket=full_bucket_name,
        Body=content,
        Key=key,
        EnableMD5=False
    )
    logger.info(f"upload_object_bytes {response = }")
    return response


# 上传对象(file)
def upload_object_file(bucket_name: str, key: str, file_path: str):
    # 根据文件大小自动选择简单上传或分块上传，分块上传具备断点续传功能。
    full_bucket_name = bucket_name + '-' + config.COS_APP_ID
    response = cos_client.upload_file(
        Bucket=full_bucket_name,
        LocalFilePath=file_path,
        Key=key,
        PartSize=1,
        MAXThread=10,
        EnableMD5=False
    )
    logger.info(f"upload_object_file {response = }")
    return response


# 上传对象(stream)
def upload_object_stream(bucket_name: str, key: str, url: str):
    import requests
    stream = requests.get(url)
    full_bucket_name = bucket_name + '-' + config.COS_APP_ID
    # 网络流将以 Transfer-Encoding:chunked 的方式传输到 COS
    response = cos_client.put_object(
        Bucket=full_bucket_name,
        Body=stream,
        Key=key
    )
    logger.info(f"upload_object_stream {response = }")
    return response


# 上传对象(追加写方式)
def upload_object_append(bucket_name: str, key: str, content: [bytes, BinaryIO], position: int = 0):
    '''
    '''
    full_bucket_name = bucket_name + '-' + config.COS_APP_ID
    response = cos_client.append_object(
        Bucket=full_bucket_name,
        Key=key,
        Position=position,
        Data=content,
    )
    logger.info(f"upload_object_append {response = }")
    return response['x-cos-next-append-position']


# 查询对象列表
def list_objects(bucket_name: str, key_prefix: str):
    # 单次调用 list_objects 接口一次只能查询1000个对象，如需要查询所有的对象，则需要循环调用。不建议检索遍历cos
    full_bucket_name = bucket_name + '-' + config.COS_APP_ID
    response = cos_client.list_objects(
        Bucket=full_bucket_name,
        Prefix=key_prefix
    )
    return response


def list_objects_iter(bucket_name: str, key_prefix: str, count):
    full_bucket_name = bucket_name + '-' + config.COS_APP_ID

    marker = ""
    while marker is not None:
        response = cos_client.list_objects(
            Bucket=full_bucket_name, Prefix=key_prefix, Marker=marker, MaxKeys=count)
        if 'Contents' in response:
            # yield from (content['Key'] for content in response['Contents'])
            for content in response['Contents']:
                yield content['Key']

        if response['IsTruncated'] == 'false':
            break

        marker = response.get("NextMarker", None)


# 下载对象到文件
def download_object_file(bucket_name: str, key: str, file_path: str):
    full_bucket_name = bucket_name + '-' + config.COS_APP_ID
    response = cos_client.get_object(
        Bucket=full_bucket_name,
        Key=key,
    )
    # response['Body'] 是对requests.model.Response的封装
    response['Body'].get_stream_to_file(file_path)
    return response


# 下载对象到stream
def download_object_stream(bucket_name: str, key: str):
    full_bucket_name = bucket_name + '-' + config.COS_APP_ID
    response = cos_client.get_object(
        Bucket=full_bucket_name,
        Key=key,
    )
    fp = response['Body'].get_raw_stream()
    return fp


# 删除object
def delete_object(bucket_name: str, key: str):
    full_bucket_name = bucket_name + '-' + config.COS_APP_ID
    response = cos_client.delete_object(
        Bucket=full_bucket_name,
        Key=key
    )
    logger.info(f"delete_object {response = }")
    return response


# 删除多个object
def delete_objects(bucket_name: str, keys: list[str]):
    full_bucket_name = bucket_name + '-' + config.COS_APP_ID
    response = cos_client.delete_objects(
        Bucket=full_bucket_name,
        Delete={
            'Object': [{'Key': k} for k in keys],
            'Quiet': 'true'
        }
    )
    logger.info(f"delete_objects {response = }")
    return response


# 生成上传预签名URL
def get_presigned_upload_url(bucket_name: str, key: str, expired_time: int = 120):
    # 生成上传 URL，未限制请求头部和请求参数
    full_bucket_name = bucket_name + '-' + config.COS_APP_ID
    url = cos_client.get_presigned_url(
        Method='PUT',
        Bucket=full_bucket_name,
        Key=key,
        Expired=expired_time  # 120秒后过期，过期时间请根据自身场景定义
    )
    return url


# 生成下载预签名URL
def get_presigned_download_url(bucket_name: str, key: str, expired_time: int = 120):
    # 生成上传 URL，未限制请求头部和请求参数
    full_bucket_name = bucket_name + '-' + config.COS_APP_ID
    url = cos_client.get_presigned_url(
        Method='GET',
        Bucket=full_bucket_name,
        Key=key,
        Expired=expired_time  # 120秒后过期，过期时间请根据自身场景定义
    )
    return url
