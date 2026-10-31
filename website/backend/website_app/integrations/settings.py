import os

class WebsiteSmsSettings:
    """Adapter for extracted providers; no student-system configuration fallback."""
    def __getattr__(self, key):
        if not key.startswith('SMS_'): raise AttributeError(key)
        return os.environ.get('WEBSITE_' + key, '')

settings = WebsiteSmsSettings()
