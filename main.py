import os
import asyncio
import aiohttp
import discord

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
MODEL = os.getenv("MODEL", "google/gemini-2.0-flash-001")

with open("contexto_maestro.txt", "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


@client.event
async def on_ready():
    print(f"DLAsistente conectado como {client.user} en el canal {CHANNEL_ID}")


@client.event
async def on_message(message):
    if message.author.bot:
        return
    if message.channel.id != CHANNEL_ID:
        return

    async with message.channel.typing():
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    OPENROUTER_URL,
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": MODEL,
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": message.content},
                        ],
                    },
                ) as resp:
                    data = await resp.json()
                    reply = data["choices"][0]["message"]["content"]
        except Exception as e:
            reply = f"Error al procesar el mensaje: {e}"

    if len(reply) > 2000:
        reply = reply[:1997] + "..."

    await message.reply(reply, mention_author=False)


client.run(DISCORD_TOKEN)
