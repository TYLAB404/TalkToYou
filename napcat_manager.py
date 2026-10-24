import os
import sys
import json
import time
import io
import base64
import hashlib
import subprocess
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, List

# 预设 NapCat 目录查找路径
DEFAULT_NAPCAT_DIRS = [
    os.environ.get("NAPCAT_DIR"),
    r"C:\Users\Admin\Desktop\CodeWork\NapCat.Shell.Windows.OneKey\NapCat.52230.Shell",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "NapCat.Shell.Windows.OneKey", "NapCat.52230.Shell"),
    r"C:\NapCat.Shell.Windows.OneKey\NapCat.52230.Shell",
    "/opt/napcat",
    "/app/napcat"
]

class NapCatManager:
    def __init__(self):
        self.webui_host = os.environ.get("NAPCAT_WEBUI_HOST", "127.0.0.1")
        self.napcat_dir = self._detect_napcat_dir()
        self.webui_port = 6099
        self.webui_token = ""
        self._cached_credential = None
        self._credential_time = 0
        self._load_webui_config()

    def _detect_napcat_dir(self) -> Optional[str]:
        for d in DEFAULT_NAPCAT_DIRS:
            if d and os.path.exists(d):
                exe = os.path.join(d, "NapCatWinBootMain.exe")
                sh = os.path.join(d, "napcat.sh")
                if os.path.exists(exe) or os.path.exists(sh) or os.path.isdir(d):
                    return os.path.abspath(d)
        return None

    def _load_webui_config(self):
        """自动寻址并读取 NapCat WebUI 配置文件"""
        if not self.napcat_dir:
            return

        # 尝试查找 webui.json
        candidates = [
            os.path.join(self.napcat_dir, "versions", "9.9.33-52230", "resources", "app", "napcat", "config", "webui.json"),
            os.path.join(self.napcat_dir, "config", "webui.json"),
        ]
        
        # 递归搜索 webui.json
        if not any(os.path.exists(p) for p in candidates):
            for root, dirs, files in os.walk(self.napcat_dir):
                if "webui.json" in files:
                    candidates.append(os.path.join(root, "webui.json"))
                    break

        for path in candidates:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                        self.webui_port = cfg.get("port", 6099)
                        self.webui_token = cfg.get("token", "")
                        print(f"[NapCatManager] 成功加载 NapCat WebUI 配置: Port={self.webui_port}")
                        return
                except Exception as e:
                    print(f"[NapCatManager] 读取 webui.json 失败: {e}")

    def is_process_running(self) -> bool:
        """检查 NapCat 进程或 WebUI 服务是否正在运行"""
        try:
            # 快速端口检查
            req = urllib.request.Request(f"http://{self.webui_host}:{self.webui_port}/webui/", headers={"User-Agent": "TalkToYou"})
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass

        # 降级通过系统进程检查
        try:
            if sys.platform == "win32":
                output = subprocess.check_output('tasklist /FI "IMAGENAME eq NapCatWinBootMain.exe" /NH', shell=True).decode('gbk', errors='ignore')
                if "NapCatWinBootMain.exe" in output:
                    return True
            else:
                res = subprocess.run(["pgrep", "-f", "napcat"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if res.returncode == 0:
                    return True
        except Exception:
            pass
        return False

    def start_process(self) -> Dict[str, Any]:
        """后台静默拉起 NapCat 守护进程"""
        if self.is_process_running():
            return {"success": True, "message": "NapCatQQ 已经在运行中"}

        if not self.napcat_dir:
            self.napcat_dir = self._detect_napcat_dir()
            self._load_webui_config()

        if not self.napcat_dir:
            return {"success": False, "message": "未找到 NapCat 安装目录，请确认 NapCat 路径"}

        exe_path = os.path.join(self.napcat_dir, "NapCatWinBootMain.exe")
        if not os.path.exists(exe_path):
            return {"success": False, "message": f"未找到启动程序: {exe_path}"}

        try:
            # 纯后台静默拉起，不产生黑色 CMD 弹窗
            flags = 0
            if sys.platform == "win32":
                flags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS

            subprocess.Popen(
                [exe_path],
                cwd=self.napcat_dir,
                creationflags=flags,
                close_fds=True
            )

            # 等待 3 秒等待 WebUI 端口就绪
            for _ in range(8):
                time.sleep(1.0)
                if self.is_process_running():
                    return {"success": True, "message": "NapCatQQ 守护进程已成功在后台启动！"}

            return {"success": True, "message": "NapCat 进程已拉起，正在初始化环境..."}
        except Exception as e:
            return {"success": False, "message": f"启动 NapCat 失败: {str(e)}"}

    def stop_process(self) -> Dict[str, Any]:
        """关闭 NapCat 守护进程及专属 QQ 实例 (精确匹配路径，绝不误杀主号)"""
        try:
            if sys.platform == "win32":
                subprocess.run('taskkill /F /IM NapCatWinBootMain.exe /T', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                # 精准清理 NapCat 专属目录下的 QQ 进程
                ps_cmd = 'Get-Process -Name QQ -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "*NapCat*" } | Stop-Process -Force'
                subprocess.run(['powershell', '-Command', ps_cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            else:
                subprocess.run(["pkill", "-f", "napcat"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self._cached_credential = None
            return {"success": True, "message": "NapCatQQ 及专属子进程已安全清理停止"}
        except Exception as e:
            return {"success": False, "message": f"停止 NapCat 失败: {str(e)}"}

    def restart_process(self) -> Dict[str, Any]:
        """重启 NapCat"""
        self.stop_process()
        time.sleep(1.5)
        return self.start_process()

    def _get_credential(self) -> Optional[str]:
        """向 NapCat WebUI 申请或刷新登录 Credential"""
        now = time.time()
        if self._cached_credential and (now - self._credential_time < 3000):
            return self._cached_credential

        if not self.webui_token:
            self._load_webui_config()

        try:
            token = self.webui_token or "432f68a93910"
            h = hashlib.sha256((token + ".napcat").encode("utf-8")).hexdigest()
            req = urllib.request.Request(
                f"http://{self.webui_host}:{self.webui_port}/api/auth/login",
                data=json.dumps({"hash": h}).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("code") == 0 and data.get("data", {}).get("Credential"):
                    self._cached_credential = data["data"]["Credential"]
                    self._credential_time = now
                    return self._cached_credential
        except Exception as e:
            print(f"[NapCatManager] 获取 WebUI 凭据失败: {e}")
        return None

    def _request_api(self, path: str, body: dict = None) -> Optional[dict]:
        """调用 NapCat WebUI 内部 API"""
        cred = self._get_credential()
        if not cred:
            return None

        url = f"http://{self.webui_host}:{self.webui_port}{path}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cred}"
        }
        data = json.dumps(body or {}).encode("utf-8")
        try:
            req = urllib.request.Request(url, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as he:
            if he.code == 401:
                # 凭据失效，清空缓存重试一次
                self._cached_credential = None
                new_cred = self._get_credential()
                if new_cred:
                    headers["Authorization"] = f"Bearer {new_cred}"
                    req2 = urllib.request.Request(url, data=data, headers=headers)
                    with urllib.request.urlopen(req2, timeout=5.0) as resp2:
                        return json.loads(resp2.read().decode("utf-8"))
        except Exception as e:
            print(f"[NapCatManager] 调用接口 {path} 异常: {e}")
        return None

    @staticmethod
    def _url_to_qr_base64(url: str) -> Optional[str]:
        """将二维码网址瞬间转换为 Base64 PNG 数据"""
        if not url:
            return None
        try:
            import qrcode
            qr = qrcode.QRCode(version=1, box_size=6, border=2)
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
        except Exception as e:
            print(f"[NapCatManager] 生成二维码图像异常: {e}")
            return None

    def get_login_status(self) -> Dict[str, Any]:
        """获取综合状态（优先 OneBot 双向检验，若未在线提供扫码与错误诊断）"""
        running = self.is_process_running()
        if not running:
            return {
                "running": False,
                "is_login": False,
                "login_phase": "stopped",
                "message": "NapCatQQ 守护进程未启动，请点击【启动 NapCat】",
                "login_error": None,
                "qrcode_url": None,
                "qr_url": None,
                "qrcode_base64": None,
                "qr_base64": None,
                "account": None
            }

        # 1. 优先通过 OneBot 协议栈双重检验 (OneBot 端口开放且响应即表明已深度登录在线)
        try:
            import qq_bot
            onebot_client = qq_bot.QQBotClient()
            bot_conn = onebot_client.check_connection()
            if bot_conn.get("online"):
                account = {
                    "uin": str(bot_conn.get("user_id")),
                    "nick": bot_conn.get("nickname") or "QQ小号",
                    "online": True,
                    "avatarUrl": f"https://q1.qlogo.cn/g?b=qq&nk={bot_conn.get('user_id')}&s=640"
                }
                return {
                    "running": True,
                    "is_login": True,
                    "login_phase": "ready",
                    "message": f"QQ 小号已在线: {account['nick']} ({account['uin']})",
                    "login_error": None,
                    "qrcode_url": None,
                    "qr_url": None,
                    "qrcode_base64": None,
                    "qr_base64": None,
                    "account": account
                }
        except Exception:
            pass

        # 2. 查询 WebUI 内部状态
        status_res = self._request_api("/api/QQLogin/CheckLoginStatus")
        if not status_res or status_res.get("code") != 0:
            return {
                "running": True,
                "is_login": False,
                "login_phase": "connecting",
                "message": "NapCat 正在初始化 QQ 协议栈...",
                "login_error": None,
                "qrcode_url": None,
                "qr_url": None,
                "qrcode_base64": None,
                "qr_base64": None,
                "account": None
            }

        data = status_res.get("data", {})
        is_login = data.get("isLogin", False)
        phase = data.get("loginPhase", "unknown")
        qr_url = data.get("qrcodeurl")
        error_msg = data.get("loginError", "")

        # 若未登录且无有效二维码 (或处于登录错误状态)，自动触发刷新二维码自愈
        if not is_login and (not qr_url or error_msg):
            refreshed = self.refresh_qrcode()
            if refreshed.get("success"):
                qr_url = refreshed.get("qrcode_url")
                # 重新查询清除后的错误状态
                sr2 = self._request_api("/api/QQLogin/CheckLoginStatus")
                if sr2 and sr2.get("code") == 0:
                    data = sr2.get("data", {})
                    phase = data.get("loginPhase", phase)
                    error_msg = data.get("loginError", "")

        qr_b64 = None
        # 优先从 NapCat 原生生成的 qrcode.png 提取 base64
        cache_qr_path = os.path.join(self.napcat_dir, "versions", "9.9.33-52230", "resources", "app", "napcat", "cache", "qrcode.png")
        if not is_login and os.path.exists(cache_qr_path) and os.path.getsize(cache_qr_path) > 100:
            try:
                with open(cache_qr_path, "rb") as qrf:
                    qr_b64 = "data:image/png;base64," + base64.b64encode(qrf.read()).decode()
            except Exception:
                pass

        if not is_login and not qr_b64 and qr_url:
            qr_b64 = self._url_to_qr_base64(qr_url)

        account = None
        if is_login:
            info_res = self._request_api("/api/QQLogin/GetQQLoginInfo")
            if info_res and info_res.get("code") == 0 and info_res.get("data"):
                account = info_res.get("data")
                if account and not account.get("avatarUrl") and account.get("uin"):
                    account["avatarUrl"] = f"https://q1.qlogo.cn/g?b=qq&nk={account.get('uin')}&s=640"

        # 状态解释文本
        phase_desc_map = {
            "ready": "QQ 已成功在线登录",
            "waiting_qrcode": "等待手机 QQ 扫码",
            "qrcode_scanned": "已扫码，请在手机 QQ 上点击确认登录",
            "initializing": "正在加载账号会话与好友列表...",
            "reconnecting": "正在重新连接 QQ 服务器...",
            "offline": "账号离线"
        }
        status_message = phase_desc_map.get(phase, error_msg or f"状态: {phase}")

        return {
            "running": True,
            "is_login": is_login,
            "login_phase": phase,
            "message": status_message,
            "login_error": error_msg,
            "qrcode_url": qr_url,
            "qr_url": qr_url,
            "qrcode_base64": qr_b64,
            "qr_base64": qr_b64,
            "account": account
        }

    def refresh_qrcode(self) -> Dict[str, Any]:
        """强制刷新登录二维码"""
        res = self._request_api("/api/QQLogin/RefreshQRcode")
        if res and res.get("code") == 0:
            qr_url = res.get("data", {}).get("qrcodeurl")
            qr_b64 = self._url_to_qr_base64(qr_url)
            return {
                "success": True,
                "qrcode_url": qr_url,
                "qr_url": qr_url,
                "qrcode_base64": qr_b64,
                "qr_base64": qr_b64,
                "message": "二维码已刷新"
            }
        return {"success": False, "message": res.get("message") if res else "刷新二维码失败"}

    def get_quick_login_list(self) -> List[str]:
        """获取本机已缓存可免扫码快捷登录的 QQ 列表"""
        res = self._request_api("/api/QQLogin/GetQuickLoginList")
        if res and res.get("code") == 0 and isinstance(res.get("data"), list):
            return [str(x) for x in res["data"]]
        return []

    def quick_login(self, uin: str) -> Dict[str, Any]:
        """使用已存会话快速一键登录"""
        res = self._request_api("/api/QQLogin/SetQuickLogin", {"uin": str(uin)})
        if res and res.get("code") == 0:
            return {"success": True, "message": f"已提交快捷登录请求: {uin}"}
        return {"success": False, "message": res.get("message") if res else "快捷登录失败"}

# 全局单例
napcat_manager = NapCatManager()
