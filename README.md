# Syscordmin - A Discord Bot for Sysadmins

A discord bot written in python that provides a set of configured whitelisted users (sysadmins) the ability to execute commands on their servers over Discord.

# Features

- Single command execution
    - Return code, stdout and stderr as feedback
- Interactive shell sessions
    - Persistent sessions with history
    - Commands executed through stdin of a shell process, allowing for commands that require user interaction.
    - Ability to send signals such as SIGINT (Ctrl+C) and SIGTERM (termination signal).
- Setting customization through bot commands (e.g. `/timeout <n>` and `/scroll <n>`).

## Initial Setup

1. Create a virtual environment with `python -m venv .venv`
2. Activate the virtual environment:
    - On Windows, run `.venv\Scripts\activate`
    - On Linux, run `source .venv/bin/activate`
3. Run `pip install -r requirements.txt` to install the required packages in the virtual environment.
4. Create a `.env` file in the root directory of the project by copying the provided `.env.example` file.
5. Configure the `.env` file with your bot's token and any other necessary settings.
6. Run `python main.py` to start the bot.

## Systemd Service Setup (Linux)

To set up Syscordmin as a systemd service, create a service file for it:

1. Create a new service file in the systemd directory: `sudo vim /etc/systemd/system/syscordmin.service`

2. Add the following content to the service file:

    ```txt
    [Unit]
    Description=Syscordmin Discord Bot
    After=network-online.target
    Wants=network-online.target
    StartLimitIntervalSec=0

    [Service]
    User=<user_to_run_as>
    WorkingDirectory=</path/to/your/project>
    ExecStart=</path/to/your/project>/.venv/bin/python </path/to/your/project>/main.py
    Restart=on-failure
    RestartSec=60

    [Install]
    WantedBy=multi-user.target
    ```

3. Replace `<user_to_run_as>` with the username of the user to run the bot as. (The commands sent to the bot will be executed as this user.)
4. Replace `</path/to/your/project>` with the absolute path to your project directory.

5. Save and exit the editor.

6. Reload the systemd daemon to recognize the new service: `sudo systemctl daemon-reload`

7. Enable the service to start on boot: `sudo systemctl enable syscordmin`

8. Start the service: `sudo systemctl start syscordmin`

## ⚠️ Security Warning

The functionality of this bot can also be known as a "reverse shell". This means that it can be used to execute commands on the host machine where the bot is running as a client of the Discord servers, bypassing most port forwarding and firewall restrictions.
As such, it is crucial to ensure that only trusted users have access to the bot and its commands.

Additionally, if you identify a compiled version of this project circulating, it is highly likely being used for malicious purposes.
