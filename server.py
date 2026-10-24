import os
import sys
import time
import subprocess

# 智能环境自动桥接：若非 AI 专属 Python 环境启动，在导入前自动切换至具备 CUDA / IndexTTS2 / CosyVoice 的专属环境
AI_PYTHON = os.environ.get("AI_PYTHON", r"D:\AI\ComfyUI-aki-v3\python\python.exe")
if __name__ == "__main__" and os.path.exists(AI_PYTHON) and os.path.abspath(sys.executable).lower() != os.path.abspath(AI_PYTHON).lower():
    print(f"[环境自检] 检测到当前 Python 并非 AI 专属环境 ({sys.executable})，正在自动无缝切换至: {AI_PYTHON}...")
    res = subprocess.run([AI_PYTHON, os.path.abspath(__file__)] + sys.argv[1:])
    sys.exit(res.returncode)

import re

if os.path.isdir(r"D:\MediaToolkit") and r"D:\MediaToolkit" not in os.environ.get("PATH", ""):
    os.environ["PATH"] = r"D:\MediaToolkit;" + os.environ.get("PATH", "")

import uvicorn
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List

from tts_engine import tts_engine, OUTPUT_DIR, CUSTOMS_DIR, EMOTIONS_DIR
from runninghub_engine import runninghub_engine
from qq_bot import QQBotClient, DEFAULT_ONEBOT_URL
import asr_engine
from napcat_manager import napcat_manager

app = FastAPI(title="TalkToYou - AI语音第二人代发系统")

# 允许跨域（方便反向代理与容器互联）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 挂载静态资源
STATIC_DIR = os.path.join(BASE_DIR, "static")
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(CUSTOMS_DIR, exist_ok=True)
os.makedirs(EMOTIONS_DIR, exist_ok=True)
PRESETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voices", "presets")
os.makedirs(PRESETS_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/audio", StaticFiles(directory=OUTPUT_DIR), name="audio")
app.mount("/voices/customs", StaticFiles(directory=CUSTOMS_DIR), name="custom_voices")
app.mount("/voices/emotions", StaticFiles(directory=EMOTIONS_DIR), name="emotion_voices")
app.mount("/voices/presets", StaticFiles(directory=PRESETS_DIR), name="preset_voices")



# 机器人实例
bot_client = QQBotClient()

class BotConfigReq(BaseModel):
    onebot_url: str
    access_token: Optional[str] = None

class TTSPreviewReq(BaseModel):
    text: str
    voice_id: str
    engine: Optional[str] = "cosyvoice"
    speed: Optional[int] = 0
    mood: Optional[str] = "auto"
    pitch: Optional[int] = 0
    emotion_mode: Optional[str] = "none"
    emotion_prompt: Optional[str] = None
    emotion_audio_id: Optional[str] = None
    emo_vector: Optional[List[float]] = None
    emo_intensity: Optional[float] = 1.0

class TTSSendReq(BaseModel):
    text: str
    voice_id: str
    target_qq: int
    message_type: Optional[str] = "private"  # 'private' (私聊) 或 'group' (群聊)
    engine: Optional[str] = "cosyvoice"
    speed: Optional[int] = 0
    mood: Optional[str] = "auto"
    pitch: Optional[int] = 0
    emotion_mode: Optional[str] = "none"
    emotion_prompt: Optional[str] = None
    emotion_audio_id: Optional[str] = None
    emo_vector: Optional[List[float]] = None
    emo_intensity: Optional[float] = 1.0

class SendExistingReq(BaseModel):
    audio_id: str
    target_id: int
    message_type: Optional[str] = "private"  # 'private' (私聊) 或 'group' (群聊)

@app.get("/")
async def index():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "TalkToYou 后端已启动，前端界面加载中..."}

@app.get("/api/status")
async def get_bot_status():
    """检测 QQ 机器人 NapCatQQ 在线状态"""
    status = bot_client.check_connection()
    return status

@app.post("/api/config/bot")
async def update_bot_config(req: BotConfigReq):
    """更新 NapCatQQ 的地址或 Token"""
    global bot_client
    bot_client = QQBotClient(base_url=req.onebot_url, access_token=req.access_token)
    return bot_client.check_connection()

