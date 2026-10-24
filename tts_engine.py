import os
import sys
import json
import uuid
import asyncio
import edge_tts
try:
    import torch
    HAS_TORCH = True
except ImportError:
    torch = None
    HAS_TORCH = False
import soundfile as sf
import numpy as np
from scipy import signal
import subprocess
from typing import List, Dict, Any, Optional, Tuple
from audio_converter import convert_to_silk, FFMPEG_BIN

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VOICES_FILE = os.path.join(BASE_DIR, "voices", "voices.json")
CUSTOMS_DIR = os.path.join(BASE_DIR, "voices", "customs")
EMOTIONS_DIR = os.path.join(BASE_DIR, "voices", "emotions")
EMOTIONS_FILE = os.path.join(BASE_DIR, "voices", "emotions.json")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

COSYVOICE_CODE_DIR = os.environ.get("COSYVOICE_CODE_DIR", r"D:\AI\CosyVoice")
MATCHA_CODE_DIR = os.environ.get("MATCHA_CODE_DIR", r"D:\AI\CosyVoice\third_party\Matcha-TTS")
MODEL_DIR = os.environ.get("COSYVOICE_MODEL_DIR", r"D:\AI\models\Fun-CosyVoice3-0.5B-2512")

INDEX_CODE_DIR = os.environ.get("INDEX_CODE_DIR", r"D:\AI\IndexTTS-2")
INDEX_CHECKPOINTS_DIR = os.environ.get("INDEX_CHECKPOINTS_DIR", r"D:\AI\IndexTTS-2\checkpoints")

if os.path.isdir(COSYVOICE_CODE_DIR) and COSYVOICE_CODE_DIR not in sys.path:
    sys.path.append(COSYVOICE_CODE_DIR)
if os.path.isdir(MATCHA_CODE_DIR) and MATCHA_CODE_DIR not in sys.path:
    sys.path.append(MATCHA_CODE_DIR)
if os.path.isdir(INDEX_CODE_DIR) and INDEX_CODE_DIR not in sys.path:
    sys.path.append(INDEX_CODE_DIR)

import re

def clean_and_split_text(text: str, max_chars: int = 50) -> List[str]:
    """
    智能清洗并切分文本：
    1. 过滤连续重复的标点
    2. 拆分句子，确保每段都有真实可发音的文字内容（汉字/字母/数字）
    3. 彻底杜绝空句或纯标点触发 edge-tts 长时间卡死挂起
    """
    if not text:
        return []

    # 将多个连续标点压缩为单个
    text = re.sub(r'([。！？!?；;，,\.\n\r\t ])\1+', r'\1', text)

    delimiters = r'([。！？!?；;\n]+)'
    parts = re.split(delimiters, text)

    sentences = []
    current = ""
    for part in parts:
        if not part:
            continue
        if re.match(r'^[。！？!?；;\n]+$', part):
            current += part
            if len(current) >= 15:
                if re.search(r'[\u4e00-\u9fa5a-zA-Z0-9]', current):
                    sentences.append(current.strip())
                current = ""
        else:
            if len(current) + len(part) > max_chars:
                if re.search(r'[\u4e00-\u9fa5a-zA-Z0-9]', current):
                    sentences.append(current.strip())
                current = part
            else:
                current += part

    if current.strip() and re.search(r'[\u4e00-\u9fa5a-zA-Z0-9]', current):
        sentences.append(current.strip())

    valid = [s for s in sentences if re.search(r'[\u4e00-\u9fa5a-zA-Z0-9]', s)]
    return valid if valid else [text.strip()]

