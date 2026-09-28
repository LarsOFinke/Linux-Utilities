import importlib.util
import os
import sys
import unittest
from unittest.mock import patch

MODULE_PATH = os.path.join(os.path.dirname(__file__), "..", "tools", "canary-mailer", "app.py")
SPEC = importlib.util.spec_from_file_location("canary_mailer_app", MODULE_PATH)
mail_app = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mail_app)


class CanaryMailerTestCase(unittest.TestCase):
    def setUp(self):
        self.env = {
            "FS_TRACKER_MAIL_TO": "ops@example.com",
            "FS_TRACKER_MAIL_FROM": "alert@example.com",
            "FS_TRACKER_MAIL_SUBJECT": "canary hit",
            "FS_TRACKER_SMTP_HOST": "smtp.example.com",
            "FS_TRACKER_SMTP_PORT": "2525",
            "FS_TRACKER_SMTP_USER": "mailer",
            "FS_TRACKER_SMTP_PASSWORD": "secret",
            "FS_TRACKER_SMTP_TLS": "true",
        }

    def test_main_sends_mail_via_smtp(self):
        with patch.dict(os.environ, self.env, clear=True):
            with patch("smtplib.SMTP") as smtp_mock:
                smtp_instance = smtp_mock.return_value.__enter__.return_value
                rc = mail_app.main(["mailer.py", "/tmp/secret.txt", "32", "1234"])
                self.assertEqual(rc, 0)

        smtp_mock.assert_called_once_with("smtp.example.com", 2525, timeout=10)
        smtp_instance.starttls.assert_called_once_with()
        smtp_instance.login.assert_called_once_with("mailer", "secret")
        smtp_instance.send_message.assert_called_once()

    def test_main_requires_smtp_host(self):
        with patch.dict(os.environ, {k: v for k, v in self.env.items() if k != "FS_TRACKER_SMTP_HOST"}, clear=True):
            rc = mail_app.main(["mailer.py", "/tmp/secret.txt", "32", "1234"])
            self.assertEqual(rc, 2)

    def test_main_requires_mail_to(self):
        with patch.dict(os.environ, {k: v for k, v in self.env.items() if k != "FS_TRACKER_MAIL_TO"}, clear=True):
            rc = mail_app.main(["mailer.py", "/tmp/secret.txt", "32", "1234"])
            self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