@app.get("/api/bot/groups")
async def get_bot_groups():
    """获取当前登录 QQ 小号已加入的群聊列表，用于前端快捷选择"""
    return bot_client.get_groups()

# ==================== NapCat 深度接入 & 扫码登录托管 API ====================

class QuickLoginReq(BaseModel):
    uin: str

@app.get("/api/napcat/status")
async def get_napcat_status():
    """获取 NapCat 进程状态及 QQ 登录状态 (带 Base64 二维码)"""
    return napcat_manager.get_login_status()

@app.post("/api/napcat/start")
async def start_napcat_daemon():
    """后台一键拉起 NapCat 守护进程"""
    return napcat_manager.start_process()

@app.post("/api/napcat/stop")
async def stop_napcat_daemon():
    """停止 NapCat 守护进程"""
    return napcat_manager.stop_process()

@app.post("/api/napcat/restart")
async def restart_napcat_daemon():
    """重启 NapCat 守护进程"""
    return napcat_manager.restart_process()

@app.post("/api/napcat/refresh_qr")
async def refresh_napcat_qr():
    """刷新 QQ 登录二维码"""
    return napcat_manager.refresh_qrcode()

@app.get("/api/napcat/quick_logins")
async def get_napcat_quick_logins():
    """获取本机已缓存的快捷登录账号"""
    return {"logins": napcat_manager.get_quick_login_list()}

@app.post("/api/napcat/quick_login")
async def do_napcat_quick_login(req: QuickLoginReq):
    """一键免扫码快捷登录"""
    return napcat_manager.quick_login(req.uin)

@app.get("/api/voices")
async def list_voices():
    """获取所有音色列表（包含预设音色和自定义音色）"""
    return tts_engine.get_all_voices()

@app.post("/api/voices/custom")
async def create_custom_voice(
    name: str = Form(...),
    description: str = Form(""),
    prompt_text: str = Form(""),
    audio_file: UploadFile = File(...),
    emotion_audio_file: Optional[UploadFile] = File(None),
    emotion_name: Optional[str] = Form(None)
):
    """
    上传音频以添加新的自定义预设音色，支持可选绑定专属情感音频
    """
    if not name.strip():
        raise HTTPException(status_code=400, detail="音色名称不能为空")

    audio_bytes = await audio_file.read()
    if len(audio_bytes) < 1000:
        raise HTTPException(status_code=400, detail="上传的音频文件过小或无效")

    emotion_bytes = None
    emotion_filename = None
    if emotion_audio_file and emotion_audio_file.filename:
        raw_e = await emotion_audio_file.read()
        if len(raw_e) >= 1000:
            emotion_bytes = raw_e
            emotion_filename = emotion_audio_file.filename

    new_voice = tts_engine.add_custom_voice(
        name=name.strip(),
        description=description.strip(),
        audio_bytes=audio_bytes,
        filename=audio_file.filename,
        prompt_text=prompt_text.strip(),
        emotion_audio_bytes=emotion_bytes,
        emotion_filename=emotion_filename,
        emotion_name=emotion_name.strip() if emotion_name else None
    )
    return {"success": True, "voice": new_voice}

