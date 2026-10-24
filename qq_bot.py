import os
import base64
import requests
from typing import Dict, Any, Optional

DEFAULT_ONEBOT_URL = os.environ.get("ONEBOT_URL", "http://127.0.0.1:3000")

class QQBotClient:
    def __init__(self, base_url: str = DEFAULT_ONEBOT_URL, access_token: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.headers = {"Content-Type": "application/json"}
        if access_token:
            self.headers["Authorization"] = f"Bearer {access_token}"

    def check_connection(self) -> Dict[str, Any]:
        """
        检测与 NapCatQQ / OneBot 服务的连接状态及登录小号信息
        """
        try:
            url = f"{self.base_url}/get_login_info"
            resp = requests.get(url, headers=self.headers, timeout=2.5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "ok":
                    user_info = data.get("data", {})
                    return {
                        "online": True,
                        "user_id": user_info.get("user_id"),
                        "nickname": user_info.get("nickname"),
                        "message": f"QQ小号已在线: {user_info.get('nickname')} ({user_info.get('user_id')})"
                    }
            return {
                "online": False,
                "message": f"OneBot 服务返回异常: {resp.text}"
            }
        except requests.exceptions.RequestException:
            return {
                "online": False,
                "message": f"无法连接到 NapCatQQ 服务 ({self.base_url})。请确认已在本地启动 NapCatQQ。"
            }

    def get_groups(self) -> list:
        """获取机器人小号已加入的群聊列表"""
        try:
            url = f"{self.base_url}/get_group_list"
            resp = requests.get(url, headers=self.headers, timeout=3.5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "ok":
                    return [
                        {
                            "group_id": g.get("group_id"),
                            "group_name": g.get("group_name", f"群 {g.get('group_id')}")
                        }
                        for g in data.get("data", [])
                    ]
        except Exception as e:
            print(f"[QQBotClient] 获取群列表失败: {e}")
        return []

    def send_voice_message(self, target_id: int, silk_path: str, message_type: str = "private") -> Dict[str, Any]:
        """
        向指定 QQ 好友或 QQ 群发送原生绿底 Silk 语音条
        :param target_id: 目标 QQ 号或群号
        :param silk_path: 本地 Silk 语音文件路径
        :param message_type: 'private' (私聊好友) 或 'group' (QQ群)
        """
        if not os.path.exists(silk_path):
            raise FileNotFoundError(f"Silk 语音文件不存在: {silk_path}")

        # 使用带本地绝对路径和 .silk 扩展名的 file:/// URI，确保 NTQQ 识别原生语音格式
        abs_path = os.path.abspath(silk_path).replace("\\", "/")
        file_uri = f"file:///{abs_path}"

        record_payload = [
            {
                "type": "record",
                "data": {
                    "file": file_uri
                }
            }
        ]

        if message_type == "group":
            url = f"{self.base_url}/send_group_msg"
            payload = {
                "group_id": int(target_id),
                "message": record_payload
            }
        else:
            url = f"{self.base_url}/send_private_msg"
            payload = {
                "user_id": int(target_id),
                "message": record_payload
            }

        try:
            print(f"[NapCat 发送] 目标: {target_id} ({message_type}), URI: {file_uri}")
            resp = requests.post(url, headers=self.headers, json=payload, timeout=8.0)
            res_data = resp.json()
            print(f"[NapCat 响应] {res_data}")
            if res_data.get("status") == "ok" or res_data.get("retcode") == 0:
                return {
                    "success": True,
                    "message_id": res_data.get("data", {}).get("message_id"),
                    "message": "语音条发送成功！"
                }
            else:
                raw_err = res_data.get("message") or res_data.get("wording") or str(res_data)
                hint = ""
                if "rich media transfer failed" in raw_err:
                    if message_type == "group":
                        hint = "\n\n💡【排查提示】：QQ底层拒绝了向该群传输语音条。\n1. 请检查你的QQ小号是否确实已加入该群（未加群无法向群发消息）；\n2. 检查小号在该群是否被管理员禁言，或群内开启了全员禁言；\n3. 检查群设置是否禁止发送语音消息。"
                    else:
                        hint = "\n\n💡【排查提示】：QQ底层富媒体上传被拦截，对方可能开启了防打扰/拒收陌生人消息，或小号被临时限制发送媒体文件。"
                elif "无法获取用户信息" in raw_err:
                    hint = "\n\n💡【排查提示】：目标 QQ 号不存在，或者把群号当成了私聊好友发送（请在上方切换为「QQ 群聊」）。"

                return {
                    "success": False,
                    "message": f"QQ 发送失败: {raw_err}{hint}"
                }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "message": f"请求 NapCatQQ 失败: {str(e)}"
            }

if __name__ == "__main__":
    bot = QQBotClient()
    status = bot.check_connection()
    print("NapCatQQ 状态:", status)
