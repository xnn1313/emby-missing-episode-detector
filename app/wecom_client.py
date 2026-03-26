"""
企业微信应用客户端
支持回调消息验签/加解密，以及主动发送应用消息
"""

from __future__ import annotations

import base64
import hashlib
import os
import secrets
import struct
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from loguru import logger


class WeComError(Exception):
    """企业微信相关错误"""


@dataclass
class WeComConfig:
    """企业微信配置"""

    enabled: bool = False
    corp_id: str = ""
    agent_id: int = 0
    corp_secret: str = ""
    token: str = ""
    encoding_aes_key: str = ""
    base_url: str = "https://qyapi.weixin.qq.com/cgi-bin"


class _PKCS7Encoder:
    """企业微信回调使用 32 位分组补位"""

    block_size = 32

    @classmethod
    def encode(cls, text: bytes) -> bytes:
        amount_to_pad = cls.block_size - (len(text) % cls.block_size)
        if amount_to_pad == 0:
            amount_to_pad = cls.block_size
        return text + bytes([amount_to_pad]) * amount_to_pad

    @classmethod
    def decode(cls, text: bytes) -> bytes:
        if not text:
            return text
        pad = text[-1]
        if pad < 1 or pad > cls.block_size:
            raise WeComError("非法的 PKCS7 补位")
        return text[:-pad]


class WeComCrypto:
    """企业微信回调消息加解密"""

    def __init__(self, token: str, encoding_aes_key: str, receive_id: str):
        if not token or not encoding_aes_key or not receive_id:
            raise WeComError("企业微信回调加解密配置不完整")

        self.token = token
        self.receive_id = receive_id

        try:
            self.aes_key = base64.b64decode(f"{encoding_aes_key}=")
        except Exception as exc:
            raise WeComError(f"EncodingAESKey 非法: {exc}") from exc

        if len(self.aes_key) != 32:
            raise WeComError("EncodingAESKey 解码后长度必须为 32 字节")

        self.iv = self.aes_key[:16]

    def _cipher(self) -> Cipher:
        return Cipher(algorithms.AES(self.aes_key), modes.CBC(self.iv))

    def generate_signature(self, timestamp: str, nonce: str, encrypted: str) -> str:
        raw = "".join(sorted([self.token, timestamp, nonce, encrypted]))
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def verify_signature(self, signature: str, timestamp: str, nonce: str, encrypted: str):
        expect = self.generate_signature(timestamp, nonce, encrypted)
        if expect != signature:
            raise WeComError("企业微信签名校验失败")

    def decrypt(self, encrypted: str) -> str:
        try:
            encrypted_bytes = base64.b64decode(encrypted)
            decryptor = self._cipher().decryptor()
            padded = decryptor.update(encrypted_bytes) + decryptor.finalize()
            plain = _PKCS7Encoder.decode(padded)
        except Exception as exc:
            raise WeComError(f"企业微信消息解密失败: {exc}") from exc

        if len(plain) < 20:
            raise WeComError("企业微信消息体长度非法")

        xml_length = struct.unpack("!I", plain[16:20])[0]
        xml_content = plain[20:20 + xml_length]
        receive_id = plain[20 + xml_length :].decode("utf-8")

        if receive_id != self.receive_id:
            raise WeComError("企业微信 receive_id 校验失败")

        return xml_content.decode("utf-8")

    def encrypt(self, message: str) -> str:
        message_bytes = message.encode("utf-8")
        raw = (
            os.urandom(16)
            + struct.pack("!I", len(message_bytes))
            + message_bytes
            + self.receive_id.encode("utf-8")
        )
        padded = _PKCS7Encoder.encode(raw)
        encryptor = self._cipher().encryptor()
        encrypted = encryptor.update(padded) + encryptor.finalize()
        return base64.b64encode(encrypted).decode("utf-8")


