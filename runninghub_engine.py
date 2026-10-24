import os
import json
import time
import uuid
import asyncio
import aiohttp
import requests
import subprocess
import urllib.parse
from typing import List, Dict, Any, Optional
from audio_converter import convert_to_silk, FFMPEG_BIN
from security import encrypt_str, decrypt_str, mask_api_key

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
CUSTOMS_DIR = os.path.join(BASE_DIR, "voices", "customs")
PRESETS_DIR = os.path.join(BASE_DIR, "voices", "presets")
CONFIG_PATH = os.path.join(BASE_DIR, "runninghub_config.json")
RUNNINGHUB_BASE_URL = "https://www.runninghub.cn"
RUNNINGHUB_AI_URL = "https://www.runninghub.ai"

# BreezeTTS2 8位预设角色的工作流节点映射规格
BREEZE_SPEAKER_SPECS = [
    {
        "id": "Alice",
        "slot": 1,
        "name_node": "2",
        "clone_mode_node": "3",
        "audio_node": "4",
        "crop_node": "5",
        "instruction_node": "100",
        "default_name": "Alice",
        "default_clone_mode": True,  # 工作流原版 Alice 默认为克隆模式
        "default_instruction": "温暖清晰的年轻女声，语调平和，普通话标准，语速适中。",
        "default_audio": "57866b24bbad2ff1c537c83a4ff2a77a3007eac94cada0fd3ef67ed941a515a8.mp3",
        "default_audio_label": "Alice 官方预设原声音频",
        "gender": "女声",
        "color": "purple"
    },
    {
        "id": "Bob",
        "slot": 2,
        "name_node": "13",
        "clone_mode_node": "14",
        "audio_node": "15",
        "crop_node": "16",
        "instruction_node": "103",
        "default_name": "Bob",
        "default_clone_mode": False,
        "default_instruction": "低沉稳重的男声，略带磁性，语速稍慢，普通话标准。",
        "default_audio": "455171f03c25d54129af190b95a12848089d21fc61a398b59c5b484252e4e69d.flac",
        "default_audio_label": "Bob 官方预设原声音频",
        "gender": "男声",
        "color": "blue"
    },
    {
        "id": "Carol",
        "slot": 3,
        "name_node": "24",
        "clone_mode_node": "25",
        "audio_node": "26",
        "crop_node": "27",
        "instruction_node": "105",
        "default_name": "Carol",
        "default_clone_mode": False,
        "default_instruction": "活泼明亮的少女声，语速轻快，带着笑意。",
        "default_audio": "719477257c995fcb67bda307e08bf341f20fd1775f7cae1c2d2b276a3c28af47.mp3",
        "default_audio_label": "Carol 官方预设原声音频",
        "gender": "女声",
        "color": "pink"
    },
    {
        "id": "David",
        "slot": 4,
        "name_node": "35",
        "clone_mode_node": "36",
        "audio_node": "37",
        "crop_node": "38",
        "instruction_node": "106",
        "default_name": "David",
        "default_clone_mode": False,
        "default_instruction": "成熟浑厚的中年男声，气息沉稳，吐字清晰。",
        "default_audio": "dfb0ae81ed2177efb825d85f55614ac5dccf19826646605c5f053ed31d57915a.mp3",
        "default_audio_label": "David 官方预设原声音频",
        "gender": "男声",
        "color": "indigo"
    },
    {
        "id": "Emma",
        "slot": 5,
        "name_node": "46",
        "clone_mode_node": "47",
        "audio_node": "48",
        "crop_node": "49",
        "instruction_node": "108",
        "default_name": "Emma",
        "default_clone_mode": False,
        "default_instruction": "温柔舒缓的知性女声，轻声细语，节奏从容。",
        "default_audio": "bfe9e3b92304dabb9cf6888b7182895ae6fd3e8fa302a8be10a552fb18d61464.mp3",
        "default_audio_label": "Emma 官方预设原声音频",
        "gender": "女声",
        "color": "emerald"
    },
    {
        "id": "Frank",
        "slot": 6,
        "name_node": "57",
        "clone_mode_node": "58",
        "audio_node": "59",
        "crop_node": "60",
        "instruction_node": "110",
        "default_name": "Frank",
        "default_clone_mode": False,
        "default_instruction": "沙哑有磁性的烟嗓男声，低沉有力，语速偏慢。",
        "default_audio": "719477257c995fcb67bda307e08bf341f20fd1775f7cae1c2d2b276a3c28af47.mp3",
        "default_audio_label": "Frank 官方预设原声音频",
        "gender": "男声",
        "color": "amber"
    },
    {
        "id": "Grace",
        "slot": 7,
        "name_node": "68",
        "clone_mode_node": "69",
        "audio_node": "70",
        "crop_node": "71",
        "instruction_node": "112",
        "default_name": "Grace",
        "default_clone_mode": False,
        "default_instruction": "甜美清脆的年轻女声，干净利落，略带俏皮。",
        "default_audio": "6f15ed193a3ac9960e86da252c9268322e970a0041812af38e893894bbb39014.mp3",
        "default_audio_label": "Grace 官方预设原声音频",
        "gender": "女声",
        "color": "rose"
    },
    {
        "id": "Henry",
        "slot": 8,
        "name_node": "79",
        "clone_mode_node": "80",
        "audio_node": "81",
        "crop_node": "82",
        "instruction_node": "114",
        "default_name": "Henry",
        "default_clone_mode": False,
        "default_instruction": "沉稳老练的年长男声，语速平缓，语气郑重。",
        "default_audio": "719477257c995fcb67bda307e08bf341f20fd1775f7cae1c2d2b276a3c28af47.mp3",
        "default_audio_label": "Henry 官方预设原声音频",
        "gender": "男声",
        "color": "slate"
    }
]

