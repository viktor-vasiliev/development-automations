#! /usr/bin/env python3

# This is a sample Python script.

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.
import json
import os
import subprocess
import sys
import re
import pyperclip
import requests
import logging
import webbrowser

import enquiries

# logging.basicConfig(level=logging.DEBUG)

BASE_PATH = '/home/novapulsar/PhpstormProjects'
CODE_REVIEW = 'code review'

class Bash:
    def __init__(self, path):
        self.path = path


class Wizard:
    project_names = []
    current_project_name = None
    current_workflow = None
    tickets_to_review = []
    current_project_config = {}
    config = None

    def __init__(self):
        self.config = None
        self.read_config_file()
        self.get_project_names()

    def read_config_file(self):
        with open('config.json') as json_file:
            self.config = json.load(json_file)

    def get_project_names(self):
        self.project_names = list(map(lambda x: x['name'], self.config['projects']))

    def choose_project(self):
        self.current_project_name = enquiries.choose('Choose one of the projects: ', self.project_names)
        self.load_project_config(self.current_project_name)

    def choose_workflow(self):
        self.current_workflow = enquiries.choose('Choose one of the workflows: ', [CODE_REVIEW])
        self.handle_workflow()

    def load_project_config(self, project_name):
        loaded_config = next(obj for obj in self.config['projects'] if obj['name'] == project_name)

    def handle_code_review(self):
        self.tickets_to_review = str(input('Enter tickets to review: ')).split(',')
        if len(self.tickets_to_review) > 0:
            for ticket in self.tickets_to_review:
                branch_name = 'issue/' + ticket

    def handle_workflow(self):
        if self.current_workflow == CODE_REVIEW:
            self.handle_code_review()



class Releaser:
    def __init__(self, frontend_project, project, jira_project_name):
        self.jira_project_name = jira_project_name
        self.project = project
        self.frontend_project = frontend_project
        self.project_from_directory = BASE_PATH + '/' + frontend_project
        self.project_directory = BASE_PATH + '/' + project

    def get_last_tag(self):
        p = subprocess.run(
            ["git", "describe", "--tags"],
            cwd=self.project_from_directory,
            capture_output=True,
            universal_newlines=True
        )
        return p.stdout.strip()

    def is_release_branch(self):
        return self.get_current_branch() == 'master'

    def run_shell_command(self, command):
        print(command)
        p = subprocess.run(
            command.split(' '),
            cwd=self.project_from_directory,
            capture_output=True,
            universal_newlines=True,
        )
        return p.stdout.strip()

    def has_not_staged_changes(self):
        output = self.run_shell_command('git status')
        if len(re.findall('Changes not staged for commit', output)) > 0:
            return True
        else:
            return False

    def get_current_branch(self):
        return self.run_shell_command('git rev-parse --abbrev-ref HEAD')

    def get_commits(self, tag1, tag2):
        command = f'git log {tag1}...{tag2}'
        return self.run_shell_command(command)

    def get_commit_update_frontend(self, commit_message):
        command = f'git add package.json package.lock'
        self.run_shell_command(command)

        command = f'git commit -m {commit_message}'
        self.run_shell_command(command)

    def get_last_installed_tag(self):
        with open(self.project_directory + '/package.json') as json_file:
            data = json.load(json_file)
            package_name = data['dependencies'][self.frontend_project]
            match = re.findall('#(.+)$', package_name)
            if len(match) > 0:
                return match[0]
            return None

    def is_ready_for_release(self):
        ready_to_release = False
        if not self.is_release_branch():
            print("You are not on the release branch")
            response = input("Switch to the release branch y/n?")
            if response == 'y':
                if not self.has_not_staged_changes():
                    self.run_shell_command('git checkout master')
                    if self.is_release_branch():
                        ready_to_release = True

        else:
            ready_to_release = True

        return ready_to_release

    def send_webhook(self):
        data = {}
        tickets = ["PER-2407", "PER-2414", "PER-2418"]
        data['issues'] = tickets
        response = requests.post(
            'https://automation.atlassian.com/pro/hooks/f5f11cb39c540b89c8398262eb6bfaf0a01fb8ae',
            data=data,
            headers={
                'Content-Type': 'application/json'
            }
        )
        print(response.status_code)

    def update_frontend_package(self):

        if not self.is_ready_for_release():
            print('Not Ready for Release')
            return

        last_existed_tag = self.get_last_tag()
        last_installed_tag = self.get_last_installed_tag()
        print(last_existed_tag)
        print(last_installed_tag)

        if last_installed_tag == last_existed_tag:
            print("Nothing to update")
            return
        else:
            commits = self.get_commits(last_existed_tag, last_installed_tag).strip()
            tickets = re.findall('(' + self.jira_project_name + '-\d+)', commits)
            tickets = list(set(tickets))
            tickets.sort()
            commit_message = f'feat({str(self.frontend_project).replace("sxope-", "")}): update package to {last_existed_tag} ({", ".join(tickets)})'

            formatted_tickets = "\n".join(tickets)
            formatted_package_name = str(self.frontend_project).replace('-', ' ').title().replace(' ', '-').replace('Sxope','SXOPE')
            release_message = f'Version {last_existed_tag} has been published to *{formatted_package_name}* package: \n{formatted_tickets}'
            # copy release message
            pyperclip.copy(release_message)
            print(commit_message)
            print(release_message)

    def make_review(self):
        print(self.frontend_project)
        self.run_shell_command('git for-each-ref --sort=-committerdate refs/heads/')
        webbrowser.open_new_tab('https://github.com/inventcorp/sxope-persona-frontend/commit'
                                '/6b29865c28480c18c1cfb19145672e4e89820ebf')


def frontend_packages(x):
    """

    :type x: Array
    """
    return 'frontend' in x


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    filtered = filter(frontend_packages, os.listdir(BASE_PATH))
    arg1 = sys.argv[1]

    if arg1 == 'release-sandbox':
        releaser = Releaser('sxope-sandbox-frontend', 'sxope-sandbox', "SNX")
        releaser.update_frontend_package()

    if arg1 == 'release-persona':
        releaser = Releaser('sxope-persona-frontend', 'sxope-persona', "PER")
        releaser.update_frontend_package()

    if arg1 == 'release-tag':
        releaser = Releaser('sxope-tag-frontend', 'sxope-tag', "TAG")
        releaser.update_frontend_package()

    if arg1 == 'move-jira-tickets':
        releaser = Releaser('sxope-persona-frontend', 'sxope-persona', "PER")
        releaser.send_webhook()

    if arg1 == 'review':
        releaser = Releaser('sxope-persona-frontend', 'sxope-persona', "PER")
        releaser.make_review()

    if arg1 == 'test':
        releaser = Releaser('sxope-persona-frontend', 'sxope-persona', "PER")
        options = ['Do Something 1', 'Do Something 2', 'Do Something 3']
        choice = enquiries.choose('Choose one of these options: ', options)
        print(choice)

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