# ================= IndexTTS2 8维情感基底向量定义 =================
# 严格按照 IndexTTS2 官方向量顺序:
# [0: 高兴, 1: 愤怒, 2: 悲伤, 3: 恐惧, 4: 反感, 5: 低落, 6: 惊讶, 7: 自然]
EMOTION_PRESETS = {
    "coquettish": {
        "name": "撒娇卖萌 / 甜美娇嗔",
        "vector": [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.25, 0.0],
        "keywords": ["撒娇", "可爱", "甜美", "卖萌", "娇嗔", "娇羞", "开心", "欢快", "兴奋", "喜悦", "俏皮", "宠溺", "萌萌"]
    },
    "crying": {
        "name": "伤心哭腔 / 悲痛哽咽",
        "vector": [0.0, 0.0, 1.0, 0.0, 0.0, 0.35, 0.0, 0.0],
        "keywords": ["哭腔", "哭", "伤心", "难过", "悲伤", "痛苦", "哽咽", "泣", "心碎", "泪", "凄惨", "抽泣"]
    },
    "angry": {
        "name": "暴躁愤怒 / 严厉质问",
        "vector": [0.0, 1.0, 0.0, 0.0, 0.2, 0.0, 0.0, 0.0],
        "keywords": ["愤怒", "生气", "暴怒", "火大", "质问", "凶", "暴躁", "发火", "怒吼", "气愤", "吵架"]
    },
    "melancholic": {
        "name": "委屈可怜 / 失落低落",
        "vector": [0.0, 0.0, 0.25, 0.0, 0.0, 1.0, 0.0, 0.0],
        "keywords": ["委屈", "低落", "沮丧", "难受", "抑郁", "失落", "叹气", "无精打采", "自责", "可怜", "闷闷不乐"]
    },
    "fearful": {
        "name": "恐惧慌张 / 战战兢兢",
        "vector": [0.0, 0.0, 0.0, 1.0, 0.0, 0.1, 0.3, 0.0],
        "keywords": ["害怕", "恐惧", "慌张", "慌乱", "颤抖", "战战兢兢", "哆嗦", "吓死", "惊恐", "怯生生"]
    },
    "surprised": {
        "name": "震惊诧异 / 难以置信",
        "vector": [0.2, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0],
        "keywords": ["惊讶", "震惊", "吃惊", "难以置信", "不敢相信", "目瞪口呆", "诧异", "天哪", "哇塞"]
    },
    "disgusted": {
        "name": "嫌弃反感 / 鄙视傲慢",
        "vector": [0.0, 0.2, 0.0, 0.0, 1.0, 0.0, 0.0, 0.1],
        "keywords": ["反感", "嫌弃", "鄙视", "厌恶", "傲慢", "不耐烦", "冷淡", "看不起", "恶心"]
    },
    "calm": {
        "name": "平静自然 / 日常随性",
        "vector": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        "keywords": ["平静", "自然", "日常", "平淡", "闲聊", "正常", "普通", "随性", "淡定"]
    }
}

def match_emotion_vector(text: Optional[str]) -> Tuple[Optional[List[float]], Optional[str]]:
    """
    智能语义关键词直通匹配：
    若用户输入'我要撒娇的'、'带哭腔'等，直接精准命中纯净情感向量，彻底跳过 QwenEmotion 幻觉与耗时
    """
    if not text or not text.strip():
        return None, None
    t = text.strip()
    for preset_key, info in EMOTION_PRESETS.items():
        for kw in info["keywords"]:
            if kw in t:
                return list(info["vector"]), info["name"]
    return None, None

