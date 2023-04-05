import json
import os
from dataclasses import dataclass

import requests


@dataclass
class Slack:
    def __init__(self):
        self.config = {}
        self.release_webhook_url = os.environ.get('SLACK_RELEASE_WEB_HOOK_URL')
        self._headers = {'Content-Type': 'application/json'}

    def push_release_message(self, message):
        print(message)
        return requests.request(
            'POST',
            self.release_webhook_url,
            data=json.dumps({"text": message}),
            headers=self._headers,
        )


