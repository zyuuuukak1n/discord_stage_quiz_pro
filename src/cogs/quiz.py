import discord
from discord.ext import commands
import asyncio
import traceback
from sqlalchemy.orm import Session
from ..database import SessionLocal
from ..models import GameState, GameStateEnum, User, ProtectedUser
from ..websocket_manager import manager

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

    @commands.hybrid_command(name="protect", description="指定したメンバーをオーディエンス一斉降格から保護します")
    async def protect(self, ctx: commands.Context, member: discord.Member):
        from ..models import ProtectedUser
        from ..database import SessionLocal
        
        await ctx.defer()
        db = SessionLocal()
        try:
            existing = db.query(ProtectedUser).filter(ProtectedUser.discord_user_id == str(member.id)).first()
            if existing:
                await ctx.send(f"⚠️ {member.display_name} は既に保護リストに登録されています。")
            else:
                new_protected = ProtectedUser(discord_user_id=str(member.id))
                db.add(new_protected)
                db.commit()
                await ctx.send(f"🛡️ {member.display_name} を保護リストに登録しました。（一斉降格の対象外になります）")
        except Exception as e:
            await ctx.send(f"処理中にエラーが発生しました: {e}")
        finally:
            db.close()

    @commands.hybrid_command(name="unprotect", description="指定したメンバーを保護リストから解除します")
    async def unprotect(self, ctx: commands.Context, member: discord.Member):
        from ..models import ProtectedUser
        from ..database import SessionLocal
        
        await ctx.defer()
        db = SessionLocal()
        try:
            existing = db.query(ProtectedUser).filter(ProtectedUser.discord_user_id == str(member.id)).first()
            if not existing:
                await ctx.send(f"⚠️ {member.display_name} は保護リストに登録されていません。")
            else:
                db.delete(existing)
                db.commit()
                await ctx.send(f"🗑️ {member.display_name} を保護リストから解除しました。")
        except Exception as e:
            await ctx.send(f"処理中にエラーが発生しました: {e}")
        finally:
            db.close()

    @commands.hybrid_command(name="protect_list", description="現在保護リストに登録されているユーザー一覧を表示します")
    async def protect_list(self, ctx: commands.Context):
        from ..models import ProtectedUser
        from ..database import SessionLocal
        
        await ctx.defer()
        db = SessionLocal()
        try:
            protected = db.query(ProtectedUser).all()
            if not protected:
                await ctx.send("現在保護されているユーザーはいません。")
            else:
                mentions = []
                for p in protected:
                    user = ctx.guild.get_member(int(p.discord_user_id)) if ctx.guild else None
                    if user:
                        mentions.append(user.mention)
                    else:
                        mentions.append(f"<@{p.discord_user_id}>")
                await ctx.send(f"🛡️ **保護リスト一覧**:\n" + "\n".join(mentions))
        except Exception as e:
            await ctx.send(f"処理中にエラーが発生しました: {e}")
        finally:
            db.close()

async def setup(bot):
    await bot.add_cog(QuizCog(bot))
