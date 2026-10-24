"""
语音转文字 (ASR) 引擎 - 基于 FunASR SenseVoiceSmall
高精度多语言 (中文/英文/粤语/日文/韩文) 自动语音识别与标点恢复
"""

import os
import io
import torch
import numpy as np
import soundfile as sf

_model = None

def get_asr_model():
    global _model
    if _model is None:
        from funasr import AutoModel
        # SenseVoiceSmall 显存占用仅约 400MB，推理超快 (<50ms)
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        print(f"[ASR] 正在初始化 SenseVoiceSmall 语音识别模型 (设备: {device})...")
        _model = AutoModel(
            model="iic/SenseVoiceSmall",
            device=device,
            disable_update=True,
            vad_model="fsmn-vad",
            vad_kwargs={"max_single_segment_time": 30000}
        )
        print("[ASR] SenseVoiceSmall 模型加载就绪！")
    return _model

def transcribe(audio_path_or_bytes, language="auto") -> dict:
    """
    识别音频中的文字并恢复标点
    :param audio_path_or_bytes: 本地音频路径 (str) 或 音频二进制 (bytes)
    :param language: 语种，默认 auto (支持 zh, en, yue, ja, ko)
    :return: {"text": str, "clean_text": str}
    """
    import re
    from funasr.utils.postprocess_utils import rich_transcription_postprocess

    model = get_asr_model()
    
    temp_file = None
    input_path = audio_path_or_bytes
    if isinstance(audio_path_or_bytes, bytes):
        import tempfile
        temp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        temp.write(audio_path_or_bytes)
        temp.close()
        temp_file = temp.name
        input_path = temp_file

    try:
        res = model.generate(
            input=input_path,
            cache={},
            language=language,
            use_itn=True,
            batch_size_s=60,
            merge_vad=True,
            merge_length_s=15,
        )

        raw_text = ""
        if res and len(res) > 0:
            raw_text = res[0].get("text", "")

        # 过滤 SenseVoice 的标签 (如 <|zh|><|NEUTRAL|><|Speech|><|woitn|>)
        cleaned = rich_transcription_postprocess(raw_text)
        # 去掉多余的尖括号标签
        cleaned = re.sub(r'<\|.*?\|>', '', cleaned).strip()

        return {
            "success": True,
            "text": cleaned,
            "raw": raw_text
        }
    finally:
        if temp_file and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except Exception:
                pass
