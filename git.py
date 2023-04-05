import json
import os
import re
import subprocess
import webbrowser

import inquirer

from jira import JiraClient
from main import Releaser

BASE_PATH = '/home/sxope/PhpstormProjects'
import enquiries


class Git:
    def __init__(self):
        self.config = None
        self.frontend_project = None
        self.backend_project = None
        self.project_from_directory = None
        self.projects = []
        self.project_directory = None
        self.current_flow = None
        self.current_project_alias = None
        self.jira_project_name = None
        self.read_config_file()
        self.jira = JiraClient()
        self.current_tickets = []
        self.available_flows = [
            'commit',
            'merge',
            'cr',
            'release',
            'commit+jira',
            'move-tickets',
            'move-tickets-prod',
            'new-branch'
        ]

    def get_last_tag(self):
        p = subprocess.run(
            ["git", "describe", "--tags"],
            cwd=self.project_from_directory,
            capture_output=True,
            universal_newlines=True
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

    def run_shell_command(self, command):
        if isinstance(command, list):
            pass
        else:
            command = command.split(' ')
        print(' '.join(command))
        p = subprocess.run(
            command,
            cwd=self.project_from_directory,
            capture_output=True,
            universal_newlines=True,
        )
        if p.returncode != 0:
            return p.stderr.strip()

        else:
            return p.stdout.strip()

    def get_list_modified_files(self):
        string_list = self.run_shell_command('git diff --name-status | cut -f2')
        return string_list.splitlines()

    def read_config_file(self):
        file_path = os.path.dirname(__file__)
        with open('{0}/config.json'.format(file_path)) as json_file:
            self.config = json.load(json_file)

        self.projects = list(map(lambda x: x['name'], self.config['projects']))

    def get_all_local_branches(self):
        output = self.run_shell_command('git branch --all')
        tickets = re.findall(
            'issue/(' + self.jira_project_name + '-[0-9_]+)',
            output
        )
        return list(set(tickets))

    def fetch_remote_branch(self, branch_name):
        output = self.run_shell_command('git fetch')
        print(output)
        output = self.run_shell_command(f'git branch -D {branch_name}')
        print(output)
        output = self.run_shell_command(f'git checkout -b {branch_name} origin/{branch_name}')
        print(output)

        return True

    def rebase_develop(self):
        output = self.run_shell_command('git rebase develop')
        print(output)
        return True

    def merge_to_develop(self, branch_name):
        output = self.run_shell_command(f'git checkout develop')
        print(output)
        output = self.run_shell_command(f'git merge {branch_name}')
        print(output)
        return True

    def get_all_remote_branches(self):
        output = self.run_shell_command('git branch -r --all')
        tickets = re.findall(
            'issue/(' + self.jira_project_name + '-[0-9_]+)',
            output
        )
        return list(set(tickets))

    def chouse_option(self, message, choices):
        return enquiries.choose(message, choices)

    def get_ticket_number_from_raw_text(self, text):
        tickets = re.findall(
            f'{self.jira_project_name}-\d+',
            text
        )
        if len(tickets) > 0:
            return tickets[0]
        else:
            print("No ticket in text '{0}'".format(text))
            return None

    def get_ticket_numbers_from_raw_text(self, text):
        return re.findall(
            f'{self.jira_project_name}-\d+',
            text
        )

    def create_branch(self, from_branch='develop'):
        tickets = re.findall(
            '(' + self.jira_project_name + '-\d+)',
            input("Ticket: ")
        )
        self.run_shell_command(f'git checkout {from_branch}')
        if len(tickets) > 0:
            ticket = tickets[0]
            all_branches = set(self.get_all_local_branches() + self.get_all_remote_branches())
            if ticket in all_branches:
                print("ticket already has branch")
                for i in range(1, 20):
                    branch_ticket = f'{ticket}_{str(i)}'
                    if branch_ticket not in all_branches:
                        return self.run_shell_command('git checkout -b issue/' + branch_ticket)
            return self.run_shell_command('git checkout -b issue/' + ticket)
        else:
            print('Ticket not found')
            self.chouse_flow()

    def chouse_options(self, message, choices):
        pass
        questions = [inquirer.Checkbox(
            'Checkbox',
            message=message,
            choices=choices,
        )]

        return inquirer.prompt(questions)['Checkbox']

    def chouse_project(self):
        project_name = self.chouse_option("Select project: ", self.projects)
        project = next(filter(lambda item: item['name'] == project_name, self.config['projects']), None)
        self.load_project(project)

    def chouse_flow(self):
        self.current_flow = self.chouse_option("Select flow: ", self.available_flows)
        self.handle_flow()

    def handle_flow(self):
        message = ''
        flow = self.current_flow
        if flow == 'new-branch':
            message = self.create_branch('develop')
        if flow == 'commit+jira':
            message = self.commit()
            self.push_current_branch()
            link_to_remote_branch = self.render_git_branch_remote_link()
            for ticket in self.current_tickets:
                self.jira.set_status(ticket, 'WAIT_FOR_STAGE')
                self.jira.create_comment(ticket, commit=link_to_remote_branch)

        if flow == 'commit':
            message = self.commit()
            self.push_current_branch()

        if flow == 'merge':
            message = self.merge()
            self.push_current_branch()

        if flow == 'move-tickets':
            tickets = list(self.get_ticket_numbers_from_raw_text(input('Enter tickets numbers:')))
            for ticket in tickets:
                self.jira.set_status(ticket, 'ON_STAGE')
                self.jira.set_assignee(ticket)
            print(tickets)
        if flow == 'cr':
            response = self.jira.get_tickets_in_code_review(self.jira_project_name)
            json_response = json.loads(response.text)
            issues = list(map(lambda issue: issue['key'], json_response['issues']))
            for issue in issues:
                commit_data = self.jira.get_last_link(issue)
                commit_link = commit_data['url']
                author = commit_data['authorName']
                print(f'Commit link: {commit_link} by {author}')
                if commit_link:
                    branch_name = self.parse_branch_name(commit_link)
                    print(f'Branch name: {branch_name}')
                    if branch_name:
                        webbrowser.open_new_tab(commit_link)
                        answer = self.chouse_option(
                            f'Review issue {issue}, branch {branch_name}, Approve or not',
                            ['Approve+Merge', 'Approve', 'Decline']
                        )
                        print(answer)
                        if answer == 'Approve+Merge':
                            self.fetch_remote_branch(branch_name)
                            self.rebase_develop()
                            self.merge_to_develop(branch_name)
                        if answer == 'Decline':
                            comment = input(f'Comment to @{author}')
                            self.jira.set_status(issue, 'TO_DO')
                            self.jira.set_assignee(issue, commit_data['accountId'])
                            self.jira.create_comment(issue, mention={
                                'accountId': commit_data['accountId'],
                                'author': commit_data['author'],
                                'comment': f'Please, {comment}',
                            })
                        if answer == 'Approve':
                            self.jira.set_status(issue, 'WAIT_FOR_STAGE')
                            self.jira.create_comment(issue, comment='Code review approved')

                        break

        if flow == 'move-tickets-prod':
            tickets = list(self.get_ticket_numbers_from_raw_text(input('Enter tickets numbers:')))
            for ticket in tickets:
                self.jira.set_status(ticket, 'ON_PROD')
                self.jira.set_assignee(ticket)
            print(tickets)

        if flow == 'release':
            self.run_shell_command('git checkout master')
            self.run_shell_command('git merge develop --no-ff')
            self.run_shell_command('npm run release')
            self.run_shell_command('git push --follow-tags origin master')
            releaser = Releaser(self.frontend_project, self.backend_project, self.jira_project_name)
            releaser.update_frontend_package()

        print(message)

    def parse_branch_name(self, link):
        regex = r"inventcorp\/(.+)\/tree\/(.*)"
        matches = re.finditer(regex, link, re.MULTILINE)
        for matchNum, match in enumerate(matches, start=1):
            # if git branch matches current project
            if match.group(1) == self.frontend_project:
                return match.group(2)
        return False

    def merge(self, branch='develop'):
        current_branch = self.get_current_branch()
        self.run_shell_command(f'git checkout {branch}')
        return self.run_shell_command(f'git merge {current_branch}')

    def load_project(self, project):
        self.jira_project_name = project['jira']['project-name']
        self.current_project_alias = project['jira']['project-name']
        self.frontend_project = project['frontend']['project-name']
        self.backend_project = project['backend']['project-name']

    def commit(self):
        tickets = [self.get_ticket_number_from_raw_text(self.get_current_branch())]
        message = input(f'Commit message for ({", ".join(tickets)}):').strip()
        extra_tickets = input("Any extra tickets?")
        if len(extra_tickets):
            tickets_from_message = self.get_ticket_numbers_from_raw_text(extra_tickets)
            tickets = tickets_from_message + tickets

        # unique
        tickets = set(tickets)
        self.current_tickets = tickets
        if len(message) == 0:
            print('message is required')
            self.commit()
        else:
            self.run_shell_command('git add .')

            return self.run_shell_command(
                [
                    'git',
                    'commit',
                    '-m',
                    f'{message} ({", ".join(tickets).strip()})'
                ]
            )

    def render_git_branch_remote_link(self):
        project_git_alias = self.run_shell_command('pwd').split('/').pop()
        return f'https://github.com/inventcorp/{project_git_alias}/tree/{self.get_current_branch()}'

    def push_current_branch(self):
        return self.run_shell_command(f'git push -f origin {self.get_current_branch()}')


if __name__ == '__main__':
    git = Git()
    git.chouse_project()
    # git.get_all_local_branches()
    git.chouse_flow()
    # print(git.current_flow)
