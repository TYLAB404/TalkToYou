import os
import sys

# 关键：清除代理，使用国内极速镜像 hf-mirror.com 直连
for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]:
    os.environ.pop(k, None)

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

from huggingface_hub import hf_hub_download

REPO_ID = "FunAudioLLM/Fun-CosyVoice3-0.5B-2512"
TARGET_DIR = r"D:\AI\models\Fun-CosyVoice3-0.5B-2512"

# 核心需要的 3 个大模型文件
BIG_FILES = [
    "speech_tokenizer_v3.onnx",
    "flow.pt",
    "llm.pt"
]

print("=" * 60)
print(f"正在从国内极速镜像 (hf-mirror.com) 下载剩余的核心大模型文件...")
print(f"目标目录: {TARGET_DIR}")
print("=" * 60)

for filename in BIG_FILES:
    dest_path = os.path.join(TARGET_DIR, filename)
    if os.path.exists(dest_path) and os.path.getsize(dest_path) > 10 * 1024 * 1024:
        print(f"[跳过] 已存在完整文件: {filename} ({os.path.getsize(dest_path) / 1024 / 1024:.2f} MB)")
        continue
    
    print(f"\n>>> 正在下载: {filename} ...")
    try:
        downloaded = hf_hub_download(
            repo_id=REPO_ID,
            filename=filename,
            local_dir=TARGET_DIR,
            local_dir_use_symlinks=False
        )
        print(f"[成功] {filename} 下载完毕！")
    except Exception as e:
        print(f"[失败] 下载 {filename} 失败: {e}", file=sys.stderr)

print("\n" + "=" * 60)
print("所有文件校验完毕！")
print("=" * 60)
