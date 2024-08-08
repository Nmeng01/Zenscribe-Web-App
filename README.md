# Zenscribe-Web-App
Front-facing application utilizing original Zenscribe script

## How to run locally without using git commands

- [Install VS Code](https://code.visualstudio.com/download)
- Ensure you have installed python
- [Install pipenv](https://pypi.org/project/pipenv/)
- Download a zip file of this repository by clicking the green Code button above
- Unzip this file and place the project somewhere in your file explorer that is easily accessible
- Open the project in VS Code and create a new file called .env. Correspond with me directly about what to put in this file. Make sure to save it.
- Once .env file is set up, open up your Command Prompt or use the one in VS Code and navigate into the project by entering cd {path}/{to}/Zenscribe-Web-App
- Make sure that you have navigated to the right project in the Command Prompt and open a virtual environment by entering pipenv shell. 
- Install all dependencies by entering pipenv install
- Run the project by entering python3 webApp/app.py
- You will see a message in the Command Prompt now telling you the address where you can access the app. Paste this into your browser.
