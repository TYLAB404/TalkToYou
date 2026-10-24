import os
import sys
import shutil
import subprocess

try:
    import pilk
    HAS_PILK = True
except ImportError:
    HAS_PILK = False

# 查找本地可用的 ffmpeg 路径（优先系统 PATH 与环境变量）
def get_ffmpeg_path():
    env_ffmpeg = os.environ.get("FFMPEG_PATH")
    if env_ffmpeg and (os.path.exists(env_ffmpeg) or shutil.which(env_ffmpeg)):
        return env_ffmpeg

    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    candidates = [
        r"D:\MediaToolkit\ffmpeg.exe",
        r"D:\ruanJian\MarukoToolbox\tools\ffmpeg.exe",
        r"D:\ruanJian\JYpro\janypro\Jianying_Pro\6.0.1.11779\ffmpeg.exe",
        "/usr/bin/ffmpeg",
        "/usr/local/bin/ffmpeg"
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return "ffmpeg"

FFMPEG_BIN = get_ffmpeg_path()

# 可选独立 Python（若主环境无 pilk 时通过子进程代理，优先环境变量 SILK_PYTHON）
FALLBACK_PYTHON = os.environ.get("SILK_PYTHON", r"D:\geek\python\python3.10.6\python.exe")

def convert_to_silk(input_audio_path: str, output_silk_path: str, sample_rate: int = 24000) -> str:
    """
    将任意音频格式（wav, mp3, m4a 等）转换为腾讯 QQ 原生语音条所需的 Silk v3 格式 (tencent=True)
    """
    if not os.path.exists(input_audio_path):
        raise FileNotFoundError(f"音频源文件不存在: {input_audio_path}")
    
    # 如果当前环境没有 pilk，委托给已有 pilk 的备用 Python 环境
    if not HAS_PILK and FALLBACK_PYTHON and os.path.exists(FALLBACK_PYTHON):
        script_path = os.path.abspath(__file__)
        cmd = [
            FALLBACK_PYTHON,
            script_path,
            "--encode-silk",
            input_audio_path,
            output_silk_path,
            str(sample_rate)
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode != 0:
            raise RuntimeError(f"Silk 代理转码失败: {res.stderr.decode('utf-8', errors='ignore')}")
        return output_silk_path

    if not HAS_PILK:
        raise RuntimeError("系统未检测到 pilk 语音编码库。在 Linux/云服务器部署时，请执行 'pip install pilk' 安装支持。")

    # 本地直接转码
    temp_pcm = output_silk_path + ".temp.pcm"
    try:
        # 1. 使用 ffmpeg 将输入音频转换为 16bit、单声道、指定采样率的原始 PCM (s16le)
        cmd = [
            FFMPEG_BIN,
            "-y",
            "-i", input_audio_path,
            "-f", "s16le",
            "-ar", str(sample_rate),
            "-ac", "1",
            temp_pcm
        ]
        
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode != 0:
            raise RuntimeError(f"FFmpeg 转码 PCM 失败: {res.stderr.decode('utf-8', errors='ignore')}")
        
        # 2. 使用 pilk 将 PCM 编码为带腾讯私有头的 Silk 格式
        pilk.encode(temp_pcm, output_silk_path, pcm_rate=sample_rate, tencent=True)
        return output_silk_path
    finally:
        if os.path.exists(temp_pcm):
            try:
                os.remove(temp_pcm)
            except Exception:
                pass

if __name__ == "__main__":
    if len(sys.argv) >= 5 and sys.argv[1] == "--encode-silk":
        inp = sys.argv[2]
        outp = sys.argv[3]
        sr = int(sys.argv[4])
        convert_to_silk(inp, outp, sr)
        sys.exit(0)
    print(f"当前使用的 FFmpeg 路径: {FFMPEG_BIN}")