@app.delete("/api/voices/custom/{voice_id}")
async def remove_custom_voice(voice_id: str):
    """删除指定的自定义音色"""
    try:
        ok = tts_engine.delete_custom_voice(voice_id)
        if not ok:
            raise HTTPException(status_code=404, detail="未找到该自定义音色")
        return {"success": True, "message": "音色已删除"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/emotions")
async def list_emotions():
    """获取所有独立情感参考预设列表"""
    return tts_engine.get_all_emotions()

@app.post("/api/emotions")
async def create_emotion_preset(
    name: str = Form(...),
    audio_file: UploadFile = File(...)
):
    """保存一个新的独立情感参考预设"""
    if not name.strip():
        raise HTTPException(status_code=400, detail="情感预设名称不能为空")
    audio_bytes = await audio_file.read()
    if len(audio_bytes) < 1000:
        raise HTTPException(status_code=400, detail="上传的情感音频过小或无效")
    new_emo = tts_engine.add_emotion_preset(
        name=name.strip(),
        audio_bytes=audio_bytes,
        filename=audio_file.filename
    )
    return {"success": True, "emotion": new_emo}

@app.delete("/api/emotions/{emotion_id}")
async def remove_emotion_preset(emotion_id: str):
    """删除指定的情感参考预设"""
    ok = tts_engine.delete_emotion_preset(emotion_id)
    if not ok:
        raise HTTPException(status_code=404, detail="未找到该情感预设")
    return {"success": True, "message": "情感预设已删除"}

@app.get("/api/runninghub/config")
async def get_runninghub_config():
    """获取 RunningHub 云端算力配置及支持的工作流与角色 (API Key 已脱敏防泄露)"""
    return runninghub_engine.get_config()

@app.post("/api/runninghub/config")
async def update_runninghub_config(req: dict):
    """更新 RunningHub API Key、当前激活的工作流或角色设定 (自动加密落地存储)"""
    return runninghub_engine.update_config(req)

@app.post("/api/runninghub/test_connection")
async def test_runninghub_connection(req: dict = {}):
    """真实测试 RunningHub API Key 连通性与云端通信状态"""
    api_key = req.get("api_key")
    return runninghub_engine.test_connection(api_key)

@app.get("/api/tts/progress")
async def get_tts_progress():
    """获取当前实事求是的真实生成阶段与进度"""
    return runninghub_engine.get_progress()

@app.post("/api/runninghub/upload_audio")
async def upload_runninghub_audio(file: UploadFile = File(...)):
    """上传本地自定义音频至 RunningHub 云端，供 BreezeTTS2 角色克隆模式绑定"""
    try:
        import uuid
        ext = os.path.splitext(file.filename)[1] or ".wav"
        file_bytes = await file.read()
        if len(file_bytes) < 500:
            raise HTTPException(status_code=400, detail="音频文件过小或无效")

        local_id = uuid.uuid4().hex[:10]
        local_filename = f"rh_upload_{local_id}{ext}"
        local_path = os.path.join(OUTPUT_DIR, local_filename)
        with open(local_path, "wb") as f:
            f.write(file_bytes)

        rh_res = runninghub_engine.upload_media_to_runninghub(
            file_bytes=file_bytes,
            filename=file.filename or f"clone_{local_id}{ext}",
            content_type=file.content_type or "audio/wav"
        )
        return {
            "success": True,
            "runninghub_file": rh_res["fileName"],
            "download_url": rh_res.get("download_url"),
            "preview_url": f"/audio/{local_filename}",
            "filename": file.filename
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "message": f"上传失败: {str(e)}"})

@app.post("/api/runninghub/upload_preset")
async def upload_runninghub_preset(req: dict):
    """将系统内置音色预设（如晓晓、云健等）上传到 RunningHub 云端用于克隆"""
    try:
        voice_id = req.get("voice_id")
        if not voice_id:
            raise HTTPException(status_code=400, detail="未指定音色ID")

        voices = tts_engine.get_all_voices()
        target_v = None
        for v in voices:
            if v.get("id") == voice_id:
                target_v = v
                break

        if not target_v:
            raise HTTPException(status_code=404, detail="未找到该预设音色")

        p_audio = target_v.get("prompt_audio")
        if p_audio and not os.path.isabs(p_audio):
            p_audio = os.path.join(BASE_DIR, p_audio)

        if not p_audio or not os.path.exists(p_audio):
            raise HTTPException(status_code=404, detail="该预设的音频文件不存在")

        with open(p_audio, "rb") as f:
            file_bytes = f.read()

        fname = os.path.basename(p_audio)
        rh_res = runninghub_engine.upload_media_to_runninghub(
            file_bytes=file_bytes,
            filename=fname,
            content_type="audio/wav"
        )

        return {
            "success": True,
            "runninghub_file": rh_res["fileName"],
            "download_url": rh_res.get("download_url"),
            "preview_url": target_v.get("prompt_audio_url") or f"/audio/{fname}",
            "name": target_v.get("name")
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "message": f"预设上传失败: {str(e)}"})

