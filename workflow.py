from dataclasses import dataclass

from jira import JiraClient


@dataclass
class WorkFlow:
    MAKE_RELEASE = 'MAKE_RELEASE'
    UPDATE_BACKEND = 'UPDATE_BACKEND'

    def __init__(self):
        self.jira = JiraClient()
        self._steps = []

    def add_step(self, step: str, payload: dict):
        self._steps.append({step: step, payload: payload})

    def handle(self):
        for step in self._steps:
            if step == self.MAKE_RELEASE:
                self.make_release(step.payload)
            if step == self.UPDATE_BACKEND:
                self.update_backend(step.payload)

    def make_release(self, payload):
        print('MAKE_RELEASE')
        pass

    def update_backend(self, payload):
        print('UPDATE_BACKEND')
        pass
