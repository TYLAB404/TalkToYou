import os
import sys

# 清理代理，直接走国内高速通道
for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]:
    os.environ.pop(k, None)

from modelscope import snapshot_download

MODEL_ID = "FunAudioLLM/Fun-CosyVoice3-0.5B-2512"
TARGET_DIR = r"D:\AI\models\Fun-CosyVoice3-0.5B-2512"

print("=" * 60)
print(f"正在通过国内 ModelScope (阿里云高速节点) 下载:")
print(f"模型仓库: {MODEL_ID}")
print(f"目标目录: {TARGET_DIR}")
print("=" * 60)

# 排除冗余版本（onnx/rl），只下载 PyTorch 原生核心，极速提速！
ignore_file_patterns = [
    "*.batch.onnx",
    "flow.decoder.estimator.fp32.onnx",
    "llm.rl.pt"
]

try:
    path = snapshot_download(
        model_id=MODEL_ID,
        local_dir=TARGET_DIR,
        ignore_patterns=ignore_file_patterns
    )
    print(f"\n[OK] 下载完成！模型路径: {path}")
except Exception as e:
    print(f"\n[ERROR] 下载异常: {e}", file=sys.stderr)
    sys.exit(1)
