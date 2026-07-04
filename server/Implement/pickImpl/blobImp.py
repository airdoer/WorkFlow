import boto3
import threading
from botocore.config import Config

import config

class BlobImp():
    def __init__(self):
        self.endpoint_url = config.endpoint_url
        self.access_key = config.aws_access_key_id
        self.secret_key = config.aws_secret_access_key
        self.bucket_name = config.bucket_name
        self.region_name = config.region_name
        # 使用线程本地存储为每个线程维护独立的客户端
        self._thread_local = threading.local()

    def create_client(self):
        """为当前线程创建一个新的 S3 客户端"""
        # 配置：减少并发连接，增加超时时间
        s3_config = Config(
            signature_version='s3v4',
            s3={'addressing_style': 'path'},
            max_pool_connections=5,  # 限制连接池大小
            retries={'max_attempts': 3, 'mode': 'adaptive'},  # 自动重试
            connect_timeout=30,
            read_timeout=60
        )
        
        s3_client = boto3.client(
            's3',
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region_name,
            config=s3_config
        )
        return s3_client
    
    def get_client(self):
        """获取当前线程的客户端（懒加载）"""
        if not hasattr(self._thread_local, 'client') or self._thread_local.client is None:
            self._thread_local.client = self.create_client()
        return self._thread_local.client

    def download(self, key, file_path):
        """下载文件，为每个请求使用独立的客户端"""
        try:
            client = self.get_client()
            # 确保目录存在
            import os
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            client.download_file(
                Bucket=self.bucket_name,
                Key=key,
                Filename=file_path
            )
            return True, ""
        except Exception as e:
            return False, str(e)

    def list_objects(self, prefix, max_keys=1000):
        """列出对象"""
        try:
            client = self.get_client()
            response = client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=max_keys
            )
            
            objects = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    objects.append({
                        'key': obj['Key'],
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'].isoformat()
                    })
            
            return True, objects
        except Exception as e:
            return False, str(e)
    
    def close(self):
        """关闭当前线程的客户端连接"""
        if hasattr(self._thread_local, 'client') and self._thread_local.client is not None:
            try:
                self._thread_local.client.close()
            except Exception:
                pass
            self._thread_local.client = None
