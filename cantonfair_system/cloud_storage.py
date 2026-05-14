# ============================================================
# CantonFair Pro — 云存储管理模块
# 支持: Cloudflare R2 / AWS S3 / 阿里云 OSS / 本地文件
# ============================================================
import os
import io
import hashlib
import shutil
import tempfile
from pathlib import Path
from typing import Optional

try:
    import boto3
    from botocore.config import Config as BotoConfig
    from botocore.exceptions import ClientError
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False


class CloudStorage:
    """
    统一云存储接口
    自动检测环境变量，判断使用 R2/S3 还是本地文件
    """

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.account_id = os.environ.get('R2_ACCOUNT_ID', '')
        self.access_key = os.environ.get('R2_ACCESS_KEY_ID', '')
        self.secret_key = os.environ.get('R2_SECRET_ACCESS_KEY', '')
        self.bucket = os.environ.get('R2_BUCKET_NAME', 'cantonfair-data')
        self.data_key = os.environ.get('R2_DATA_FILE_KEY', '广交会数据综合整理_标准格式.xlsx')
        self.public_url = os.environ.get('R2_PUBLIC_URL', '')
        self.local_fallback = os.environ.get('LOCAL_DATA_FILE', '../广交会数据综合整理_标准格式.xlsx')

        self._client = None
        self._use_cloud = self._should_use_cloud()
        self._cache_dir = self._get_cache_dir()

    def _should_use_cloud(self) -> bool:
        """判断是否使用云存储"""
        if not self.account_id or not self.access_key or not self.secret_key:
            return False
        return True

    def _get_cache_dir(self) -> Path:
        cache = Path(tempfile.gettempdir()) / 'cantonfair_cache'
        cache.mkdir(parents=True, exist_ok=True)
        return cache

    @property
    def client(self):
        """懒加载 S3 客户端（R2 兼容 S3 API）"""
        if self._client is None and self._use_cloud:
            self._client = boto3.client(
                's3',
                endpoint_url=f'https://{self.account_id}.r2.cloudflarestorage.com',
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name='auto',
                config=BotoConfig(
                    signature_version='s3v4',
                    retries={'max_attempts': 3, 'mode': 'standard'},
                    connect_timeout=30,
                    read_timeout=60,
                )
            )
        return self._client

    def _get_cache_path(self) -> Path:
        """获取本地缓存文件路径"""
        filename = f"{self.data_key}.cache"
        return self._cache_dir / filename

    def _get_etag_hash(self, s3_etag: str) -> str:
        """从 S3 ETag 提取 hash"""
        return s3_etag.strip('"').strip("'")

    def download(self, force: bool = False) -> Optional[str]:
        """
        下载数据文件到本地缓存
        优先使用本地文件 > 云存储缓存 > 云存储下载
        Returns: 本地文件路径 或 None
        """
        cache_path = self._get_cache_path()

        # 1. 优先使用本地文件
        local_file = self._find_local_file()
        if local_file and not force:
            print(f"[CloudStorage] 使用本地文件: {local_file}")
            return local_file

        if local_file and force:
            print(f"[CloudStorage] 强制刷新，使用本地文件: {local_file}")
            return local_file

        # 2. 云存储模式
        if self._use_cloud:
            try:
                # 检查缓存是否新鲜
                if cache_path.exists() and not force:
                    local_etag = self._file_md5(cache_path)[:8]
                    try:
                        resp = self.client.head_object(Bucket=self.bucket, Key=self.data_key)
                        remote_etag = resp.get('ETag', '').strip('"')
                        if local_etag == remote_etag:
                            print(f"[CloudStorage] 使用缓存（同版本）: {cache_path}")
                            return str(cache_path)
                    except Exception:
                        pass

                # 下载
                print(f"[CloudStorage] 从 R2 下载: {self.bucket}/{self.data_key}")
                self.client.download_file(self.bucket, self.data_key, str(cache_path))
                print(f"[CloudStorage] 下载完成，保存到: {cache_path}")
                return str(cache_path)

            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')
                if error_code == '404':
                    print(f"[CloudStorage] R2 中未找到文件: {self.data_key}")
                else:
                    print(f"[CloudStorage] R2 下载失败: {e}")
                # 回退到本地
                if local_file:
                    return local_file

        # 3. 纯本地模式
        if local_file:
            return local_file

        print("[CloudStorage] 警告: 无法找到数据文件！")
        return None

    def _find_local_file(self) -> Optional[str]:
        """在多个可能的位置查找本地数据文件"""
        search_paths = [
            Path(self.local_fallback),
            Path(__file__).parent.parent / '广交会数据综合整理_标准格式.xlsx',
            Path.cwd() / '广交会数据综合整理_标准格式.xlsx',
            Path.home() / 'cantonfair_data' / '广交会数据综合整理_标准格式.xlsx',
        ]

        for p in search_paths:
            if p.exists():
                return str(p.resolve())

        # 也支持直接是相对路径的相对于 cwd
        if os.path.exists(self.local_fallback):
            return os.path.abspath(self.local_fallback)

        return None

    def _file_md5(self, path: Path) -> str:
        """计算文件 MD5"""
        md5 = hashlib.md5()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                md5.update(chunk)
        return md5.hexdigest()

    def upload(self, local_file: str) -> bool:
        """上传本地文件到 R2"""
        if not self._use_cloud:
            print("[CloudStorage] 未配置云存储，跳过上传")
            return False
        try:
            print(f"[CloudStorage] 上传到 R2: {self.bucket}/{self.data_key}")
            self.client.upload_file(local_file, self.bucket, self.data_key)
            print("[CloudStorage] 上传完成")
            return True
        except Exception as e:
            print(f"[CloudStorage] 上传失败: {e}")
            return False

    def get_presigned_url(self, expires: int = 3600) -> Optional[str]:
        """生成预签名 URL（私有桶访问）"""
        if not self._use_cloud:
            return None
        try:
            url = self.client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket, 'Key': self.data_key},
                ExpiresIn=expires
            )
            return url
        except Exception as e:
            print(f"[CloudStorage] 生成预签名URL失败: {e}")
            return None

    def clear_cache(self) -> int:
        """清理本地缓存，返回清理的文件数"""
        count = 0
        for f in self._cache_dir.glob('*.cache'):
            f.unlink()
            count += 1
        print(f"[CloudStorage] 清理了 {count} 个缓存文件")
        return count

    def get_status(self) -> dict:
        """获取存储状态"""
        status = {
            'mode': 'cloud' if self._use_cloud else 'local',
            'cache_dir': str(self._cache_dir),
            'cache_exists': self._get_cache_path().exists(),
            'local_exists': self._find_local_file() is not None,
            'bucket': self.bucket,
            'data_key': self.data_key,
        }

        if self._use_cloud:
            try:
                resp = self.client.head_object(Bucket=self.bucket, Key=self.data_key)
                status['cloud_size_mb'] = round(resp['ContentLength'] / 1024 / 1024, 1)
                status['cloud_etag'] = resp.get('ETag', '').strip('"')
                status['cloud_last_modified'] = str(resp.get('LastModified', ''))
            except Exception as e:
                status['cloud_error'] = str(e)

        return status


# ---------- R2 预热脚本 ----------
def warmup_cache():
    """部署后预热缓存（Railway startCommand 中调用）"""
    storage = CloudStorage()
    path = storage.download()
    if path:
        print(f"[Warmup] 数据就绪: {path}")
    else:
        print("[Warmup] 警告: 数据文件不可用")


# ---------- 独立下载脚本 ----------
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='CantonFair 数据下载工具')
    parser.add_argument('--force', action='store_true', help='强制重新下载')
    parser.add_argument('--upload', type=str, metavar='FILE', help='上传本地文件到 R2')
    parser.add_argument('--status', action='store_true', help='查看存储状态')
    args = parser.parse_args()

    storage = CloudStorage()

    if args.status:
        import json
        print(json.dumps(storage.get_status(), indent=2, ensure_ascii=False))
    elif args.upload:
        storage.upload(args.upload)
    else:
        path = storage.download(force=args.force)
        if path:
            print(f"数据路径: {path}")
        else:
            print("错误: 无法获取数据文件")
