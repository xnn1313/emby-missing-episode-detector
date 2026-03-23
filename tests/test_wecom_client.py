import unittest

from app.wecom_client import WeComClient, WeComConfig, WeComError


class WeComClientTests(unittest.TestCase):
    def setUp(self):
        self.client = WeComClient(
            WeComConfig(
                enabled=True,
                corp_id="ww-test",
                agent_id=1000002,
                corp_secret="secret",
                token="token",
                encoding_aes_key="MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA",
            )
        )

    def tearDown(self):
        self.client.close()

    def test_parse_callback_message_requires_encrypted_payload(self):
        body = (
            "<xml>"
            "<ToUserName><![CDATA[ww-test]]></ToUserName>"
            "<FromUserName><![CDATA[zhangsan]]></FromUserName>"
            "<CreateTime>1710000000</CreateTime>"
            "<MsgType><![CDATA[text]]></MsgType>"
            "<Content><![CDATA[帮助]]></Content>"
            "<MsgId>123</MsgId>"
            "</xml>"
        )

        with self.assertRaises(WeComError) as context:
            self.client.parse_callback_message(
                body=body,
                signature=None,
                timestamp=None,
                nonce=None,
                require_encrypted=True,
            )

        self.assertIn("安全模式", str(context.exception))


if __name__ == "__main__":
    unittest.main()
