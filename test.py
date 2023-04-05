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


from main import Wizard

wizard = Wizard()

wizard.choose_project()
wizard.choose_workflow()
print(wizard.current_workflow)
print(wizard.tickets_to_review)

