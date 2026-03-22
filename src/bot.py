import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.voice_states = True
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

async def start_bot(token: str):
    async def play_audio_active_vc(file_path: str):
        cog = bot.get_cog("QuizCog")
        if cog:
            for vc in bot.voice_clients:
                await cog._ensure_speaker(vc)
                if not vc.is_playing():
                    vc.play(discord.FFmpegPCMAudio(file_path))

    bot.play_audio_active_vc = play_audio_active_vc
    await bot.load_extension("src.cogs.quiz")
    await bot.start(token)