def adjust_audio_speed_wsola(wav_path: str, speed_pct: int) -> bool:
    """
    使用广播级 WSOLA (波形相似度重叠累加) 算法调节音频语速：
    - 彻底杜绝相位声码器 (librosa) 的重音、回音、金属失真
    - 纯时域波形对齐拉伸，完美保留共振峰与吐字清晰度
    :param wav_path: 音频 WAV 文件绝对路径
    :param speed_pct: 语速调节百分比 (-50 ~ +50)，负数减慢，正数加快
    """
    if speed_pct == 0 or not os.path.exists(wav_path):
        return True

    # 换算为速度因子：例如 -20% -> 0.8x; +20% -> 1.2x
    factor = 1.0 + (speed_pct / 100.0)
    factor = max(0.5, min(2.0, factor))

    temp_wav = wav_path + ".stretched.wav"
    try:
        cmd = [
            FFMPEG_BIN,
            "-y",
            "-i", wav_path,
            "-filter:a", f"atempo={factor:.3f}",
            "-vn",
            temp_wav
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode == 0 and os.path.exists(temp_wav) and os.path.getsize(temp_wav) > 100:
            os.replace(temp_wav, wav_path)
            print(f"[WSOLA 广播级语速调节] 语速倍率: {factor:.2f}x ({speed_pct}%)，已完美消除回音与重音！")
            return True
        else:
            err = res.stderr.decode('utf-8', errors='ignore')
            print(f"[WSOLA 语速调节跳过] {err}")
            return False
    except Exception as e:
        print(f"[WSOLA 语速调节异常] {e}")
        return False
    finally:
        if os.path.exists(temp_wav):
            try:
                os.remove(temp_wav)
            except Exception:
                pass

class TTSEngine:
    def __init__(self):
        self._ensure_dirs()
        self._cosyvoice_model = None
        self._indextts2_model = None
        self._voices_cache = None

    def _ensure_dirs(self):
        os.makedirs(CUSTOMS_DIR, exist_ok=True)
        os.makedirs(EMOTIONS_DIR, exist_ok=True)
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        if not os.path.exists(VOICES_FILE):
            with open(VOICES_FILE, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=2)
        if not os.path.exists(EMOTIONS_FILE):
            with open(EMOTIONS_FILE, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=2)

    def get_all_emotions(self) -> List[Dict[str, Any]]:
        """获取所有独立情感预设"""
        try:
            with open(EMOTIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def add_emotion_preset(self, name: str, audio_bytes: bytes, filename: str) -> Dict[str, Any]:
        """保存一个新的情感参考预设，供随时复用"""
        emo_id = f"emo_{uuid.uuid4().hex[:8]}"
        ext = os.path.splitext(filename)[1].lower() or ".wav"
        save_name = f"{emo_id}{ext}"
        save_path = os.path.join(EMOTIONS_DIR, save_name)
        with open(save_path, "wb") as f:
            f.write(audio_bytes)

        new_emo = {
            "id": emo_id,
            "name": name,
            "filename": save_name,
            "audio_path": save_path,
            "audio_url": f"/voices/emotions/{save_name}"
        }
        emotions = self.get_all_emotions()
        emotions.append(new_emo)
        with open(EMOTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(emotions, f, ensure_ascii=False, indent=2)
        return new_emo

    def delete_emotion_preset(self, emo_id: str) -> bool:
        """删除指定情感预设"""
        emotions = self.get_all_emotions()
        target = None
        new_list = []
        for e in emotions:
            if e["id"] == emo_id:
                target = e
            else:
                new_list.append(e)
        if not target:
            return False
        if target.get("audio_path") and os.path.exists(target["audio_path"]):
            try:
                os.remove(target["audio_path"])
            except Exception:
                pass
        with open(EMOTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(new_list, f, ensure_ascii=False, indent=2)
        return True

    def get_cosyvoice_model(self):
        """单例加载 CosyVoice 声音克隆模型 (GPU fp16)"""
        if not HAS_TORCH:
            raise RuntimeError("系统未安装 PyTorch。本地模型克隆需要 torch 与 GPU 环境，请使用 RunningHub 云端工作流或 Edge-TTS。")
        if self._cosyvoice_model is None:
            # 释放 IndexTTS-2 及其缓存，确保显存和内存绝对充裕，避免 Windows 发生 PCIe 内存交换
            if self._indextts2_model is not None:
                print(f"[显存优化] 释放 IndexTTS-2 显存，全速让路给 CosyVoice...")
                del self._indextts2_model
                self._indextts2_model = None
                import gc; gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()

            print(f"[CosyVoice] 正在将声音克隆大模型加载到 GPU 显存 (fp16)...")
            from cosyvoice.cli.cosyvoice import AutoModel
            self._cosyvoice_model = AutoModel(model_dir=MODEL_DIR, fp16=True)
            print(f"[CosyVoice] 大模型加载就绪，可随时进行高保真声纹克隆！")
        return self._cosyvoice_model

    def get_indextts2_model(self):
        """单例加载 IndexTTS2 情感解耦声音克隆大模型 (GPU fp16)"""
        if not HAS_TORCH:
            raise RuntimeError("系统未安装 PyTorch。本地模型克隆需要 torch 与 GPU 环境，请使用 RunningHub 云端工作流或 Edge-TTS。")
        if self._indextts2_model is None:
            # 释放 CosyVoice 及其缓存，确保显存和内存绝对充裕，避免 Windows 发生 PCIe 内存交换
            if self._cosyvoice_model is not None:
                print(f"[显存优化] 释放 CosyVoice 显存，全速让路给 IndexTTS-2...")
                del self._cosyvoice_model
                self._cosyvoice_model = None
                import gc; gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()

            print(f"[IndexTTS2] 正在将 IndexTTS-2 旗舰级情感解耦声音克隆大模型加载至 GPU (fp16)...")
            from indextts.infer_v2 import IndexTTS2
            cfg_path = os.path.join(INDEX_CHECKPOINTS_DIR, "config.yaml")
            # use_qwen_emo=False 避免载入 1.8B LLM 霸占额外 3.5GB 显存与 4GB 内存（系统已有 rule-based 情绪向量匹配）
            self._indextts2_model = IndexTTS2(
                cfg_path=cfg_path,
                model_dir=INDEX_CHECKPOINTS_DIR,
                use_fp16=True,
                device="cuda:0" if torch.cuda.is_available() else "cpu",
                use_qwen_emo=False
            )
            print(f"[IndexTTS2] IndexTTS-2 大模型加载就绪！显存纯净，无 PCIe 溢出风险！")
        return self._indextts2_model

    def get_all_voices(self) -> List[Dict[str, Any]]:
        """获取所有音色（带内存缓存，消除无谓的反复磁盘 I/O）"""
        if self._voices_cache is not None:
            return list(self._voices_cache)

        voices = []
        try:
            with open(VOICES_FILE, "r", encoding="utf-8") as f:
                voices = json.load(f)
        except Exception:
            voices = []

        # 动态附带 RunningHub BreezeTTS2 云端 8 位人设立体角色
        try:
            from runninghub_engine import BREEZE_SPEAKERS
            for spk in BREEZE_SPEAKERS:
                voices.append({
                    "id": f"breeze_{spk['id']}",
                    "name": f"Breeze - {spk['name']} ({spk['desc']})",
                    "type": "breeze",
                    "gender": spk["gender"],
                    "description": spk["desc"],
                    "engine": "runninghub_breeze",
                    "speaker_id": spk["id"]
                })
        except Exception:
            pass

        self._voices_cache = voices
        return list(voices)

    def get_voice_by_id(self, voice_id: str) -> Optional[Dict[str, Any]]:
        for v in self.get_all_voices():
            if v["id"] == voice_id:
                return v
        return None

    def add_custom_voice(
        self,
        name: str,
        description: str,
        audio_bytes: bytes,
        filename: str,
        prompt_text: str = "",
        emotion_audio_bytes: Optional[bytes] = None,
        emotion_filename: Optional[str] = None,
        emotion_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        添加一个新的自定义预设音色（保存用户上传的人声录音和参考文字，并支持可选绑定情感音频）
        """
        voice_id = f"custom_{uuid.uuid4().hex[:8]}"
        ext = os.path.splitext(filename)[1].lower() or ".wav"
        save_audio_filename = f"{voice_id}{ext}"
        save_audio_path = os.path.join(CUSTOMS_DIR, save_audio_filename)

        with open(save_audio_path, "wb") as f:
            f.write(audio_bytes)

        emotion_audio_path = None
        emotion_audio_url = None
        if emotion_audio_bytes and len(emotion_audio_bytes) > 0:
            e_ext = os.path.splitext(emotion_filename or "emo.wav")[1].lower() or ".wav"
            e_filename = f"{voice_id}_emotion{e_ext}"
            emotion_audio_path = os.path.join(CUSTOMS_DIR, e_filename)
            with open(emotion_audio_path, "wb") as f:
                f.write(emotion_audio_bytes)
            emotion_audio_url = f"/voices/customs/{e_filename}"

        new_voice = {
            "id": voice_id,
            "name": name,
            "type": "custom",
            "gender": "custom",
            "description": description or "用户自定义克隆音色",
            "engine": "cosyvoice",
            "prompt_audio": save_audio_path,
            "prompt_audio_url": f"/voices/customs/{save_audio_filename}",
            "prompt_text": prompt_text,
            "emotion_audio": emotion_audio_path,
            "emotion_audio_url": emotion_audio_url,
            "emotion_name": emotion_name if emotion_audio_path else None
        }

        voices = self.get_all_voices()
        voices.append(new_voice)
        with open(VOICES_FILE, "w", encoding="utf-8") as f:
            json.dump(voices, f, ensure_ascii=False, indent=2)
        self._voices_cache = None

        return new_voice

    def delete_custom_voice(self, voice_id: str) -> bool:
        """删除指定的自定义音色及其关联的情感音频"""
        voices = self.get_all_voices()
        target_voice = None
        new_voices = []
        for v in voices:
            if v["id"] == voice_id:
                target_voice = v
            else:
                new_voices.append(v)

        if not target_voice:
            return False

        if target_voice.get("type") == "preset":
            raise ValueError("系统预设音色不可删除")

        audio_path = target_voice.get("prompt_audio")
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except Exception:
                pass

        emotion_audio = target_voice.get("emotion_audio")
        if emotion_audio and os.path.exists(emotion_audio):
            try:
                os.remove(emotion_audio)
            except Exception:
                pass

        with open(VOICES_FILE, "w", encoding="utf-8") as f:
            json.dump(new_voices, f, ensure_ascii=False, indent=2)
        self._voices_cache = None

        return True

    async def synthesize(
        self,
        text: str,
        voice_id: str,
        engine: str = "cosyvoice",
        speed_pct: int = 0,
        mood: str = "auto",
        pitch_hz: int = 0,
        emotion_mode: str = "none",
        emotion_prompt: Optional[str] = None,
        emotion_audio_path: Optional[str] = None,
        emo_vector: Optional[List[float]] = None,
        emo_intensity: float = 1.0
    ) -> Dict[str, Any]:
        """
        将文本合成语音，支持 CosyVoice 与 IndexTTS2 双引擎切换，并自动转码为 QQ 原生 Silk 格式
        :param text: 要合成的文本
        :param voice_id: 音色 ID
        :param engine: AI 引擎 ('cosyvoice' 或 'indextts2')
        :param speed_pct: 语速微调 (-50 ~ +50)
        :param mood: 语气风格 (CosyVoice 专用)
        :param pitch_hz: 语调高低 (-15 ~ +15)
        :param emotion_mode: 情感模式 ('none', 'audio', 'text')
        :param emotion_prompt: 自然语言情感描述 (如 '非常委屈哽咽的哭腔' 或 '我要撒娇的')
        :param emotion_audio_path: 独立情感参考音频路径 (实现音色与情感解耦)
        :param emo_vector: 8维显式情感向量 (可选直接传入)
        :param emo_intensity: 情感表现强度倍率 (0.5 ~ 1.5)
        """
        voice = self.get_voice_by_id(voice_id)
        if not voice:
            all_v = self.get_all_voices()
            voice = all_v[0] if all_v else {
                "id": "preset_xiaoxiao",
                "name": "温柔知性姐姐",
                "engine": "edge",
                "voice_code": "zh-CN-XiaoxiaoNeural"
            }

        audio_id = uuid.uuid4().hex
        output_wav = os.path.join(OUTPUT_DIR, f"{audio_id}.wav")
        output_silk = os.path.join(OUTPUT_DIR, f"{audio_id}.silk")

        # ------------ RunningHub 云端工作流合成（零本地显存占用） ------------
        from runninghub_engine import runninghub_engine, load_runninghub_config
        rh_cfg = load_runninghub_config()

        is_rh_engine = (
            engine in ("runninghub", "runninghub_indextts2", "runninghub_breeze", "2113835289022435330", "2113847965285941250")
            or rh_cfg.get("enabled", True)
        )
        if is_rh_engine:
            # 确定具体工作流 ID
            if engine in ("runninghub_breeze", "2113847965285941250") or voice_id.startswith("breeze_") or voice.get("type") == "breeze":
                target_wfid = "2113847965285941250"
            elif engine in ("runninghub_indextts2", "2113835289022435330", "indextts2"):
                target_wfid = "2113835289022435330"
            else:
                target_wfid = rh_cfg.get("active_workflow", "2113835289022435330")

            # 提取 BreezeTTS2 的角色名
            breeze_spk = None
            if voice_id.startswith("breeze_"):
                breeze_spk = voice_id.replace("breeze_", "")
            elif voice_id in ("Alice", "Bob", "Carol", "David", "Emma", "Frank", "Grace", "Henry"):
                breeze_spk = voice_id
            elif voice.get("speaker_id"):
                breeze_spk = voice["speaker_id"]

            return await runninghub_engine.synthesize(
                text=text,
                workflow_id=target_wfid,
                speaker=breeze_spk,
                emotion_prompt=emotion_prompt,
                emo_vector=emo_vector,
                emo_intensity=emo_intensity
            )

        if engine == "indextts2":
            # ---------------- IndexTTS2 旗舰情感解耦引擎 ----------------
            spk_prompt = voice.get("prompt_audio")
            if spk_prompt and not os.path.isabs(spk_prompt):
                spk_prompt = os.path.join(BASE_DIR, spk_prompt)
            temp_prompt = None

            # 若所选角色无本地参考音频，使用自定义声音或生成临时音色参考
            if not spk_prompt or not os.path.exists(spk_prompt):
                # 优先选用已有的自定义声音参考
                candidates = [
                    os.path.join(CUSTOMS_DIR, f)
                    for f in os.listdir(CUSTOMS_DIR)
                    if f.endswith(".wav")
                ] if os.path.exists(CUSTOMS_DIR) else []

                if candidates:
                    spk_prompt = candidates[0]
                else:
                    # 自动生成 3 秒参考音频以作为声纹锚点
                    temp_prompt = os.path.join(OUTPUT_DIR, f"temp_spk_{audio_id}.wav")
                    v_code = voice.get("voice_code", "zh-CN-XiaoxiaoNeural")
                    comm = edge_tts.Communicate(text="你好，今天天气真不错，很高兴与你相遇。", voice=v_code)
                    await asyncio.wait_for(comm.save(temp_prompt), timeout=10.0)
                    spk_prompt = temp_prompt

            emo_audio = None
            use_emo_text = False
            emo_text = None
            resolved_emo_vector = emo_vector

            if emotion_mode == "audio":
                if emotion_audio_path and os.path.exists(emotion_audio_path):
                    emo_audio = emotion_audio_path
                elif voice.get("emotion_audio") and os.path.exists(voice["emotion_audio"]):
                    emo_audio = voice["emotion_audio"]
            elif emotion_mode == "text" or (emotion_prompt and emotion_prompt.strip()):
                # 1. 优先使用智能语义关键词匹配（避免 QwenEmotion 误判与极慢推理）
                matched_vec, preset_name = match_emotion_vector(emotion_prompt)
                if matched_vec is not None:
                    scale = max(0.2, min(1.5, emo_intensity))
                    resolved_emo_vector = [round(v * scale, 4) for v in matched_vec]
                    print(f"[IndexTTS2 语义情绪匹配] 关键词精准命中 -> 情绪风格: 【{preset_name}】, 最终向量: {resolved_emo_vector}")
                elif resolved_emo_vector is not None:
                    scale = max(0.2, min(1.5, emo_intensity))
                    resolved_emo_vector = [round(v * scale, 4) for v in resolved_emo_vector]
                else:
                    use_emo_text = True
                    emo_text = emotion_prompt.strip()
            elif emotion_mode == "none" and voice.get("emotion_audio") and os.path.exists(voice["emotion_audio"]):
                emo_audio = voice["emotion_audio"]

            try:
                def _run_indextts2():
                    model = self.get_indextts2_model()
                    gen = model.infer(
                        spk_audio_prompt=spk_prompt,
                        text=text,
                        output_path=output_wav,
                        emo_audio_prompt=emo_audio,
                        emo_vector=resolved_emo_vector,
                        use_emo_text=use_emo_text,
                        emo_text=emo_text,
                        num_beams=1,
                        temperature=0.8,
                        top_p=0.8,
                        top_k=30
                    )
                    for _ in gen:
                        pass

                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, _run_indextts2)

                # 广播级 WSOLA 语速微调 (彻底杜绝 librosa 相位声码器带来的回音与重音，真实放缓/加速吐字)
                if speed_pct != 0 and os.path.exists(output_wav):
                    adjust_audio_speed_wsola(output_wav, speed_pct)

            finally:
                if temp_prompt and os.path.exists(temp_prompt):
                    try:
                        os.remove(temp_prompt)
                    except Exception:
                        pass

        else:
            # ---------------- CosyVoice / Edge 引擎 ----------------
            engine_type = voice.get("engine", "edge")

            if engine_type == "cosyvoice":
                prompt_audio = voice.get("prompt_audio")
                if not prompt_audio or not os.path.exists(prompt_audio):
                    raise FileNotFoundError(f"未找到该音色的参考音频文件: {prompt_audio}")

                # 确保参考音频严格 <= 20 秒，防止触发 CosyVoice 30s 限制
                d_prompt, sr_prompt = sf.read(prompt_audio)
                trimmed_prompt = None
                if len(d_prompt) / sr_prompt > 20.0:
                    d_prompt = d_prompt[: int(20.0 * sr_prompt)]
                    trimmed_prompt = os.path.join(OUTPUT_DIR, f"trimmed_prompt_{audio_id}.wav")
                    sf.write(trimmed_prompt, d_prompt, sr_prompt)
                    prompt_audio = trimmed_prompt

                # 语气风格映射（告别刻板生硬的播音腔，让底模具备真实生活口吻）
                base_pitch = pitch_hz
                if mood == "chat_male":
                    base_voice = "zh-CN-YunxiNeural"         # 阳光自然少年日常
                elif mood == "chat_female":
                    base_voice = "zh-TW-HsiaoChenNeural"     # 极度生活化的柔和日常腔，零播音感
                elif mood == "chat_sweet":
                    base_voice = "zh-TW-HsiaoChenNeural"     # 甜美温柔
                    base_pitch += 3
                elif mood == "lively_girl":
                    base_voice = "zh-CN-XiaoyiNeural"        # 元气活泼少女
                    base_pitch += 2
                elif mood == "lively_northeast":
                    base_voice = "zh-CN-liaoning-XiaobeiNeural" # 诙谐生动东北腔
                elif mood == "deep_man":
                    base_voice = "zh-CN-YunjianNeural"       # 沉稳磁性男声
                    base_pitch -= 4
                elif mood == "broadcast":
                    base_voice = "zh-CN-XiaoxiaoNeural"      # 传统严谨播音腔
                else:
                    # auto: 默认优先采用生活化闲聊腔
                    base_voice = "zh-CN-YunxiNeural" if voice.get("gender") == "male" else "zh-TW-HsiaoChenNeural"

                rate_str = f"+{speed_pct}%" if speed_pct >= 0 else f"{speed_pct}%"
                pitch_str = f"+{base_pitch}Hz" if base_pitch >= 0 else f"{base_pitch}Hz"

                # 智能清洗与分句（过滤无意义标点，确保每段有实际文字且 <= 50字）
                text_chunks = clean_and_split_text(text, max_chars=50)
                chunk_wav_paths = []

                try:
                    for idx, chunk_text in enumerate(text_chunks):
                        chunk_source_wav = os.path.join(OUTPUT_DIR, f"src_{audio_id}_{idx}.wav")
                        chunk_source_16k = os.path.join(OUTPUT_DIR, f"src16k_{audio_id}_{idx}.wav")

                        comm = edge_tts.Communicate(text=chunk_text, voice=base_voice, rate=rate_str, pitch=pitch_str)
                        await asyncio.wait_for(comm.save(chunk_source_wav), timeout=12.0)

                        d, sr = sf.read(chunk_source_wav)
                        if d.ndim > 1:
                            d = d[:, 0]
                        d16 = signal.resample(d, int(len(d) * 16000 / sr)).astype(np.float32)
                        sf.write(chunk_source_16k, d16, 16000)
                        chunk_wav_paths.append((chunk_source_wav, chunk_source_16k))

                    def _run_cosyvoice():
                        model = self.get_cosyvoice_model()
                        all_chunk_tensors = []

                        for _, chunk_16k in chunk_wav_paths:
                            outputs = []
                            for j in model.inference_vc(chunk_16k, prompt_audio, stream=False):
                                outputs.append(j['tts_speech'])
                            if outputs:
                                all_chunk_tensors.append(torch.concat(outputs, dim=1))

                        if not all_chunk_tensors:
                            raise RuntimeError("CosyVoice 未能生成有效声音数据")

                        pause_samples = int(0.12 * model.sample_rate)
                        silence = torch.zeros((1, pause_samples), dtype=all_chunk_tensors[0].dtype, device=all_chunk_tensors[0].device)

                        final_parts = []
                        for i, t in enumerate(all_chunk_tensors):
                            if i > 0:
                                final_parts.append(silence)
                            final_parts.append(t)

                        final_audio = torch.concat(final_parts, dim=1)
                        sf.write(output_wav, final_audio.squeeze().cpu().numpy(), model.sample_rate)

                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, _run_cosyvoice)
                finally:
                    for src_wav, src_16k in chunk_wav_paths:
                        for p in (src_wav, src_16k):
                            if os.path.exists(p):
                                try:
                                    os.remove(p)
                                except Exception:
                                    pass
                    if trimmed_prompt and os.path.exists(trimmed_prompt):
                        try:
                            os.remove(trimmed_prompt)
                        except Exception:
                            pass

            else:
                # 官方预设音色 (Edge-TTS)
                voice_code = voice.get("voice_code", "zh-CN-XiaoxiaoNeural")
                rate_str = f"+{speed_pct}%" if speed_pct >= 0 else f"{speed_pct}%"
                communicate = edge_tts.Communicate(text=text, voice=voice_code, rate=rate_str)
                await asyncio.wait_for(communicate.save(output_wav), timeout=15.0)

        # 转换为 QQ 原生 Silk 格式
        convert_to_silk(output_wav, output_silk, sample_rate=24000)

        return {
            "audio_id": audio_id,
            "text": text,
            "voice_name": voice.get("name"),
            "wav_path": output_wav,
            "silk_path": output_silk,
            "wav_url": f"/audio/{audio_id}.wav",
            "silk_url": f"/audio/{audio_id}.silk"
        }

tts_engine = TTSEngine()