def build_default_speakers_config() -> Dict[str, Any]:
    res = {}
    for spec in BREEZE_SPEAKER_SPECS:
        res[spec["id"]] = {
            "name": spec["default_name"],
            "clone_mode": spec["default_clone_mode"],
            "instruction": spec["default_instruction"],
            "audio_file": spec["default_audio"],
            "audio_label": spec["default_audio_label"],
            "preview_url": ""
        }
    return res

DEFAULT_CONFIG = {
    "enabled": True,
    "api_key_encrypted": "",
    "key_name": "默认主账号",
    "active_workflow": "2113847965285941250",
    "workflows": {
        "2113835289022435330": {
            "name": "IndexTTS2 旗舰情感克隆工作流",
            "type": "indextts2",
            "description": "基于 IndexTTS2 旗舰级情感解耦声音克隆大模型，支持自然语言情绪微调与情绪强度控制。"
        },
        "2113847965285941250": {
            "name": "BreezeTTS2 多角色AI语音工作流",
            "type": "breezetts2",
            "description": "包含 8 位高拟真人设角色，支持每位角色独立设定名字、特点描述、克隆音色或上传音频。"
        }
    },
    "breeze_settings": {
        "active_speaker": "Alice",
        "high_precision": False,
        "speakers": build_default_speakers_config()
    },
    "indextts2_settings": {
        "temperature": 0.8,
        "top_p": 0.8,
        "top_k": 30,
        "num_beams": 3,
        "emo_alpha": 1.0
    }
}


def load_runninghub_config() -> Dict[str, Any]:
    if not os.path.exists(CONFIG_PATH):
        save_runninghub_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        # 检查是否包含历史明文 api_key，自动无感迁移并加密
        needs_re_save = False
        if "api_key" in cfg and cfg["api_key"]:
            raw_k = str(cfg["api_key"]).strip()
            if not raw_k.startswith("gAAAAA"):
                cfg["api_key_encrypted"] = encrypt_str(raw_k)
                cfg.pop("api_key", None)
                needs_re_save = True

        # 补齐默认顶级字段
        for k, v in DEFAULT_CONFIG.items():
            if k not in cfg:
                cfg[k] = v

        if needs_re_save:
            save_runninghub_config(cfg)

        # 内存中解密 api_key 供后端接口使用
        raw_token = cfg.get("api_key_encrypted", "")
        cfg["api_key"] = decrypt_str(raw_token)
        cfg["key_name"] = cfg.get("key_name", "默认主账号")

        # 补齐 breeze_settings 与角色设定
        breeze_cfg = cfg.setdefault("breeze_settings", {})
        if "active_speaker" not in breeze_cfg:
            breeze_cfg["active_speaker"] = "Alice"
        if "high_precision" not in breeze_cfg:
            breeze_cfg["high_precision"] = False
        spk_cfg = breeze_cfg.setdefault("speakers", {})
        default_spks = build_default_speakers_config()
        for spk_id, def_val in default_spks.items():
            if spk_id not in spk_cfg:
                spk_cfg[spk_id] = def_val
            else:
                for subk, subv in def_val.items():
                    if subk not in spk_cfg[spk_id]:
                        spk_cfg[spk_id][subk] = subv
        return cfg
    except Exception as e:
        print(f"[RunningHub] 读取配置文件失败，重置为默认: {e}")
        return DEFAULT_CONFIG


