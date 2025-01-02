from typing import Final
import os
from dotenv import load_dotenv
from discord import Intents, Client, Message
from responses import get_response

#Load the Token From somewhere SAFE
load_dotenv()
TOKEN: Final[str] = os.getenv('DISCORD_TOKEN')

#BOT SETUP

Intents: Intents = Intents.default()
Intents.message_content = True # NOQA
client: Client = Client(intents=Intents)

# Message Functionaloty

async def send_message(message: Message, user_message: str) -> None:
    if not user_message:
        print('(message was empty because intents were not enebled probably)')
        return
    
    if is_private := user_message[0] == '?'