def find_emotion_audio_path(audio_id: Optional[str]) -> Optional[str]:
    """多目录寻址情感参考音频 (支持临时上传、自定义音色绑定、情感预设库)"""
    if not audio_id:
        return None
    candidates = [
        os.path.join(OUTPUT_DIR, audio_id),
        os.path.join(CUSTOMS_DIR, audio_id),
        os.path.join(EMOTIONS_DIR, audio_id),
        audio_id
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    import traceback
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"success": False, "message": f"服务处理失败: {str(exc)}"}
    )

@app.post("/api/tts/upload_emotion_audio")
async def upload_emotion_audio(file: UploadFile = File(...)):
    """上传用于 IndexTTS2 情感解耦克隆的情感参考音频"""
    try:
        import uuid
        ext = os.path.splitext(file.filename)[1] or ".wav"
        emotion_id = uuid.uuid4().hex
        filename = f"emotion_{emotion_id}{ext}"
        saved_path = os.path.join(OUTPUT_DIR, filename)

        contents = await file.read()
        with open(saved_path, "wb") as f:
            f.write(contents)

        return {
            "success": True,
            "emotion_audio_id": filename,
            "filename": file.filename,
            "message": "情感参考音频已上传"
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "message": f"上传失败: {str(e)}"})

@app.post("/api/asr/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """
    语音转文字 (ASR) 接口 - 基于 FunASR SenseVoiceSmall
    支持普通话、粤语、英语等高精度识别与自动标点
    """
    try:
        contents = await file.read()
        res = asr_engine.transcribe(contents)
        if res.get("success"):
            return {
                "success": True,
                "text": res.get("text", ""),
                "raw": res.get("raw", "")
            }
        else:
            return JSONResponse(status_code=500, content={"success": False, "message": "识别失败"})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"success": False, "message": f"语音识别异常: {str(e)}"})

@app.post("/api/tts/preview")
async def tts_preview(req: TTSPreviewReq):
    """
    仅合成语音并在网页提供在线试听
    """
    cleaned_text = req.text.strip()
    if not cleaned_text:
        return JSONResponse(status_code=400, content={"success": False, "message": "请输入要朗读的文本内容"})
    if not re.search(r'[\u4e00-\u9fa5a-zA-Z0-9]', cleaned_text):
        return JSONResponse(status_code=400, content={"success": False, "message": "输入内容必须包含实际的汉字、字母或数字，不能仅包含标点符号"})

    emotion_audio_path = find_emotion_audio_path(req.emotion_audio_id)

    try:
        t0 = time.time()
        res = await tts_engine.synthesize(
            text=cleaned_text,
            voice_id=req.voice_id,
            engine=req.engine or "cosyvoice",
            speed_pct=req.speed or 0,
            mood=req.mood or "auto",
            pitch_hz=req.pitch or 0,
            emotion_mode=req.emotion_mode or "none",
            emotion_prompt=req.emotion_prompt,
            emotion_audio_path=emotion_audio_path,
            emo_vector=req.emo_vector,
            emo_intensity=req.emo_intensity or 1.0
        )
        elapsed_sec = round(time.time() - t0, 1)
        return {
            "success": True,
            "audio_id": res["audio_id"],
            "voice_name": res["voice_name"],
            "wav_url": res["wav_url"],
            "silk_url": res["silk_url"],
            "text": cleaned_text,
            "engine": req.engine or "cosyvoice",
            "elapsed_time": elapsed_sec
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"合成失败: {str(e)}"}
        )

@app.post("/api/tts/send")
async def tts_and_send(req: TTSSendReq):
    """
    合成语音，并通过 QQ 机器人将原生 Silk 语音条发送给指定 QQ 好友或 QQ 群
    """
    cleaned_text = req.text.strip()
    if not cleaned_text:
        return JSONResponse(status_code=400, content={"success": False, "message": "请输入要发送的内容"})
    if not re.search(r'[\u4e00-\u9fa5a-zA-Z0-9]', cleaned_text):
        return JSONResponse(status_code=400, content={"success": False, "message": "输入内容必须包含实际的汉字、字母或数字，不能仅包含标点符号"})
    if not req.target_qq or req.target_qq <= 10000:
        return JSONResponse(status_code=400, content={"success": False, "message": "请输入合法的目标 QQ 号或群号"})

    msg_type = req.message_type or "private"
    emotion_audio_path = find_emotion_audio_path(req.emotion_audio_id)

    try:
        t0 = time.time()
        # 1. 检查 QQ 机器人是否就绪
        bot_status = bot_client.check_connection()
        if not bot_status.get("online"):
            # 生成音频后告知机器人未就绪，同时提供试听与保留
            synth_res = await tts_engine.synthesize(
                text=cleaned_text,
                voice_id=req.voice_id,
                engine=req.engine or "cosyvoice",
                speed_pct=req.speed or 0,
                mood=req.mood or "auto",
                pitch_hz=req.pitch or 0,
                emotion_mode=req.emotion_mode or "none",
                emotion_prompt=req.emotion_prompt,
                emotion_audio_path=emotion_audio_path,
                emo_vector=req.emo_vector,
                emo_intensity=req.emo_intensity or 1.0
            )
            elapsed_sec = round(time.time() - t0, 1)
            return {
                "success": False,
                "bot_offline": True,
                "message": f"QQ 机器人 NapCatQQ 尚未连接或未登录，无法自动发送。\n不过语音已生成完毕，可在下方试听并保留！",
                "audio_id": synth_res["audio_id"],
                "wav_url": synth_res["wav_url"],
                "silk_url": synth_res["silk_url"],
                "text": cleaned_text,
                "voice_name": synth_res["voice_name"],
                "engine": req.engine or "cosyvoice",
                "elapsed_time": elapsed_sec
            }

        # 2. 合成语音并转 Silk
        synth_res = await tts_engine.synthesize(
            text=cleaned_text,
            voice_id=req.voice_id,
            engine=req.engine or "cosyvoice",
            speed_pct=req.speed or 0,
            mood=req.mood or "auto",
            pitch_hz=req.pitch or 0,
            emotion_mode=req.emotion_mode or "none",
            emotion_prompt=req.emotion_prompt,
            emotion_audio_path=emotion_audio_path,
            emo_vector=req.emo_vector,
            emo_intensity=req.emo_intensity or 1.0
        )
        elapsed_sec = round(time.time() - t0, 1)

        # 3. 发送 QQ 语音条 (支持私聊好友或 QQ 群)
        send_res = bot_client.send_voice_message(
            target_id=req.target_qq,
            silk_path=synth_res["silk_path"],
            message_type=msg_type
        )

        return {
            "success": send_res.get("success", False),
            "message": send_res.get("message"),
            "audio_id": synth_res["audio_id"],
            "target_qq": req.target_qq,
            "message_type": msg_type,
            "voice_name": synth_res["voice_name"],
            "text": cleaned_text,
            "engine": req.engine or "cosyvoice",
            "wav_url": synth_res["wav_url"],
            "silk_url": synth_res["silk_url"],
            "elapsed_time": elapsed_sec
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"发送处理失败: {str(e)}"}
        )

@app.post("/api/tts/send_existing")
async def send_existing_audio(req: SendExistingReq):
    """
    将已试听/已生成的现有 Silk 语音条直接发送给好友或群聊，无需重复经过 TTS 神经渲染 (耗时 < 0.1秒)
    """
    if not req.target_id or req.target_id <= 10000:
        return JSONResponse(status_code=400, content={"success": False, "message": "请输入合法的目标 QQ 号或群号"})

    silk_path = os.path.join(OUTPUT_DIR, f"{req.audio_id}.silk")
    if not os.path.exists(silk_path):
        return JSONResponse(status_code=404, content={"success": False, "message": "未找到对应的语音文件，可能已被清理"})

    bot_status = bot_client.check_connection()
    if not bot_status.get("online"):
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": f"QQ 机器人尚未就绪: {bot_status.get('message', '未连接')}"}
        )

    send_res = bot_client.send_voice_message(
        target_id=req.target_id,
        silk_path=silk_path,
        message_type=req.message_type or "private"
    )
    return send_res

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8086"))
    print(f"[TalkToYou] Web 服务已就绪: http://{host}:{port}")
    uvicorn.run("server:app", host=host, port=port, reload=False)
