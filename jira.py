import json
import os
import sys
import time
from dataclasses import dataclass
import re
import enquiries

import requests
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

from slack import Slack

TO_DO = 'TO_DO'
IN_PROGRESS = 'IN_PROGRESS'
PUT_OFF = 'PUT_OFF'
CODE_REVIEW = 'CODE_REVIEW'
ON_STAGE = 'ON_STAGE'
WAIT_FOR_STAGE = 'WAIT_FOR_STAGE'
ON_PROD = 'ON_PROD'
ON_PREPROD = 'ON_PREPROD'
DONE = 'DONE'

STATUSES_MAP = [TO_DO, IN_PROGRESS, PUT_OFF, CODE_REVIEW, ON_STAGE, WAIT_FOR_STAGE, ON_PROD, ON_PREPROD, DONE]


@dataclass
class JiraClient:
    project_url: str
    current_ticket = ''
    _auth: HTTPBasicAuth
    _headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    _statusesMap = {}
    _assigneeMap = {}

    def __init__(self):
        self._auth = HTTPBasicAuth(
            os.environ.get('JIRA_EMAIL'),
            os.environ.get('JIRA_TOKEN')
        )

        self.project_url = os.environ.get('JIRA_PROJECT_URL')

    def get_url(self):
        return f'{self.project_url}/rest/api/3/issue/{self.current_ticket}'

    def create_comment(self, current_ticket: str, **kwargs):
        self.current_ticket = current_ticket

        if kwargs.get('commit'):
            commit = kwargs.get('commit')
            payload = json.dumps({
                "body": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "content": [
                                {
                                    "attrs": {
                                        "url": commit
                                    },
                                    "type": "inlineCard"
                                },
                                {
                                    "text": " ",
                                    "type": "text"
                                }
                            ],
                            "type": "paragraph"
                        }
                    ],

                }
            })

        elif kwargs.get('comment'):
            comment = kwargs.get('comment')
            payload = json.dumps({
                "body": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {
                                    "text": comment,
                                    "type": "text"
                                }
                            ]
                        }
                    ]
                }
            })
        elif kwargs.get('mention'):
            mention = kwargs.get('mention')
            payload = json.dumps({
                "body": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "mention",
                            "attrs": {
                                "id": mention['accountId'],
                                "text": "@" + mention['author'],
                                "userType": "APP"
                            }
                        },
                        {
                            "type": "paragraph",
                            "content": [
                                {
                                    "text": mention['comment'],
                                    "type": "text"
                                }
                            ]
                        }
                    ]
                }
            })
        else:
            return
        return requests.request(
            'POST',
            self.get_url() + '/comment',
            data=payload,
            headers=self._headers,
            auth=self._auth
        )

    def get_comments(self, current_ticket):
        self.current_ticket = current_ticket
        print(self.get_url() + '/comment')
        return self.get_request(self.get_url() + '/comment')

    def get_last_link(self, current_ticket):
        self.current_ticket = current_ticket
        response = dict(self.get_request(self.get_url() + '/comment').json())
        comments = response['comments']
        for comment in comments:
            if comment['body']['content']:
                for contentItem in comment['body']['content']:
                    for contentItemDeep in contentItem['content']:
                        if contentItemDeep['type'] == 'inlineCard' and contentItemDeep['attrs']['url']:
                            return {
                                "accountId": comment['author']['accountId'],
                                "authorName": comment['author']['displayName'],
                                'url': contentItemDeep['attrs']['url']
                            }
        return False

    def get_status_by_alias(self, alias):
        if alias in self._statusesMap:
            return self._statusesMap[alias]
        else:
            raise Exception('Status ID for ALIAS ' + alias + ' not found')

    def set_status(self, current_ticket, status):
        if not bool(self._statusesMap):
            self.load_transitions(current_ticket)
        self.current_ticket = current_ticket

        return self.post_request(
            self.get_url() + '/transitions',
            json.dumps({
                "transition": {"id": self.get_status_by_alias(status)}
            }))

    def set_assignee(self, current_ticket, assignee=None):
        self.current_ticket = current_ticket
        return self.put_request(
            self.get_url() + '/assignee',
            json.dumps({"accountId": assignee})
        )

    def load_transitions(self, current_ticket):
        self.current_ticket = current_ticket

        transitions_response = self.get_request(self.get_url() + '/transitions')
        if transitions_response.status_code == 200:
            transitions = transitions_response.json()['transitions']
            for transition in transitions:
                prepared_name = str(transition['name']).upper().replace(" ", "_")
                self._statusesMap[prepared_name] = transition['id']
        else:
            print(transitions_response.status_code)
        return self._statusesMap

    def load_assignee(self, current_ticket):
        self.current_ticket = current_ticket

        assignee_response = self.get_request(self.get_url() + '/assignee')
        if assignee_response.status_code == 200:
            assignees = assignee_response.json()['assignee']
            print(assignees)
            for assignee in assignees:
                prepared_name = str(assignee['name']).upper().replace(" ", "_")
                self._assigneeMap[prepared_name] = assignee['id']
        else:
            print(assignee_response.status_code)
        return self._assigneeMap

    def get_request(self, url):
        return requests.get(
            url,
            headers=self._headers,
            auth=self._auth
        )

    def post_request(self, url, payload: dict):
        return requests.request(
            'POST',
            url,
            data=payload,
            headers=self._headers,
            auth=self._auth
        )

    def put_request(self, url, payload: dict):
        return requests.request(
            'PUT',
            url,
            data=payload,
            headers=self._headers,
            auth=self._auth
        )

    def get_tickets_in_code_review(self, jira_project_key: str):
        url = f'{self.project_url}/rest/api/3/search?jql=project={jira_project_key} AND status = "Code Review" AND ' \
              f'assignee IN ("5ec7ac320221530c2ec47b47") ORDER BY created DESC '
        return self.get_request(url)


load_dotenv()

# slack = Slack()
#
# # r = slack.push_release_message("release message")
# # print(r.status_code)
# # sys.exit("Debug exit")
#
# jira = JiraClient()
# # r = jira.create_comment('TEST-1', commit="https://www.geeksforgeeks.org/convert-json-to-dictionary-in-python/")
# # r = jira.get_comments('TEST-1')
# jira.load_transitions('SNX-592')
# r = jira.set_status('SNX-592', 'TO_DO')
# r = jira.set_assignee('SNX-592')
# print(r.status_code)
# print(r.text)

if __name__ == '__main__':
    arg1 = sys.argv[1]
    jira = JiraClient()
    jira.load_transitions('SNX-592')
    end_status = enquiries.choose('Choose one of the jira statuses: ', STATUSES_MAP)
    raw_tickets = str(input('Insert list of tickets you want to handle:'))
    if arg1 == 'move':
        tickets = re.findall('([A-Z]{2,10}-\d+)', raw_tickets)
        for ticket in tickets:
            jira.set_status(ticket, end_status)
            jira.set_assignee(ticket)
        print(tickets)
