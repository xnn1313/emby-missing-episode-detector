import unittest

from app.wecom_command_service import WeComCommandService


class FakeTMDBClient:
    def search_tv_series_candidates(self, title: str, year=None, limit: int = 5):
        return [
            {"id": 100, "name": "黑镜", "first_air_date": "2011-12-04"},
            {"id": 101, "name": "黑镜(美版)", "first_air_date": "2025-01-01"},
        ][:limit]


class FakeHDHiveClient:
    def search_tv_resources(self, tmdb_id: str, prefer_115: bool = True):
        return [
            {
                "slug": "res-1",
                "title": "黑镜 S01-S06 1080p",
                "unlock_points": 15,
                "is_unlocked": False,
                "video_resolution": ["1080p"],
                "source": ["WEB-DL"],
            },
            {
                "slug": "res-2",
                "title": "黑镜 S01-S06 4K",
                "unlock_points": 80,
                "is_unlocked": False,
                "video_resolution": ["4K"],
                "source": ["WEB-DL"],
            },
        ]

    def unlock_resource(self, slug: str):
        return {
            "url": "https://115.com/s/abc123",
            "access_code": "1a2b",
            "full_url": "https://115.com/s/abc123?pwd=1a2b",
            "already_owned": False,
            "points_spent": 15,
        }


class FakeDB:
    def __init__(self):
        self.saved = None
        self.sessions = {}

    def save_hdhive_unlock(self, **kwargs):
        self.saved = kwargs
        return 1

    def get_hdhive_unlocks(self, limit: int = 5):
        return [
            {
                "title": "黑镜 S01-S06 1080p",
                "unlocked_at": "2026-03-17 10:00:00",
            }
        ]

    def save_wecom_session(self, user_id: str, payload):
        self.sessions[user_id] = payload
        return True

    def get_wecom_session(self, user_id: str, ttl_seconds: int):
        return self.sessions.get(user_id)

    def delete_wecom_session(self, user_id: str):
        self.sessions.pop(user_id, None)
        return True


class FakeConfigManager:
    def get_hdhive_config(self):
        return {
            "settings": {
                "prefer_115": True,
                "max_points_per_unlock": 50,
            }
        }


class WeComCommandServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = WeComCommandService()
        self.tmdb = FakeTMDBClient()
        self.hdhive = FakeHDHiveClient()
        self.db = FakeDB()
        self.config = FakeConfigManager()

    def test_search_then_resource_then_unlock(self):
        search_reply = self.service.handle_text_message(
            user_id="zhangsan",
            content="搜索 黑镜",
            tmdb_client=self.tmdb,
            hdhive_client=self.hdhive,
            db=self.db,
            config_manager=self.config,
        )
        self.assertIn("找到 2 个候选", search_reply)
        self.assertIn("黑镜 (2011-12-04)", search_reply)
        self.assertIn("黑镜(美版) (2025-01-01)", search_reply)
        self.assertIn("资源 1", search_reply)

        resource_reply = self.service.handle_text_message(
            user_id="zhangsan",
            content="资源 1",
            tmdb_client=self.tmdb,
            hdhive_client=self.hdhive,
            db=self.db,
            config_manager=self.config,
        )
        self.assertIn("黑镜 的资源如下", resource_reply)
        self.assertIn("超过积分上限", resource_reply)

        unlock_reply = self.service.handle_text_message(
            user_id="zhangsan",
            content="解锁 1",
            tmdb_client=self.tmdb,
            hdhive_client=self.hdhive,
            db=self.db,
            config_manager=self.config,
        )
        self.assertIn("解锁成功", unlock_reply)
        self.assertIn("https://115.com/s/abc123?pwd=1a2b", unlock_reply)
        self.assertEqual(self.db.saved["slug"], "res-1")

    def test_unlock_blocks_when_points_exceed_limit(self):
        self.service.handle_text_message(
            user_id="lisi",
            content="搜索 黑镜",
            tmdb_client=self.tmdb,
            hdhive_client=self.hdhive,
            db=self.db,
            config_manager=self.config,
        )
        self.service.handle_text_message(
            user_id="lisi",
            content="资源 1",
            tmdb_client=self.tmdb,
            hdhive_client=self.hdhive,
            db=self.db,
            config_manager=self.config,
        )

        reply = self.service.handle_text_message(
            user_id="lisi",
            content="解锁 2",
            tmdb_client=self.tmdb,
            hdhive_client=self.hdhive,
            db=self.db,
            config_manager=self.config,
        )
        self.assertIn("超过当前限制 50", reply)

    def test_session_survives_service_restart_when_db_available(self):
        self.service.handle_text_message(
            user_id="wangwu",
            content="搜索 黑镜",
            tmdb_client=self.tmdb,
            hdhive_client=self.hdhive,
            db=self.db,
            config_manager=self.config,
        )

        restarted_service = WeComCommandService()
        reply = restarted_service.handle_text_message(
            user_id="wangwu",
            content="资源 1",
            tmdb_client=self.tmdb,
            hdhive_client=self.hdhive,
            db=self.db,
            config_manager=self.config,
        )

        self.assertIn("黑镜 的资源如下", reply)


if __name__ == "__main__":
    unittest.main()
