import os
import sys

# 设置代理（匹配本地系统代理 127.0.0.1:7897）
os.environ["HTTP_PROXY"] = "http://127.0.0.1:7897"
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7897"

from huggingface_hub import snapshot_download

REPO_ID = "FunAudioLLM/Fun-CosyVoice3-0.5B-2512"
TARGET_DIR = r"D:\AI\models\Fun-CosyVoice3-0.5B-2512"

print(f"==================================================")
print(f"开始自动下载 CosyVoice3 模型: {REPO_ID}")
print(f"目标存放路径: {TARGET_DIR}")
print(f"支持断点续传，请稍候...")
print(f"==================================================")

os.makedirs(TARGET_DIR, exist_ok=True)

try:
    downloaded_path = snapshot_download(
        repo_id=REPO_ID,
        local_dir=TARGET_DIR,
        local_dir_use_symlinks=False,
        resume_download=True,
        max_workers=4,
    )
    print(f"\n[OK] 模型下载完成！保存在: {downloaded_path}")
except Exception as e:
    print(f"\n[ERROR] 下载过程中发生异常: {e}", file=sys.stderr)
    sys.exit(1)
