from dotenv import load_dotenv
from asyncio import sleep
from discord import (
    Intents,
    Message,
    Client,
    app_commands,
    File,
    Interaction
)
import subprocess
from os import path, getenv, makedirs, remove
from logging.handlers import TimedRotatingFileHandler
import logging
from requests import get, Response

#-----------------------Initiate all global variables--------------------------

class BotClient(Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tree = app_commands.CommandTree(self)

    async def on_ready(self):
        logging.info(f"Finished syncing commands: {await self.tree.sync()}")
        print(f"Finished setup. Logged in as {self.user}")
        self.loop.create_task(loop())

PROJECT_PATH: str  = path.dirname(path.realpath(__file__))
DATA_PATH: str  = path.join(PROJECT_PATH, "data")
LOG_PATH: str  = path.join(DATA_PATH, "main.log")
PUBLIC_IP_PATH: str = path.join(DATA_PATH, "public_ip.txt")
TEMP_PATH: str = path.join(DATA_PATH, "temp")

BOT: BotClient = BotClient(intents=Intents.all())
WHITELIST: list

#---------------------------------Functions------------------------------------

def load_whitelist() -> list:
    whitelist_env = str(getenv("WHITELIST", ""))
    whitelist = []
    for id_str in whitelist_env.split(","):
        try:
            id: int = int(id_str.strip())
            whitelist.append(id)
        except ValueError:
            continue
    logging.info(f"Loaded whitelist: {whitelist}")
    return whitelist

def is_user_allowed(user) -> bool:
    return user.id in WHITELIST

def getPublicIP() -> str:
    query_url = "https://api.ipify.org/?format=json"
    response: Response = get(query_url)
    if response.status_code != 200:
        logging.error(f"Failed to get public IP address. Status code: {response.status_code}")
        return ""
    ip = response.json()["ip"]
    logging.info(f"Current public IP: {ip}")
    return ip

async def send_msg_to_user(user_id: int, msg: str, embed=None):
    user = BOT.get_user(user_id)
    if user != None:
        dm_channel = user.dm_channel
        if dm_channel == None:
            dm_channel = await user.create_dm()
        if embed == None:
            await dm_channel.send(msg)
        else:
            await dm_channel.send(msg, embed=embed)

async def send_msg_to_all_users(msg: str, embed=None):
    for user_id in WHITELIST:
        await send_msg_to_user(user_id, msg, embed=embed)

async def loop():
    while True:
        try:
            current_ip: str = getPublicIP()
            stored_ip: str = ""
            if path.exists(PUBLIC_IP_PATH):
                with open(PUBLIC_IP_PATH, "r") as f:
                    stored_ip = f.read().strip()
            else:
                stored_ip = ""
            if current_ip == "":
                msg: str = f"Public IP address could not be retrieved. Last known Public IP: {stored_ip}"
                logging.warning(msg)
                await send_msg_to_all_users(msg)
            elif current_ip != stored_ip:
                msg: str = f"Public IP address has changed from {stored_ip} to {current_ip}"
                logging.info(msg)
                with open(PUBLIC_IP_PATH, "w") as f:
                    f.write(current_ip)
                await send_msg_to_all_users(msg)
        except Exception as e:
            logging.exception(e)
        await sleep(60 * 60)  # Check every hour

#----------------------------------Events--------------------------------------

@BOT.event
async def on_message(message: Message):
    channel = message.channel
    command = message.content
    author = message.author
    if author.bot or author.id == BOT.user.id:
        return
    await channel.send(f"Executing command: {command}")
    # Set typing status
    async with channel.typing():
        try:
            if not is_user_allowed(author):
                await channel.send("You are not authorized to use this bot.")
                logging.warning(f"Unauthorized access attempt by user {author} (ID: {author.id})")
                return
            # Execute the command
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            output = f"[RETURN_CODE={result.returncode}]"
            if result.stdout and len(result.stdout.strip()) > 0:
                output += f"\n[OUTPUT]\n{result.stdout}"
            if result.stderr and len(result.stderr.strip()) > 0:
                output += f"\n[ERRORS]\n{result.stderr}"
            # Send the output back to the user
            if len(output) > 1900:
                temp_file_path = path.join(TEMP_PATH, f"output_{message.id}.txt")
                with open(temp_file_path, "w") as f:
                    f.write(output)
                await channel.send(file=File(temp_file_path))
                remove(temp_file_path)
            else:
                await channel.send(f"```\n{output}\n```")
        except Exception as e:
            logging.exception(e)
            await channel.send(f"An error occurred while executing the command: {e}")

@BOT.tree.command(name="init", description="Initialize the bot")
async def init_bot(interaction: Interaction):
    if not is_user_allowed(interaction.user):
        await interaction.response.send_message("You are not authorized to use this command.", ephemeral=True)
        return
    await send_msg_to_user(interaction.user.id, "Bot has been initialized. You can now use this channel to send commands to the server.")
    await interaction.response.send_message("Bot has been initialized. Check your DMs to continue.", ephemeral=True)

#-----------------------------Run and Connect Bot------------------------------

if __name__ == "__main__":
    makedirs(DATA_PATH, exist_ok=True)
    makedirs(TEMP_PATH, exist_ok=True)
    logging_handler = TimedRotatingFileHandler(filename=LOG_PATH, when="D", interval=30)
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%d-%b-%y %H:%M:%S",
        level=logging.INFO,
        handlers=[logging_handler],
    )

    load_dotenv()
    WHITELIST = load_whitelist()
    token = getenv('TOKEN')
    if token == None:
        print("[ERROR] Please provide a token in the .env file.")
        exit(1)
    try:
        BOT.run(token)
    except Exception as e:
        print("[ERROR] An error occurred while running the bot:")
        print(e)
        logging.exception(e)
        exit(1)