class WeComClient:
    """企业微信应用客户端"""

    def __init__(self, config: WeComConfig):
        self.config = config
        self.base_url = config.base_url.rstrip("/")
        self.http = httpx.Client(timeout=20.0)
        self._access_token = ""
        self._access_token_expire_at = 0.0
        self.crypto = None

        if config.token and config.encoding_aes_key and config.corp_id:
            self.crypto = WeComCrypto(
                token=config.token,
                encoding_aes_key=config.encoding_aes_key,
                receive_id=config.corp_id,
            )

    def close(self):
        self.http.close()

    def can_callback(self) -> bool:
        return self.crypto is not None

    def can_send(self) -> bool:
        return bool(self.config.corp_id and self.config.corp_secret and self.config.agent_id)

    def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        response = self.http.request(method, url, **kwargs)
        data = response.json()

        errcode = data.get("errcode", 0)
        if errcode != 0:
            raise WeComError(data.get("errmsg", f"企业微信接口错误: {errcode}"))

        return data

    def get_access_token(self, force_refresh: bool = False) -> str:
        if not self.can_send():
            raise WeComError("企业微信主动发送消息配置不完整")

        now = time.time()
        if not force_refresh and self._access_token and now < self._access_token_expire_at:
            return self._access_token

        data = self._request(
            "GET",
            "/gettoken",
            params={
                "corpid": self.config.corp_id,
                "corpsecret": self.config.corp_secret,
            },
        )

        self._access_token = data.get("access_token", "")
        expires_in = int(data.get("expires_in", 7200))
        self._access_token_expire_at = now + max(300, expires_in - 120)
        return self._access_token

    def send_text_message(self, user_id: str, content: str, safe: int = 0) -> Dict[str, Any]:
        token = self.get_access_token()
        data = self._request(
            "POST",
            "/message/send",
            params={"access_token": token},
            json={
                "touser": user_id,
                "msgtype": "text",
                "agentid": self.config.agent_id,
                "text": {"content": content},
                "safe": safe,
            },
        )
        logger.info(f"企业微信消息发送成功: {user_id}")
        return data

    def upload_media_image_url(self, image_url: str) -> Optional[str]:
        """下载远程图片并上传为企业微信临时素材，返回 media_id。失败返回 None。"""
        if not self.can_send():
            return None
        try:
            img_resp = self.http.get(image_url, timeout=15.0, follow_redirects=True)
            if img_resp.status_code != 200:
                logger.warning(f"下载图片失败: {image_url} status={img_resp.status_code}")
                return None
            content_type = img_resp.headers.get("content-type", "image/jpeg")
            if "png" in content_type:
                ext = "png"
            elif "webp" in content_type:
                ext = "webp"
            else:
                ext = "jpg"
            token = self.get_access_token()
            upload_resp = self.http.post(
                f"{self.base_url}/media/upload",
                params={"access_token": token, "type": "image"},
                files={"media": (f"poster.{ext}", img_resp.content, content_type)},
                timeout=30.0,
            )
            upload_data = upload_resp.json()
            if upload_data.get("errcode", 0) != 0:
                logger.warning(f"企业微信上传素材失败: {upload_data}")
                return None
            media_id = upload_data.get("media_id")
            logger.info(f"企业微信临时素材上传成功: media_id={media_id}")
            return media_id
        except Exception as exc:
            logger.warning(f"企业微信上传图片异常: {exc}")
            return None

    def send_image_message(self, user_id: str, media_id: str) -> Dict[str, Any]:
        """发送图片消息（使用临时素材 media_id）"""
        token = self.get_access_token()
        data = self._request(
            "POST",
            "/message/send",
            params={"access_token": token},
            json={
                "touser": user_id,
                "msgtype": "image",
                "agentid": self.config.agent_id,
                "image": {"media_id": media_id},
            },
        )
        logger.info(f"企业微信图片消息发送成功: {user_id}")
        return data

    def send_news_message(self, user_id: str, articles: list) -> Dict[str, Any]:
        """发送图文消息（mpnews 样式，最多 8 条）"""
        token = self.get_access_token()
        data = self._request(
            "POST",
            "/message/send",
            params={"access_token": token},
            json={
                "touser": user_id,
                "msgtype": "textcard",
                "agentid": self.config.agent_id,
                "textcard": articles[0] if articles else {},
            },
        )
        logger.info(f"企业微信文字卡片消息发送成功: {user_id}")
        return data

    def verify_callback_url(self, signature: str, timestamp: str, nonce: str, echostr: str) -> str:
        if not self.crypto:
            raise WeComError("企业微信回调加解密未配置")
        self.crypto.verify_signature(signature, timestamp, nonce, echostr)
        return self.crypto.decrypt(echostr)

    def parse_callback_message(
        self,
        body: str,
        signature: Optional[str],
        timestamp: Optional[str],
        nonce: Optional[str],
        require_encrypted: bool = True,
    ) -> Dict[str, Any]:
        root = ET.fromstring(body)
        encrypted = root.findtext("Encrypt")

        if encrypted:
            if not self.crypto:
                raise WeComError("收到加密回调，但服务端未配置加解密参数")
            if not signature or not timestamp or not nonce:
                raise WeComError("企业微信回调缺少签名参数")

            self.crypto.verify_signature(signature, timestamp, nonce, encrypted)
            payload = self.crypto.decrypt(encrypted)
            message_root = ET.fromstring(payload)
        else:
            if require_encrypted:
                raise WeComError("企业微信回调必须使用安全模式（加密消息）")
            message_root = root

        return {child.tag: (child.text or "") for child in message_root}

    def build_text_reply(
        self,
        to_user: str,
        from_user: str,
        content: str,
        timestamp: Optional[str] = None,
        nonce: Optional[str] = None,
    ) -> str:
        created = timestamp or str(int(time.time()))
        plain_xml = (
            "<xml>"
            f"<ToUserName><![CDATA[{to_user}]]></ToUserName>"
            f"<FromUserName><![CDATA[{from_user}]]></FromUserName>"
            f"<CreateTime>{created}</CreateTime>"
            "<MsgType><![CDATA[text]]></MsgType>"
            f"<Content><![CDATA[{content}]]></Content>"
            "</xml>"
        )

        if not self.crypto:
            return plain_xml

        reply_nonce = nonce or secrets.token_hex(8)
        encrypted = self.crypto.encrypt(plain_xml)
        signature = self.crypto.generate_signature(created, reply_nonce, encrypted)
        return (
            "<xml>"
            f"<Encrypt><![CDATA[{encrypted}]]></Encrypt>"
            f"<MsgSignature><![CDATA[{signature}]]></MsgSignature>"
            f"<TimeStamp>{created}</TimeStamp>"
            f"<Nonce><![CDATA[{reply_nonce}]]></Nonce>"
            "</xml>"
        )


def create_client_from_config(config_dict: Dict[str, Any]) -> WeComClient:
    """从配置字典创建企业微信客户端"""

    return WeComClient(
        WeComConfig(
            enabled=config_dict.get("enabled", False),
            corp_id=config_dict.get("corp_id", ""),
            agent_id=int(config_dict.get("agent_id", 0) or 0),
            corp_secret=config_dict.get("corp_secret", ""),
            token=config_dict.get("token", ""),
            encoding_aes_key=config_dict.get("encoding_aes_key", ""),
            base_url=config_dict.get("base_url", "https://qyapi.weixin.qq.com/cgi-bin"),
        )
    )
