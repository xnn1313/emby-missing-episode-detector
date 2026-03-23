import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import BackgroundTasks, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from starlette.requests import Request

import app.auth as auth_module
import app.config_manager as config_module
import main
from app.database import Database


class FakeEmbyClient:
    def __init__(self, host: str, api_key: str):
        self.host = host
        self.api_key = api_key

    def test_connection(self) -> bool:
        return True

    def close(self):
        return None


class FakeTMDBClient:
    def __init__(self, api_key: str, language: str = "zh-CN", proxy_url: str = ""):
        self.api_key = api_key
        self.language = language
        self.proxy_url = proxy_url

    def close(self):
        return None


class FakeTMDBMatcher:
    def __init__(self, client):
        self.tmdb = client


class FakeExporter:
    def __init__(self, *args, **kwargs):
        return None


class FakeScheduler:
    instances = []

    def __init__(self, emby_client, detector, notifier_manager=None):
        self.emby_client = emby_client
        self.detector = detector
        self.notifier_manager = notifier_manager
        self.started_interval = None
        self.shutdown_called = False
        FakeScheduler.instances.append(self)

    def start_auto_detection(self, interval_minutes: int = 60):
        self.started_interval = interval_minutes

    def shutdown(self):
        self.shutdown_called = True

    def get_status(self):
        return {"started_interval": self.started_interval}


class FakeMoviePilotClient:
    def __init__(self, host: str, username: str = "admin", password: str = ""):
        self.host = host
        self.username = username
        self.password = password

    def subscribe_tv(self, title: str, year=None, season=None, fuzzy_match=True):
        return {"success": True, "data": {"id": 12345}}

    def close(self):
        return None


class FakeEmbyClientDisconnected(FakeEmbyClient):
    def test_connection(self) -> bool:
        return False


class MainApiTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.tempdir.name) / "settings.json"
        self.user_db_path = Path(self.tempdir.name) / "users.json"
        self.sqlite_path = Path(self.tempdir.name) / "test.db"

        self.config_path.write_text(json.dumps({
            "emby": {
                "host": "http://emby.local:8096",
                "api_key": "emby-secret"
            },
            "libraries": {
                "enabled": True,
                "selected_ids": ["lib-1"]
            },
            "tmdb": {
                "enabled": True,
                "api_key": "tmdb-secret"
            },
            "detection": {
                "interval_minutes": 30,
                "auto_start": True
            },
            "moviepilot": {
                "host": "http://moviepilot.local:3000",
                "username": "admin",
                "password": "moviepilot-secret",
                "enabled": True,
                "auto_download": True,
                "download_path": ""
            },
            "hdhive": {
                "enabled": False,
                "api_key": "",
                "base_url": "https://hdhive.com/api/open",
                "proxy": {
                    "enabled": False,
                    "host": "",
                    "port": 0,
                    "username": "",
                    "password": ""
                },
                "settings": {
                    "max_points_per_unlock": 50,
                    "prefer_115": True,
                    "auto_unlock": False
                }
            },
            "wecom": {
                "enabled": True,
                "corp_id": "ww-test",
                "agent_id": 1000002,
                "corp_secret": "wecom-secret",
                "token": "wecom-token",
                "encoding_aes_key": "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA",
                "base_url": "https://qyapi.weixin.qq.com/cgi-bin"
            }
        }), encoding="utf-8")

        os.environ["CONFIG_PATH"] = str(self.config_path)
        os.environ["USER_DB_PATH"] = str(self.user_db_path)

        auth_module.user_db = None
        config_module._config_manager = config_module.ConfigManager(str(self.config_path))
        FakeScheduler.instances = []

        self.database = Database(str(self.sqlite_path))

        self.patches = [
            patch.object(main, "EmbyClient", FakeEmbyClient),
            patch.object(main, "TMDBClient", FakeTMDBClient),
            patch.object(main, "TMDBMatcher", FakeTMDBMatcher),
            patch.object(main, "DetectionScheduler", FakeScheduler),
            patch.object(main, "ReportExporter", FakeExporter),
            patch.object(main, "setup_notifiers_from_env", lambda: None),
            patch.object(main, "get_database", lambda: self.database),
            patch("app.moviepilot_client.MoviePilotClient", FakeMoviePilotClient),
        ]

        for active_patch in self.patches:
            active_patch.start()

        main.emby_client = None
        main.tmdb_client = None
        main.tmdb_matcher = None
        main.detector = None
        main.notifier_manager = None
        main.db = None
        main.exporter = None
        main.detection_scheduler = None
        main.config_manager = config_module.get_config_manager()
        main.moviepilot_client = None
        main.hdhive_client = None
        main.wecom_client = None
        main.last_result = None
        main._apply_runtime_config(main.config_manager.get_all_config())

    def tearDown(self):
        if main.detection_scheduler is not None:
            try:
                main.detection_scheduler.shutdown()
            except Exception:
                pass

        for active_patch in reversed(self.patches):
            active_patch.stop()

        auth_module.user_db = None
        config_module._config_manager = None

        os.environ.pop("CONFIG_PATH", None)
        os.environ.pop("USER_DB_PATH", None)
        self.tempdir.cleanup()

    def login_headers_user(self):
        response = asyncio.run(main.login(main.LoginRequest(
            username="admin",
            password="admin123"
        )))
        self.assertEqual(response["status"], "success")
        token = response["access_token"]
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        user = main.get_current_user(creds)
        return {"Authorization": f"Bearer {token}"}, user

    def test_config_requires_auth_and_masks_secrets(self):
        with self.assertRaises(HTTPException) as context:
            main.get_current_user(None)
        self.assertEqual(context.exception.status_code, 401)

        _, user = self.login_headers_user()
        response = asyncio.run(main.get_config(user))

        config = response["config"]
        self.assertEqual(config["emby"]["api_key"], "***")
        self.assertEqual(config["tmdb"]["api_key"], "***")

    def test_runtime_config_passes_proxy_to_tmdb_client(self):
        self.assertIsNotNone(main.tmdb_client)
        self.assertEqual("tmdb-secret", main.tmdb_client.api_key)
        self.assertEqual("zh-CN", main.tmdb_client.language)
        self.assertEqual("", main.tmdb_client.proxy_url)

        config = main.config_manager.get_all_config()
        config["hdhive"]["proxy"] = {
            "enabled": True,
            "host": "192.168.21.90",
            "port": 2017,
            "username": "",
            "password": "",
        }

        main._apply_runtime_config(config)

        self.assertEqual("http://192.168.21.90:2017", main.tmdb_client.proxy_url)

    def test_runtime_config_initializes_wecom_without_emby(self):
        config = main.config_manager.get_all_config()
        config["emby"] = {
            "host": "",
            "api_key": "",
        }

        main._apply_runtime_config(config)

        self.assertIsNone(main.emby_client)
        self.assertIsNotNone(main.wecom_client)
        self.assertIsNone(main.detection_scheduler)

    def test_set_config_preserves_masked_secrets_and_restarts_scheduler(self):
        _, user = self.login_headers_user()
        self.assertEqual(len(FakeScheduler.instances), 1)
        original_scheduler = FakeScheduler.instances[0]

        response = asyncio.run(main.set_config(main.FullConfig.model_validate({
            "emby": {
                "host": "http://emby.changed:8096",
                "api_key": "***"
            },
            "libraries": {
                "enabled": True,
                "selected_ids": ["lib-2", "lib-3"]
            },
            "tmdb": {
                "enabled": True,
                "api_key": "***"
            },
            "detection": {
                "interval_minutes": 45,
                "auto_start": True
            },
            "moviepilot": {
                "host": "http://moviepilot.changed:3000",
                "username": "admin",
                "password": "***",
                "enabled": True,
                "auto_download": True,
                "download_path": "/downloads/tv"
            }
        }), user))

        self.assertEqual(response["status"], "success")
        self.assertEqual(len(FakeScheduler.instances), 2)
        self.assertTrue(original_scheduler.shutdown_called)

        saved_config = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(saved_config["emby"]["host"], "http://emby.changed:8096")
        self.assertEqual(saved_config["emby"]["api_key"], "emby-secret")
        self.assertEqual(saved_config["tmdb"]["api_key"], "tmdb-secret")
        self.assertEqual(saved_config["moviepilot"]["password"], "moviepilot-secret")
        self.assertEqual(saved_config["detection"]["interval_minutes"], 45)
        self.assertEqual(saved_config["libraries"]["selected_ids"], ["lib-2", "lib-3"])
        self.assertEqual(saved_config["wecom"]["corp_secret"], "wecom-secret")
        self.assertEqual(saved_config["wecom"]["token"], "wecom-token")
        self.assertEqual(saved_config["wecom"]["encoding_aes_key"], "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA")

    def test_download_route_persists_completed_status(self):
        _, user = self.login_headers_user()

        response = asyncio.run(main.push_download(main.DownloadRequest(
            series_id="series-1",
            series_name="Test Series",
            season=1,
            episodes=[2, 3, 4]
        ), user))

        self.assertEqual(response["status"], "success")

        history = self.database.get_download_history(series_id="series-1", limit=10)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["status"], "completed")
        self.assertEqual(history[0]["moviepilot_task_id"], "12345")
        self.assertIsNotNone(history[0]["completed_at"])

    def test_run_detection_fails_when_emby_is_unreachable(self):
        main.emby_client = FakeEmbyClientDisconnected("http://emby.unreachable:8096", "bad-key")

        with self.assertRaises(HTTPException) as context:
            asyncio.run(main.run_detection())

        self.assertEqual(context.exception.status_code, 502)
        self.assertIn("无法连接到 Emby 服务器", context.exception.detail)

    def test_wecom_callback_async_reply_is_idempotent(self):
        sent_messages = []

        def fake_send_text_message(user_id: str, content: str, safe: int = 0):
            sent_messages.append({
                "user_id": user_id,
                "content": content,
                "safe": safe,
            })
            return {"errcode": 0}

        plain_xml = (
            "<xml>"
            "<ToUserName><![CDATA[ww-test]]></ToUserName>"
            "<FromUserName><![CDATA[zhangsan]]></FromUserName>"
            "<CreateTime>1710000000</CreateTime>"
            "<MsgType><![CDATA[text]]></MsgType>"
            "<Content><![CDATA[帮助]]></Content>"
            "<MsgId>123456</MsgId>"
            "<AgentID>1000002</AgentID>"
            "</xml>"
        )
        encrypted = main.wecom_client.crypto.encrypt(plain_xml)
        timestamp = "1710000001"
        nonce = "nonce-1"
        signature = main.wecom_client.crypto.generate_signature(timestamp, nonce, encrypted)
        body = f"<xml><Encrypt><![CDATA[{encrypted}]]></Encrypt></xml>"

        main.wecom_client.send_text_message = fake_send_text_message

        def build_request():
            scope = {
                "type": "http",
                "method": "POST",
                "path": "/api/wecom/callback",
                "headers": [(b"content-type", b"application/xml")],
                "query_string": b"",
            }

            async def receive():
                return {
                    "type": "http.request",
                    "body": body.encode("utf-8"),
                    "more_body": False,
                }

            return Request(scope, receive)

        background_tasks = BackgroundTasks()
        response = asyncio.run(main.receive_wecom_callback(
            request=build_request(),
            background_tasks=background_tasks,
            msg_signature=signature,
            timestamp=timestamp,
            nonce=nonce,
        ))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.body.decode("utf-8"), "success")
        for task in background_tasks.tasks:
            task.func(*task.args, **task.kwargs)

        duplicate_tasks = BackgroundTasks()
        duplicate_response = asyncio.run(main.receive_wecom_callback(
            request=build_request(),
            background_tasks=duplicate_tasks,
            msg_signature=signature,
            timestamp=timestamp,
            nonce=nonce,
        ))
        self.assertEqual(duplicate_response.status_code, 200)
        self.assertEqual(duplicate_response.body.decode("utf-8"), "success")
        self.assertEqual(len(duplicate_tasks.tasks), 0)

        self.assertEqual(len(sent_messages), 1)
        self.assertEqual(sent_messages[0]["user_id"], "zhangsan")
        self.assertIn("可用命令", sent_messages[0]["content"])

        record = self.database.get_wecom_message("msgid:123456")
        self.assertIsNotNone(record)
        self.assertEqual(record["status"], "completed")
        self.assertEqual(record["delivery_mode"], "async")


if __name__ == "__main__":
    unittest.main()
