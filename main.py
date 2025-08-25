from dotenv import load_dotenv
from asyncio import sleep, Lock
import asyncio
from discord import ui, ButtonStyle, Intents, Message, Client, app_commands, File, Interaction, TextStyle, User, Member, SelectOption
from typing import Optional, Union
import subprocess
from os import path, getenv, makedirs, remove
from logging.handlers import TimedRotatingFileHandler
import logging
from requests import get, Response
import signal
import sys

# -----------------------Initiate all global variables--------------------------


class BotClient(Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tree = app_commands.CommandTree(self)

    async def on_ready(self):
        await self.tree.sync()
        print(f"Finished setup. Logged in as {self.user}")
        self.loop.create_task(loop())


BOT: BotClient = BotClient(intents=Intents.all())

# Path constants
PROJECT_PATH: str = path.dirname(path.realpath(__file__))
DATA_PATH: str = path.join(PROJECT_PATH, "data")
LOG_PATH: str = path.join(DATA_PATH, "main.log")
PUBLIC_IP_PATH: str = path.join(DATA_PATH, "public_ip.txt")
TEMP_PATH: str = path.join(DATA_PATH, "temp")

# Environment constants
TOKEN: str = ""
WHITELIST: list[int] = []
SUPPORTED_SHELLS: list[str] = ["sh", "bash", "zsh", "powershell", "cmd"]
DEFAULT_CMD_TIMEOUT: float = 5.0
DEFAULT_SCROLL_AMOUNT: int = 5
DEFAULT_SHELL: str = "bash"
DEFAULT_SIGNAL: int
if sys.platform == "win32":
    DEFAULT_SIGNAL = signal.CTRL_C_EVENT
else:
    DEFAULT_SIGNAL = signal.SIGINT

# Global variables
CMD_TIMEOUT: float
SCROLL_AMOUNT: int

# Magic numbers
WINDOW_BASE_AUTO_SCROLL: int = -1
WINDOW_BASE_AUTO_SET: int = -2

# ---------------------------------Functions------------------------------------


def load_token() -> None:
    global TOKEN
    token: Optional[str] = getenv("TOKEN")
    if token is not None:
        TOKEN = token
        return
    logging.error("TOKEN environment variable not set. Aborting.")
    print("TOKEN environment variable not set. Aborting.")
    exit(1)


def load_whitelist() -> None:
    global WHITELIST
    env = getenv("WHITELIST", "")
    whitelist = []
    for id_str in env.split(","):
        try:
            id: int = int(id_str.strip())
            whitelist.append(id)
        except ValueError:
            continue
    WHITELIST = whitelist


def load_supported_shells() -> None:
    global SUPPORTED_SHELLS
    env: Optional[str] = getenv("SUPPORTED_SHELLS")
    if env is not None:
        SUPPORTED_SHELLS = [shell.strip() for shell in env.split(",")]


def load_default_cmd_timeout() -> None:
    global DEFAULT_CMD_TIMEOUT
    env: Optional[str] = getenv("DEFAULT_CMD_TIMEOUT")
    if env is not None:
        try:
            DEFAULT_CMD_TIMEOUT = float(env.strip())
        except ValueError:
            logging.error(f"Invalid DEFAULT_CMD_TIMEOUT value: {env}")


def load_default_scroll_amount() -> None:
    global DEFAULT_SCROLL_AMOUNT
    env: Optional[str] = getenv("DEFAULT_SCROLL_AMOUNT")
    if env is not None:
        try:
            DEFAULT_SCROLL_AMOUNT = int(env.strip())
        except ValueError:
            logging.error(f"Invalid DEFAULT_SCROLL_AMOUNT value: {env}")


def load_default_shell() -> None:
    global DEFAULT_SHELL
    env: Optional[str] = getenv("DEFAULT_SHELL")
    if env is not None:
        DEFAULT_SHELL = env.strip()


def load_environ():
    global TOKEN, WHITELIST, SUPPORTED_SHELLS, DEFAULT_CMD_TIMEOUT, DEFAULT_SCROLL_AMOUNT, DEFAULT_SHELL
    load_token()
    logging.info(f"Loaded TOKEN: {TOKEN}")
    load_whitelist()
    logging.info(f"Loaded WHITELIST: {WHITELIST}")
    load_supported_shells()
    logging.info(f"Loaded SUPPORTED_SHELLS: {SUPPORTED_SHELLS}")
    load_default_cmd_timeout()
    logging.info(f"Loaded DEFAULT_CMD_TIMEOUT: {DEFAULT_CMD_TIMEOUT}")
    load_default_scroll_amount()
    logging.info(f"Loaded DEFAULT_SCROLL_AMOUNT: {DEFAULT_SCROLL_AMOUNT}")
    load_default_shell()
    logging.info(f"Loaded DEFAULT_SHELL: {DEFAULT_SHELL}")


def is_user_allowed(user: Union[User, Member]) -> bool:
    return user.id in WHITELIST


def get_supported_signals() -> list[signal.Signals]:
    if sys.platform == "win32":
        return [signal.Signals.CTRL_C_EVENT, signal.Signals.CTRL_BREAK_EVENT]
    return [signal.Signals.SIGINT, signal.Signals.SIGTERM]  # Maybe other signals are also useful in a linux terminal


def get_signal_options(default: int = DEFAULT_SIGNAL) -> list[SelectOption]:
    options = []
    for sig in get_supported_signals():
        try:
            if isinstance(sig, int):
                sig = signal.Signals(sig)
            is_default = sig.value == default
            options.append(SelectOption(label=sig.name, value=str(sig.value), default=is_default))
        except Exception:
            pass
    return options


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


# ----------------------------------Events--------------------------------------


@BOT.event
async def on_message(message: Message):
    channel = message.channel
    command = message.content
    author = message.author
    if author.bot or (BOT.user is not None and author.id == BOT.user.id):
        return
    if not is_user_allowed(author):
        await channel.send("You are not authorized to use this bot.")
        logging.warning(f"Unauthorized access attempt by user {author} (ID: {author.id})")
        return
    await channel.send(f"Executing command: {command}")
    async with channel.typing():
        try:
            # Execute the command
            logging.info(f"Executing command sent by user {author.name} (ID: {author.id}): {command}")
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=CMD_TIMEOUT)
            # Build the output and send to the channel
            prefix: str = "```sh\n"
            suffix: str = "\n```"
            body = f"[RETURN_CODE={result.returncode}]"
            if result.stdout and len(result.stdout.strip()) > 0:
                body += f"\n[OUTPUT]\n{result.stdout}"
            if result.stderr and len(result.stderr.strip()) > 0:
                body += f"\n[ERRORS]\n{result.stderr}"
            if len(prefix + body + suffix) <= 2000:
                await channel.send(prefix + body + suffix)
                return
            # If the output is too large, send it as a file
            temp_file_path = path.join(TEMP_PATH, f"output_{message.id}.txt")
            with open(temp_file_path, "w") as f:
                f.write(body)
            await channel.send(file=File(temp_file_path))
            remove(temp_file_path)
        except Exception as e:
            logging.exception(e)
            await channel.send(f"An error occurred while executing the command: {e}")