def save_runninghub_config(cfg: Dict[str, Any]) -> bool:
    """安全保存配置文件，严禁明文落地 API Key！"""
    try:
        to_save = dict(cfg)
        # 如果传入了明文 api_key，加密后落地
        if "api_key" in to_save and to_save["api_key"]:
            plain = str(to_save["api_key"]).strip()
            # 过滤前端脱敏的星号形式
            if "****" not in plain and not plain.startswith("gAAAAA"):
                to_save["api_key_encrypted"] = encrypt_str(plain)
        to_save.pop("api_key", None)  # 彻底剔除明文

        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(to_save, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[RunningHub] 保存配置文件异常: {e}")
        return False


class RunningHubEngine:
    def __init__(self):
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        os.makedirs(CUSTOMS_DIR, exist_ok=True)
        # 实事求是真实进度监控对象
        self.current_progress = {
            "active": False,
            "task_id": None,
            "percent": 0,
            "stage": "等待开始",
            "step_name": "就绪",
            "node_id": None,
            "elapsed": 0.0,
            "updated_at": time.time()
        }

    def update_progress(self, active: bool = True, task_id: Optional[str] = None, percent: int = 0, stage: str = "处理中...", step_name: str = "运行中", node_id: Optional[str] = None):
        """更新实事求是真实阶段进度"""
        self.current_progress["active"] = active
        if task_id:
            self.current_progress["task_id"] = task_id
        self.current_progress["percent"] = max(0, min(100, int(percent)))
        self.current_progress["stage"] = stage
        self.current_progress["step_name"] = step_name
        self.current_progress["node_id"] = str(node_id) if node_id else None
        self.current_progress["updated_at"] = time.time()

    def get_progress(self) -> Dict[str, Any]:
        """获取真实进度字典"""
        return dict(self.current_progress)

    def test_connection(self, api_key: Optional[str] = None) -> Dict[str, Any]:
        """真实测试 RunningHub 云端通信与 API Key 有效性"""
        cfg = load_runninghub_config()
        key_to_test = (api_key or cfg.get("api_key", "")).strip()
        if "****" in key_to_test or not key_to_test:
            key_to_test = cfg.get("api_key", "").strip()

        if not key_to_test:
            return {"success": False, "message": "API Key 不能为空，请先填写！"}

        try:
            # 请求 RunningHub 工作流格式验证接口（轻量级无副作用通信校验）
            res = requests.post(
                f"{RUNNINGHUB_BASE_URL}/api/openapi/getJsonApiFormat",
                json={"apiKey": key_to_test, "workflowId": "2113847965285941250"},
                timeout=12
            ).json()

            code = res.get("code")
            msg = res.get("msg", "")
            if code == 0:
                return {
                    "success": True,
                    "message": "✅ 连通性测试成功！RunningHub 云端连接畅通，API Key 授权有效。"
                }
            elif code in (401, 801, 802):
                return {
                    "success": False,
                    "message": f"❌ API Key 校验未通过: {msg or '授权失败或密钥错误'}"
                }
            else:
                return {
                    "success": False,
                    "message": f"云端返回错误 (Code {code}): {msg}"
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"连通性网络异常: {str(e)}"
            }

    def get_config(self) -> Dict[str, Any]:
        cfg = load_runninghub_config()
        res = dict(cfg)
        # 前端脱敏展示 API Key，严防明文外泄
        raw_key = cfg.get("api_key", "")
        res["api_key_masked"] = mask_api_key(raw_key)
        res["key_name"] = cfg.get("key_name", "默认主账号")
        res["has_key"] = bool(raw_key)
        res.pop("api_key", None)
        res.pop("api_key_encrypted", None)

        # 将静态的 BREEZE_SPEAKER_SPECS 规格与动态配置合并供前端直观渲染
        breeze_speakers_display = []
        spk_settings = cfg.get("breeze_settings", {}).get("speakers", {})
        for spec in BREEZE_SPEAKER_SPECS:
            sid = spec["id"]
            user_setting = spk_settings.get(sid, {})
            item = dict(spec)
            item["current_name"] = user_setting.get("name", spec["default_name"])
            item["current_clone_mode"] = user_setting.get("clone_mode", spec["default_clone_mode"])
            item["current_instruction"] = user_setting.get("instruction", spec["default_instruction"])
            item["current_audio"] = user_setting.get("audio_file", spec["default_audio"])
            item["current_audio_label"] = user_setting.get("audio_label", spec["default_audio_label"])
            item["preview_url"] = user_setting.get("preview_url", "")
            breeze_speakers_display.append(item)
        res["breeze_speakers"] = breeze_speakers_display
        return res

    def update_config(self, new_cfg: Dict[str, Any]) -> Dict[str, Any]:
        curr = load_runninghub_config()
        # 处理别名与 API Key
        if "key_name" in new_cfg and new_cfg["key_name"]:
            curr["key_name"] = str(new_cfg["key_name"]).strip()

        if "api_key" in new_cfg:
            new_key = str(new_cfg["api_key"]).strip()
            # 只有当用户输入了非掩码内容时才真正更新
            if new_key and "****" not in new_key:
                curr["api_key"] = new_key
                curr["api_key_encrypted"] = encrypt_str(new_key)

        for k in ["enabled", "active_workflow"]:
            if k in new_cfg:
                curr[k] = new_cfg[k]

        if "breeze_settings" in new_cfg:
            curr.setdefault("breeze_settings", {}).update(new_cfg["breeze_settings"])
        if "indextts2_settings" in new_cfg:
            curr.setdefault("indextts2_settings", {}).update(new_cfg["indextts2_settings"])

        save_runninghub_config(curr)
        return self.get_config()
        if "api_key" in new_cfg and new_cfg["api_key"].strip():
            curr["api_key"] = new_cfg["api_key"].strip()
        if "active_workflow" in new_cfg and new_cfg["active_workflow"]:
            curr["active_workflow"] = str(new_cfg["active_workflow"]).strip()
        if "enabled" in new_cfg:
            curr["enabled"] = bool(new_cfg["enabled"])
        if "breeze_settings" in new_cfg and isinstance(new_cfg["breeze_settings"], dict):
            bs = new_cfg["breeze_settings"]
            if "active_speaker" in bs:
                curr["breeze_settings"]["active_speaker"] = bs["active_speaker"]
            if "high_precision" in bs:
                curr["breeze_settings"]["high_precision"] = bool(bs["high_precision"])
            if "speakers" in bs and isinstance(bs["speakers"], dict):
                curr["breeze_settings"]["speakers"].update(bs["speakers"])
        if "indextts2_settings" in new_cfg and isinstance(new_cfg["indextts2_settings"], dict):
            curr["indextts2_settings"].update(new_cfg["indextts2_settings"])
        save_runninghub_config(curr)
        return self.get_config()

    def upload_media_to_runninghub(self, file_bytes: bytes, filename: str, content_type: str = "audio/wav") -> Dict[str, Any]:
        """
        上传音频素材至 RunningHub 云端媒体库供 LoadAudio 节点直接加载
        """
        cfg = load_runninghub_config()
        api_key = cfg.get("api_key", "").strip()
        if not api_key:
            raise ValueError("RunningHub API Key 未配置，无法上传素材！")

        upload_url = f"{RUNNINGHUB_AI_URL}/openapi/v2/media/upload/binary"
        headers = {"Authorization": f"Bearer {api_key}"}
        files = {"file": (filename, file_bytes, content_type)}

        print(f"[RunningHub] 正在上传音频素材至云端: {filename} ({len(file_bytes)} bytes)...")
        res = requests.post(upload_url, headers=headers, files=files, timeout=60).json()
        if res.get("code") == 0 and res.get("data"):
            data = res["data"]
            runninghub_filename = data.get("fileName")
            download_url = data.get("download_url")
            print(f"[RunningHub] [+] 音频上传成功！云端文件名: {runninghub_filename}")
            return {
                "fileName": runninghub_filename,
                "download_url": download_url,
                "type": data.get("type", "audio")
            }
        else:
            err_msg = res.get("msg") or str(res)
            raise RuntimeError(f"上传至 RunningHub 失败: {err_msg}")

    async def _ws_capture_audio(self, net_wss_url: str, task_id: str, captured_list: list, stop_event: asyncio.Event):
        """
        后台实时接入 RunningHub WebSocket 管道进行音频截流捕获：
        无论工作流后续节点是否报错中断，只要前面的音频生成节点（SaveAudio 等）执行输出，
        立刻在数据流中捕获其 COS 直链并准备下载！
        """
        if not net_wss_url:
            return

        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(net_wss_url, timeout=None, ssl=False, heartbeat=20.0) as ws:
                    print(f"  [WebSocket 截流管道就绪] 已连入任务 {task_id} 实时数据流，全速监听输出...")
                    async for msg in ws:
                        if stop_event.is_set():
                            await ws.close()
                            break

                        if msg.type == aiohttp.WSMsgType.TEXT:
                            try:
                                payload = json.loads(msg.data)
                                mtype = payload.get("type")
                                mdata = payload.get("data", {})

                                if mtype == "executing":
                                    curr_node = str(mdata.get("node") or "")
                                    if curr_node:
                                        print(f"  [~] 云端节点正在执行: #{curr_node}")
                                        # 实事求是阶段映射，拒绝虚假进度
                                        if curr_node in ("147", "95", "14"):
                                            self.update_progress(True, task_id, 15, f"正在清洗剧本格式并打包提交文本 (节点 #{curr_node})...", "剧本清洗")
                                        elif curr_node in ("4", "5", "15", "16", "26", "27"):
                                            self.update_progress(True, task_id, 25, f"正在装载参考音频切片并校准声学参数 (节点 #{curr_node})...", "音频预处理")
                                        elif curr_node in ("10", "21", "32"):
                                            self.update_progress(True, task_id, 35, f"正在运行 Whisper 提取人声声学特征 (节点 #{curr_node})...", "声学转写")
                                        elif curr_node in ("8", "11", "101", "102", "103"):
                                            self.update_progress(True, task_id, 45, f"正在绑定角色配置与声音风格路由 (节点 #{curr_node})...", "音色路由")
                                        elif curr_node in ("12", "23", "34", "45", "56", "67", "78", "89"):
                                            self.update_progress(True, task_id, 55, f"正在装配多角色人设声学槽位 (节点 #{curr_node})...", "角色人设")
                                        elif curr_node in ("119",):
                                            self.update_progress(True, task_id, 60, f"正在加载 BreezeTTS2 神经网络模型权重 (节点 #{curr_node})...", "模型装载")
                                        elif curr_node in ("92",):
                                            self.update_progress(True, task_id, 75, "多角色大模型自回归声学推理中 (云端 GPU 正在深度计算，此过程耗时最长)...", "大模型推理")
                                        elif curr_node in ("94", "93", "155"):
                                            self.update_progress(True, task_id, 88, f"云端音频已产出，正在拦截捕获音频流 (节点 #{curr_node})...", "音频截流")

                                elif mtype == "executed":
                                    node_id = str(mdata.get("node"))
                                    output = mdata.get("output", {})
                                    if isinstance(output, dict):
                                        for out_key, out_val in output.items():
                                            if isinstance(out_val, list):
                                                for item in out_val:
                                                    if not isinstance(item, dict):
                                                        continue
                                                    fname = str(item.get("filename", "")).lower()
                                                    cos_url = item.get("cos_url") or item.get("url") or item.get("fileUrl")
                                                    # 严格匹配音频扩展名或 audio 键
                                                    is_audio = any(fname.endswith(ext) for ext in (".flac", ".mp3", ".wav", ".ogg", ".m4a")) or (cos_url and any(ext in cos_url.lower() for ext in (".flac", ".mp3", ".wav", ".ogg", ".m4a"))) or out_key == "audio"
                                                    if cos_url and is_audio:
                                                        ext = "flac"
                                                        for e in ["flac", "mp3", "wav", "ogg", "m4a"]:
                                                            if f".{e}" in cos_url.lower():
                                                                ext = e
                                                                break
                                                        captured_entry = {
                                                            "url": cos_url,
                                                            "node_id": node_id,
                                                            "filename": item.get("filename", f"{task_id}_{node_id}.{ext}"),
                                                            "ext": ext
                                                        }
                                                        captured_list.append(captured_entry)
                                                        print(f"  [+] 成功截流音频输出 节点 #{node_id} -> {cos_url}")

                                elif mtype == "execution_error":
                                    err_msg = mdata.get("exception_message") or str(mdata)
                                    print(f"  [!] 工作流后续末端中断 (截获机制不受影响): {err_msg[:120]}")
                                    break

                            except Exception:
                                pass

                        elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                            break
        except Exception as e:
            print(f"  [WebSocket 管道提示] 连接关闭: {e}")

    async def synthesize(
        self,
        text: str,
        workflow_id: Optional[str] = None,
        speaker: Optional[str] = None,
        emotion_prompt: Optional[str] = None,
        emo_vector: Optional[List[float]] = None,
        emo_intensity: float = 1.0,
        high_precision: Optional[bool] = None,
        breeze_speakers_override: Optional[Dict[str, Any]] = None,
        timeout_seconds: int = 400
    ) -> Dict[str, Any]:
        """
        调用 RunningHub 云端工作流合成语音：
        - 完整支持 BreezeTTS2 8位人设角色的角色名设定、特点描述、克隆模式切换与音频绑定！
        - 全程采用实时 WebSocket 截流捕获技术，在节点产出瞬间捕获音频直链！
        - 即使工作流末端报错崩溃，前置已产出的音频文件依然被完整截取并转码交付！
        """
        cfg = load_runninghub_config()
        api_key = cfg.get("api_key", "").strip()
        if not api_key:
            raise ValueError("RunningHub API Key 未配置，请先在设置中填写！")

        # 针对多角色长剧本动态调整超时上限，8 人对白推理预计耗时较长，预留充裕时间
        num_turns = len([l for l in text.splitlines() if l.strip()])
        effective_timeout = max(timeout_seconds, num_turns * 55 + 180)

        target_wfid = str(workflow_id or cfg.get("active_workflow") or "2113847965285941250").strip()
        audio_id = f"rh_{uuid.uuid4().hex[:10]}"
        print(f"\n[RunningHub] 收到云端语音合成请求 -> 工作流: {target_wfid}, 行数: {num_turns}, 文本: {text[:30]}... (超时上限: {effective_timeout}s)")

        node_info_list = []

        # ---------------- 工作流 1: 2113835289022435330 (IndexTTS2 旗舰情感克隆) ----------------
        if target_wfid == "2113835289022435330":
            node_info_list.append({
                "nodeId": "14",
                "fieldName": "value",
                "fieldValue": text
            })
            if emotion_prompt and emotion_prompt.strip():
                node_info_list.append({"nodeId": "12", "fieldName": "use_emo_text", "fieldValue": True})
                node_info_list.append({"nodeId": "12", "fieldName": "emo_text", "fieldValue": emotion_prompt.strip()})
            if emo_vector and len(emo_vector) > 0:
                scale = max(0.2, min(1.5, emo_intensity))
                scaled_vec = [round(v * scale, 4) for v in emo_vector]
                vec_str = ",".join(str(v) for v in scaled_vec)
                node_info_list.append({"nodeId": "12", "fieldName": "emo_vector", "fieldValue": vec_str})

        # ---------------- 工作流 2: 2113847965285941250 (BreezeTTS2 多角色AI语音) ----------------
        elif target_wfid == "2113847965285941250":
            breeze_cfg = cfg.get("breeze_settings", {})
            active_spk_key = speaker or breeze_cfg.get("active_speaker", "Alice")
            user_spks = breeze_cfg.get("speakers", {})
            if breeze_speakers_override:
                user_spks.update(breeze_speakers_override)

            # 1. 遍历并配置 8 位角色的名字、克隆模式、描述或音频
            active_name = active_spk_key
            for spec in BREEZE_SPEAKER_SPECS:
                sid = spec["id"]
                spk_data = user_spks.get(sid, {})
                spk_name = spk_data.get("name", spec["default_name"]).strip()
                if sid == active_spk_key:
                    active_name = spk_name

                # 角色名 Node
                node_info_list.append({
                    "nodeId": spec["name_node"],
                    "fieldName": "value",
                    "fieldValue": spk_name
                })

                # 克隆模式开关 Node (True: 克隆模式使用参考音频, False: 描述模式使用 instruction)
                is_clone = bool(spk_data.get("clone_mode", spec["default_clone_mode"]))
                node_info_list.append({
                    "nodeId": spec["clone_mode_node"],
                    "fieldName": "value",
                    "fieldValue": is_clone
                })

                # 声音特点描述 Node
                inst_text = spk_data.get("instruction", spec["default_instruction"]).strip()
                node_info_list.append({
                    "nodeId": spec["instruction_node"],
                    "fieldName": "value",
                    "fieldValue": inst_text
                })

                # 参考音频 Node (若为克隆模式且指定了音频文件)
                audio_file = spk_data.get("audio_file", spec["default_audio"]).strip()
                if audio_file:
                    node_info_list.append({
                        "nodeId": spec["audio_node"],
                        "fieldName": "audio",
                        "fieldValue": audio_file
                    })

            # 2. 规范合成文本：如果文本未包含任何角色前缀（如 "Alice:" 或 "少女:"），自动加上激活角色的前缀
            text_to_send = text.strip()
            all_known_names = [spec["default_name"] for spec in BREEZE_SPEAKER_SPECS] + [user_spks.get(s["id"], {}).get("name", "") for s in BREEZE_SPEAKER_SPECS]
            all_known_names = [n for n in all_known_names if n]
            has_role_prefix = any(text_to_send.startswith(f"{n}:") or text_to_send.startswith(f"{n}：") or f"\n{n}:" in text_to_send or f"\n{n}：" in text_to_send for n in all_known_names)
            if not has_role_prefix:
                text_to_send = f"{active_name}: {text_to_send}"

            # 3. 传入文本节点 (Node 95)
            node_info_list.append({
                "nodeId": "95",
                "fieldName": "value",
                "fieldValue": text_to_send
            })

            # 4. 高精度模式 (Node 118)
            is_hp = high_precision if high_precision is not None else breeze_cfg.get("high_precision", False)
            node_info_list.append({
                "nodeId": "118",
                "fieldName": "value",
                "fieldValue": bool(is_hp)
            })
        else:
            node_info_list.append({"nodeId": "text", "fieldName": "value", "fieldValue": text})

        headers = {
            "Host": "www.runninghub.cn",
            "Content-Type": "application/json"
        }
        create_payload = {
            "apiKey": api_key,
            "workflowId": target_wfid,
            "nodeInfoList": node_info_list
        }

        self.update_progress(True, None, 5, "正在清洗文本并打包参数提交至 RunningHub 云端...", "任务提交")

        # 1. 创建任务
        def _create_task():
            return requests.post(f"{RUNNINGHUB_BASE_URL}/task/openapi/create", json=create_payload, headers=headers, timeout=25).json()

        loop = asyncio.get_running_loop()
        create_res = await loop.run_in_executor(None, _create_task)
        if create_res.get("code") != 0:
            err_msg = create_res.get("msg") or str(create_res)
            print(f"[RunningHub 提交错误] {create_res}")
            self.update_progress(False, None, 0, f"云端提交失败: {err_msg}", "提交失败")
            raise RuntimeError(f"RunningHub 任务提交失败: {err_msg}")

        task_data = create_res.get("data", {})
        task_id = str(task_data.get("taskId"))
        net_wss_url = task_data.get("netWssUrl")
        print(f"[RunningHub] 任务创建成功！TaskId: {task_id}")
        self.update_progress(True, task_id, 10, f"云端任务已就绪 (TaskId: {task_id[:10]}...)，等待 GPU 算力分配...", "云端排队")

        # 2. 建立 WebSocket 实时截流捕获
        captured_audios = []
        stop_ws_event = asyncio.Event()
        ws_task = None
        if net_wss_url:
            ws_task = asyncio.create_task(
                self._ws_capture_audio(net_wss_url, task_id, captured_audios, stop_ws_event)
            )

        # 3. 轮询并监听音频捕获
        start_time = time.time()
        outputs_url = f"{RUNNINGHUB_BASE_URL}/task/openapi/outputs"
        poll_payload = {"apiKey": api_key, "taskId": task_id}

        def _poll_outputs():
            return requests.post(outputs_url, json=poll_payload, headers=headers, timeout=20).json()

        target_file_url = None
        target_ext = "flac"
        consume_coins = "0"

        while time.time() - start_time < effective_timeout:
            await asyncio.sleep(1.5)

            # 只要 WebSocket 截获到音频，稍等 1 秒让高品质 flac 稳定到达后直接采纳
            if captured_audios:
                await asyncio.sleep(1.0)
                flac_items = [x for x in captured_audios if x["ext"] == "flac"]
                best = flac_items[-1] if flac_items else captured_audios[-1]
                target_file_url = best["url"]
                target_ext = best["ext"]
                elapsed = int(time.time() - start_time)
                print(f"[RunningHub 截流成功] 在第 {elapsed}s 捕获到音频文件: {target_file_url}")
                break

            # 若 WebSocket 管道已关闭或结束
            if ws_task and ws_task.done():
                if captured_audios:
                    flac_items = [x for x in captured_audios if x["ext"] == "flac"]
                    best = flac_items[-1] if flac_items else captured_audios[-1]
                    target_file_url = best["url"]
                    target_ext = best["ext"]
                    print(f"[RunningHub 截流成功] 音频已被完整捕获: {target_file_url}")
                    break
                else:
                    out_res = await loop.run_in_executor(None, _poll_outputs)
                    if out_res.get("code") == 0 and out_res.get("data"):
                        items = out_res["data"]
                        audio_items = [it for it in items if str(it.get("fileType", "")).lower() in ("flac", "wav", "mp3", "m4a", "ogg")]
                        chosen = audio_items[0] if audio_items else items[0]
                        target_file_url = chosen.get("fileUrl")
                        target_ext = chosen.get("fileType", "flac")
                        consume_coins = str(chosen.get("consumeCoins", "0"))
                        break
                    else:
                        raise RuntimeError(f"RunningHub 云端未捕获到音频文件: {out_res}")

        # 停止 WebSocket 监听
        stop_ws_event.set()
        if ws_task and not ws_task.done():
            ws_task.cancel()

        if not target_file_url:
            raise TimeoutError(f"RunningHub 语音合成超时（已等待 {int(time.time() - start_time)} 秒 / 动态上限 {effective_timeout} 秒）")

        # 4. 下载截获的音频
        def _download_file(url: str, save_path: str):
            r = requests.get(url, timeout=30)
            if r.status_code == 200:
                with open(save_path, "wb") as f:
                    f.write(r.content)
            else:
                raise RuntimeError(f"下载云端音频失败，状态码: {r.status_code}")

        raw_audio_path = os.path.join(OUTPUT_DIR, f"{audio_id}_raw.{target_ext}")
        output_wav = os.path.join(OUTPUT_DIR, f"{audio_id}.wav")
        output_silk = os.path.join(OUTPUT_DIR, f"{audio_id}.silk")

        print(f"[RunningHub] 开始下载截获音频: {target_file_url}")
        self.update_progress(True, task_id, 92, "云端音频已产出，正在从 CDN 下载高质量音频文件...", "音频下载")
        await loop.run_in_executor(None, _download_file, target_file_url, raw_audio_path)

        # 5. 转码为标准 24kHz 单声道 WAV 供网页端播放
        def _convert_to_wav(in_p: str, out_p: str):
            cmd = [FFMPEG_BIN, "-y", "-i", in_p, "-ar", "24000", "-ac", "1", out_p]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        try:
            await loop.run_in_executor(None, _convert_to_wav, raw_audio_path, output_wav)
        except Exception as e:
            print(f"[RunningHub] 转码 WAV 提示: {e}，使用文件复制兜底")
            if os.path.exists(raw_audio_path):
                import shutil
                shutil.copyfile(raw_audio_path, output_wav)

        # 6. 转码为 QQ 原生 Silk 格式供 NapCat 机器人发送
        print(f"[RunningHub] 正在生成 QQ 原生 Silk 语音文件...")
        self.update_progress(True, task_id, 96, "音频下载完成，正在转码为 QQ 原生 Silk 格式...", "Silk转码")
        convert_to_silk(output_wav, output_silk, sample_rate=24000)

        # 清理临时文件
        if os.path.exists(raw_audio_path) and raw_audio_path != output_wav:
            try:
                os.remove(raw_audio_path)
            except Exception:
                pass

        self.update_progress(False, task_id, 100, "语音合成与转码完成！随时可试听或发送。", "完成")
        print(f"[RunningHub] [+] 截获与转码全流程圆满完成！输出文件: {audio_id}.silk / {audio_id}.wav")

        chosen_voice_label = "IndexTTS2 旗舰情感"
        if target_wfid == "2113847965285941250":
            chosen_voice_label = f"Breeze - {active_name}"

        return {
            "audio_id": audio_id,
            "text": text,
            "voice_name": chosen_voice_label,
            "wav_path": output_wav,
            "silk_path": output_silk,
            "wav_url": f"/audio/{audio_id}.wav",
            "silk_url": f"/audio/{audio_id}.silk",
            "workflow_id": target_wfid,
            "consume_coins": consume_coins
        }


# 全局单例
runninghub_engine = RunningHubEngine()
