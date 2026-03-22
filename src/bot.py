import os
import discord
from discord.ext import commands
import asyncio
import traceback
from sqlalchemy.orm import Session
from .database import SessionLocal
from .models import GameState, GameStateEnum, User
from .main import manager

intents = discord.Intents.default()
intents.voice_states = True
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

class QuizCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _ensure_speaker(self, voice_client):
        if voice_client and isinstance(voice_client.channel, discord.StageChannel):
            if voice_client.channel.guild.me.voice and voice_client.channel.guild.me.voice.suppress:
                try:
                    await voice_client.channel.guild.me.edit(suppress=False)
                    await asyncio.sleep(0.5)
                except Exception as e:
                    print(f"Failed to unsuppress bot: {e}", flush=True)

    async def play_audio(self, channel, file_path: str):
        voice_client = discord.utils.get(self.bot.voice_clients, guild=channel.guild)
        if not voice_client:
            voice_client = await channel.connect()
        await self._ensure_speaker(voice_client)
        if not voice_client.is_playing():
            voice_client.play(discord.FFmpegPCMAudio(file_path))

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"\n========== BOT READY (COG LOADED) ==========", flush=True)
        print(f"Logged in as {self.bot.user}", flush=True)
        try:
            synced = await self.bot.tree.sync()
            print(f"Synced {len(synced)} command(s)\n", flush=True)
        except Exception as e:
            print(f"Sync error: {e}", flush=True)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member.bot:
            return

        try:
            b_req = before.requested_to_speak_at
            a_req = after.requested_to_speak_at
            
            print(f"!!! [RAW EVENT] User: {member.display_name} | Req: {b_req} -> {a_req}", flush=True)

            is_stage = getattr(after.channel, "type", None) == discord.ChannelType.stage_voice
            raised_hand_now = (b_req is None and a_req is not None)

            if is_stage and raised_hand_now:
                print(f"[ACTION] ✋ Hand raise detected for {member.display_name}!", flush=True)
                
                # スレッドを使わず、直接同一ループ内で処理する（切断エラーを完全防止）
                db: Session = SessionLocal()
                try:
                    game_state = db.query(GameState).filter(GameState.id == 1).first()
                    current_status_val = getattr(game_state.current_state, 'value', game_state.current_state) if game_state else None
                    print(f"[DB] Current status: {current_status_val}", flush=True)

                    if current_status_val == "asking":
                        game_state.current_state = GameStateEnum.paused
                        
                        quiz_user = db.query(User).filter(User.discord_user_id == str(member.id)).first()
                        if not quiz_user:
                            quiz_user = User(discord_user_id=str(member.id), display_name=member.display_name)
                            db.add(quiz_user)
                            db.commit()
                            db.refresh(quiz_user)

                        game_state.answering_user_id = quiz_user.id
                        
                        # ★重要: DBセッションが閉じる前に必要な値を変数に退避させる
                        user_id = quiz_user.id
                        display_name = quiz_user.display_name
                        db.commit()

                        print(f"[BROADCAST] Sending PAUSE_QUESTION...", flush=True)
                        await manager.broadcast_state({
                            "action": "PAUSE_QUESTION",
                            "user_id": user_id,
                            "display_name": display_name
                        })
                        
                        print(f"[DISCORD API] Unsuppressing {display_name}...", flush=True)
                        await member.edit(suppress=False)
                        
                        if member.voice and member.voice.channel:
                            print(f"[AUDIO] Playing pressed.mp3...", flush=True)
                            await self.play_audio(member.voice.channel, "audio/pressed.mp3")

                        print(f"[SUCCESS] ✨ All actions completed for {display_name}!", flush=True)

                    else:
                        print(f"[IGNORED] Status was {current_status_val}, ignoring hand raise.", flush=True)
                except Exception as inner_e:
                    print(f"[CRITICAL LOGIC ERROR] {inner_e}", flush=True)
                    traceback.print_exc()
                finally:
                    db.close()

        except Exception as e:
            print(f"[EVENT ERROR] {e}", flush=True)
            traceback.print_exc()

    @commands.hybrid_command(name="join", description="ステージに参加")
    async def join(self, ctx: commands.Context):
        await ctx.defer()
        if not ctx.author.voice:
            await ctx.send("VCにいません。")
            return
        channel = ctx.author.voice.channel
        voice_client = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        if voice_client and voice_client.is_connected():
            await voice_client.move_to(channel)
        else:
            voice_client = await channel.connect()
        await self._ensure_speaker(voice_client)
        await ctx.send(f"{channel.name} に参加しました！")

    @commands.hybrid_command(name="leave", description="ステージから退出")
    async def leave(self, ctx: commands.Context):
        await ctx.defer()
        voice_client = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        if voice_client:
            await voice_client.disconnect()
            await ctx.send("退出しました。")

    @commands.hybrid_command(name="check_stage", description="【デバッグ用】ステージの挙手状態を強制確認")
    async def check_stage(self, ctx: commands.Context):
        await ctx.defer()
        if not ctx.author.voice:
            await ctx.send("VCにいません。")
            return
        channel = ctx.author.voice.channel
        msg = f"**{channel.name} の状態**\n"
        for m in channel.members:
            req = "✋挙手あり" if getattr(m.voice, "requested_to_speak_at", None) else "挙手なし"
            msg += f"- {m.display_name}: {req}\n"
        await ctx.send(msg)

async def start_bot(token: str):
    async def play_audio_active_vc(file_path: str):
        cog = bot.get_cog("QuizCog")
        if cog:
            for vc in bot.voice_clients:
                await cog._ensure_speaker(vc)
                if not vc.is_playing():
                    vc.play(discord.FFmpegPCMAudio(file_path))

    bot.play_audio_active_vc = play_audio_active_vc
    await bot.add_cog(QuizCog(bot))
    await bot.start(token)