@BOT.tree.command(name="init", description="Initialize the bot")
async def init(interaction: Interaction):
    if not is_user_allowed(interaction.user):
        await interaction.response.send_message("You are not authorized to use this command.", ephemeral=True)
        return
    await send_msg_to_user(interaction.user.id, "Bot has been initialized. You can now use this channel to send commands to the server.")
    await interaction.response.send_message("Bot has been initialized. Check your DMs to continue.", ephemeral=True)


class InteractiveShellView(ui.LayoutView):
    text = ui.TextDisplay(content="")
    row_1 = ui.ActionRow()
    row_2 = ui.ActionRow()
    row_3 = ui.ActionRow()

    def __init__(self, interaction: Interaction) -> None:
        super().__init__(timeout=None)
        self.log: str = ""
        self.log_lock: Lock = Lock()
        self.log_window_base: int = WINDOW_BASE_AUTO_SCROLL
        self.log_window_base_lock: Lock = Lock()
        self.interaction: Interaction = interaction
        self.process: Optional[asyncio.subprocess.Process] = None
        self.selected_signal: int = DEFAULT_SIGNAL

    async def start(self, shell: str = "cmd"):
        if shell in ["sh", "bash", "zsh"]:
            shell += " -i"
        self.process = await asyncio.create_subprocess_shell(
            shell,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        BOT.loop.create_task(self.interactive_session_loop_task())
        await self.render()

    async def count_log_lines(self) -> int:
        async with self.log_lock:
            return self.log.count("\n")

    async def set_log_window_base(self, value: int):
        async with self.log_window_base_lock:
            self.log_window_base = value

    async def set_auto_scroll(self):
        async with self.log_window_base_lock:
            self.log_window_base = WINDOW_BASE_AUTO_SCROLL

    async def build_log_message(self) -> str:
        async with self.log_window_base_lock:
            log_window_base = self.log_window_base
        MAX_CONTENT_SIZE = 4000
        prefix = "```sh\n"
        header = ""
        body = ""
        footer = ""
        suffix = "\n```"
        async with self.log_lock:
            body = self.log
        if body.strip() == "":
            return prefix + " " + suffix
        # Clean line endings
        lines = body.splitlines()
        for i in range(len(lines)):
            lines[i] = lines[i].rstrip() + "\n"
        body = "".join(lines)
        content = prefix + header + body + footer + suffix
        if len(content) <= MAX_CONTENT_SIZE:
            await self.set_auto_scroll()
            return content
        # Change to a window based system, by finding the highest window base (in lines) that shows the logs until the end.
        body = ""
        if log_window_base < 0:
            # Either auto-scroll or auto-find base
            header = "…\n"
            footer = ""
            for i in range(len(lines) - 1, -1, -1):
                free: int = MAX_CONTENT_SIZE - len(prefix + header + body + footer + suffix)
                if free >= len(lines[i]):
                    body = lines[i] + body
                else:
                    # Line (i) does not fit anymore
                    if log_window_base == WINDOW_BASE_AUTO_SET:
                        await self.set_log_window_base(i + 1)
                    break
        else:
            if log_window_base != 0:
                header = "…\n"
            for i in range(log_window_base, len(lines)):
                free: int = MAX_CONTENT_SIZE - len(prefix + header + body + footer + suffix)
                if free == len(lines[i]):
                    body += lines[i]
                    footer = ""
                    await self.set_auto_scroll()
                    break
                elif free > len(lines[i]):
                    body += lines[i]
                elif free < len(lines[i]):
                    print(f"free: {free}, adding: {len(lines[i][:free-1])} ({lines[i][:free-1]})")
                    body += lines[i][: free - 1]
                    footer = "…"
                    break
        print(len(prefix + header + body + footer + suffix))
        return prefix + header + body + footer + suffix

    async def render_export(self, interaction: Interaction, msg: Optional[str] = None):
        async with self.log_lock:
            full_log = self.log
        temp_file_path = path.join(TEMP_PATH, f"interactive_log_{interaction.id}.txt")
        with open(temp_file_path, "w", encoding="utf-8", errors="ignore") as f:
            f.write(full_log)
        if msg:
            await interaction.response.send_message(content=msg, file=File(temp_file_path))
        else:
            await interaction.response.send_message(file=File(temp_file_path))
        remove(temp_file_path)

    async def append_log(self, *args):
        async with self.log_lock:
            self.log += "".join(args)

    async def render(self):
        self.text.content = await self.build_log_message()
        await self.interaction.edit_original_response(view=self)

    @row_1.button(label="↑", style=ButtonStyle.secondary)
    async def scroll_up_button(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        async with self.log_window_base_lock:
            if self.log_window_base == WINDOW_BASE_AUTO_SCROLL:
                self.log_window_base = WINDOW_BASE_AUTO_SET
            self.log_window_base = max(0, self.log_window_base - SCROLL_AMOUNT)
        await self.render()

    @row_1.button(label="↓", style=ButtonStyle.secondary)
    async def scroll_down_button(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        async with self.log_window_base_lock:
            if self.log_window_base == WINDOW_BASE_AUTO_SCROLL:
                return
            self.log_window_base = min(await self.count_log_lines() - 1, self.log_window_base + SCROLL_AMOUNT)
        await self.render()

    @row_1.button(label="Export Log", style=ButtonStyle.secondary)
    async def export_button(self, interaction: Interaction, button: ui.Button):
        try:
            await self.render_export(interaction)
        except Exception as e:
            logging.exception(e)
            await interaction.response.send_message("Failed to export log.", ephemeral=True)

    @row_2.select(placeholder="Select a signal...", min_values=1, max_values=1, options=get_signal_options())
    async def signal_select(self, interaction: Interaction, select: ui.Select):
        await interaction.response.defer()
        self.selected_signal = int(select.values[0])
        select.options = get_signal_options(default=self.selected_signal)

    @row_3.button(id=100, label="Send Signal", style=ButtonStyle.danger)
    async def send_signal_button(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        if self.process and self.selected_signal is not None:
            try:
                self.process.send_signal(self.selected_signal)
                logging.info(f"Successfully sent signal: {self.selected_signal}")
            except ProcessLookupError:
                logging.warning("Process not found.")
            except:
                logging.warning(f"Unable to send signal: {self.selected_signal}")

    @row_3.button(id=101, label="Stop", style=ButtonStyle.danger)
    async def stop_button(self, interaction: Interaction, button: ui.Button):
        view_ref = self
        try:
            if view_ref.process and view_ref.process.returncode is None:
                try:
                    view_ref.process.terminate()
                except ProcessLookupError:
                    pass
            await self.set_auto_scroll()
            for i in range(100, 103):
                item = view_ref.find_item(i)
                if item:
                    view_ref.remove_item(item)
            await self.render()
            await self.render_export(interaction, msg="Session ended. Here is the full log:")
        except Exception as e:
            logging.exception(e)

    @row_3.button(id=102, label="Send Command", style=ButtonStyle.primary)
    async def send_command_button(self, interaction: Interaction, button: ui.Button):
        view_ref = self

        class CommandModal(ui.Modal, title="Send Command"):
            command = ui.TextInput(
                label="Command",
                style=TextStyle.short,
                required=True,
                placeholder="Enter your command here...",
            )

            async def on_submit(self, modal_interaction: Interaction):
                cmd = str(self.command.value)
                newline = "\r\n" if sys.platform == "win32" else "\n"
                line = (cmd + newline).encode()
                try:
                    if view_ref.process and view_ref.process.stdin:
                        view_ref.process.stdin.write(line)
                        await view_ref.process.stdin.drain()
                except Exception as e:
                    logging.exception(e)
                await modal_interaction.response.defer()

        await interaction.response.send_modal(CommandModal())

    async def interactive_session_loop_task(self):
        if not self.process:
            return
        while True:
            if self.process.returncode is not None:
                break
            got = False
            try:
                if self.process.stdout:
                    data = await asyncio.wait_for(self.process.stdout.read(4096), timeout=0.2)
                    if data:
                        await self.append_log(data.decode(errors="ignore"))
                        got = True
            except asyncio.TimeoutError:
                pass
            except Exception as e:
                logging.exception(e)
            if got:
                try:
                    await self.render()
                except Exception as e:
                    logging.exception(e)
            await asyncio.sleep(0.5)


# Add describe to set argument 1 as shell to use
@BOT.tree.command(name="shell", description="Start an interactive shell session")
@app_commands.describe(shell="The shell to use for the interactive session")
async def shell_session(interaction: Interaction, shell: str = DEFAULT_SHELL):
    author = interaction.user
    if not is_user_allowed(author):
        await interaction.response.send_message("You are not authorized to use this command.", ephemeral=True)
        logging.warning(f"Unauthorized access attempt by user {author} (ID: {author.id})")
        return
    shell = shell.strip() if shell else DEFAULT_SHELL
    if shell not in SUPPORTED_SHELLS:
        await interaction.response.send_message("Unsupported shell.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    view = InteractiveShellView(interaction)
    await view.start(shell=shell)


@BOT.tree.command(name="ping", description="Check if the bot is responsive")
async def ping(interaction: Interaction):
    author = interaction.user
    if not is_user_allowed(author):
        await interaction.response.send_message("You are not authorized to use this command.", ephemeral=True)
        logging.warning(f"Unauthorized access attempt by user {author} (ID: {author.id})")
        return
    await interaction.response.send_message("Pong!", ephemeral=True)


@BOT.tree.command(name="timeout", description="Modify the command timeout")
async def timeout(interaction: Interaction, timeout: Optional[float] = None):
    global CMD_TIMEOUT
    author = interaction.user
    if not is_user_allowed(author):
        await interaction.response.send_message("You are not authorized to use this command.", ephemeral=True)
        logging.warning(f"Unauthorized access attempt by user {author} (ID: {author.id})")
        return
    if timeout == None:
        CMD_TIMEOUT = DEFAULT_CMD_TIMEOUT
        await interaction.response.send_message(f"Command timeout reset to the default ({DEFAULT_CMD_TIMEOUT} seconds).", ephemeral=True)
    else:
        CMD_TIMEOUT = timeout
        await interaction.response.send_message(f"Command timeout set to {timeout} seconds.", ephemeral=True)


@BOT.tree.command(name="scroll", description="Modify the scroll amount for interactive sessions")
async def scroll(interaction: Interaction, amount: Optional[int] = None):
    global SCROLL_AMOUNT
    author = interaction.user
    if not is_user_allowed(author):
        await interaction.response.send_message("You are not authorized to use this command.", ephemeral=True)
        logging.warning(f"Unauthorized access attempt by user {author} (ID: {author.id})")
        return
    if amount is None:
        SCROLL_AMOUNT = DEFAULT_SCROLL_AMOUNT
        await interaction.response.send_message(f"Scroll amount reset to the default ({DEFAULT_SCROLL_AMOUNT}).", ephemeral=True)
    else:
        SCROLL_AMOUNT = amount
        await interaction.response.send_message(f"Scroll amount set to {amount}.", ephemeral=True)


# -----------------------------Run and Connect Bot------------------------------

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
    load_environ()
    try:
        BOT.run(TOKEN)
    except Exception as e:
        logging.exception(e)
        print("[ERROR] An error occurred while running the bot:")
        print(e)
        exit(1)
