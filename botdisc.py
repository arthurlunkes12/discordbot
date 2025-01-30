import discord
from discord.ext import commands
import yt_dlp
import asyncio
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import os
from dotenv import load_dotenv

load_dotenv()

SPOTIPY_CLIENT_ID = os.getenv("SPOTIPYID")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPYSECRET")
sp = spotipy.Spotify(
    auth_manager=SpotifyClientCredentials(
            client_id=SPOTIPY_CLIENT_ID,
            client_secret=SPOTIPY_CLIENT_SECRET
                            )
                        )

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="*", intents=intents)

queue = []
bot.is_playing = False

# Configuração do FFmpeg para evitar lag
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -analyzeduration 1000000 -probesize 1000000',
    'options': '-vn -buffer_size 512k'
}


@bot.command()
async def ping(ctx):
    await ctx.send("🏓 Pong!")


# 🔍 Buscar músicas no YouTube
async def search_youtube(query):
    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'default_search': 'ytsearch1:',
        'cookiefile': 'cookies.txt'  # 🔥 Usa cookies para evitar bloqueios
    }
    loop = asyncio.get_running_loop()
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = await loop.run_in_executor(
                None, lambda: ydl.extract_info(
                    query, download=False)
                    )
            if 'entries' in info and len(info['entries']) > 0:
                entry = info['entries'][0]
                return entry['url'], entry['title']
        except Exception as e:
            print(f"Erro ao buscar no YouTube: {e}")
    return None, None


# 🔍 Buscar músicas do Spotify e converter para YouTube
async def get_spotify_tracks(url, ctx):
    """Busca músicas do Spotify e impede que sejam adicionadas após *clear"""
    track_names = []
    try:
        if "track" in url:
            track = sp.track(url)
            track_names.append(
                f"{track['name']} {track['artists'][0]['name']}"
                )
        elif "album" in url:
            album = sp.album_tracks(url)
            track_names = [
                f"{track['name']} {track['artists'][0][
                    'name'
                    ]}" for track in album['items']
                ]
        elif "playlist" in url:
            playlist = sp.playlist_tracks(url)
            track_names = [
                f"{track['track']['name']} {track['track'][
                    'artists'
                    ][0]['name']}" for track in playlist['items']
                ]

        # 🔥 Busca a primeira música e toca imediatamente
        first_track_url, first_track_title = await search_youtube(
            track_names.pop(0)
            )
        if first_track_url:
            if bot.cancela_adicao:
                return

            queue.append((first_track_title, first_track_url))
            if not bot.is_playing:
                await play_next(ctx)

        # 🔥 Busca outras músicas enquanto toca
        for track in track_names:
            if bot.cancela_adicao:
                return  # 🚨 Para de adicionar músicas se *clear foi chamado

            yt_url, yt_title = await search_youtube(track)
            if yt_url:
                queue.append((yt_title, yt_url))

    except Exception as e:
        print(f"Erro ao obter músicas do Spotify: {e}")


@bot.command()
async def queue_list(ctx):
    """ Mostra as músicas na fila corretamente """
    if not queue:
        await ctx.send("🎵 A fila está vazia!")
    else:
        max_display = 5
        queue_display = queue[:max_display]
        queue_text = "\n".join(
            [f"{i+1}. {title}" for i, (title, _) in enumerate(
                queue_display)]
            )
        await ctx.send(
            f"🎶 **Fila de Músicas (Mostrando até {max_display}):**\n{
                queue_text
                }"
            )


@commands.cooldown(1, 5, commands.BucketType.guild)
@bot.command()
async def play(ctx, *, search_query):

    global queue
    bot.cancela_adicao = False  # Permite adicionar músicas novamente

    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if not voice_client or not voice_client.is_connected():
        if ctx.author.voice:
            channel = ctx.author.voice.channel
            try:
                voice_client = await channel.connect(reconnect=True, timeout=3)
                await ctx.send(
                    f"🎶 Entrei rapidamente no canal de voz: {channel.name}"
                    )
            except asyncio.TimeoutError:
                await ctx.send(
                    "❌ Erro ao entrar no canal de voz. Tente novamente."
                    )
                return
        else:
            await ctx.send(
                "❌ Você precisa estar em um canal de voz para me chamar!"
                )
            return

    if "spotify.com" in search_query:
        await get_spotify_tracks(search_query, ctx)
    else:
        yt_url, yt_title = await search_youtube(search_query)
        if yt_url:
            if bot.cancela_adicao:
                return

            queue.append((yt_title, yt_url))
            if not bot.is_playing:
                await play_next(ctx)

    await ctx.send(f"🎶 {len(queue)} músicas na fila.")


@bot.command()
async def skip(ctx):
    """Pula a música atual"""
    voice_client = ctx.voice_client

    if voice_client and voice_client.is_playing():
        voice_client.stop()
        await ctx.send("⏭ Música pulada!")
        await play_next(ctx)
    else:
        await ctx.send("❌ Não há nenhuma música tocando no momento!")


async def play_next(ctx):
    """Toca a próxima música na fila"""
    global queue

    if not queue:
        bot.is_playing = False
        await ctx.send("✅ Fila de músicas finalizada.")
        return

    bot.is_playing = True
    title, audio_url = queue.pop(0)

    voice_client = ctx.voice_client

    if voice_client and not voice_client.is_playing():
        source = discord.FFmpegPCMAudio(audio_url, **FFMPEG_OPTIONS)

        def after_play(error):
            if error:
                print(f"Erro ao tocar música: {error}")
            asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop)

        voice_client.play(source, after=after_play)
        await ctx.send(f"🎵 Tocando agora: {title}")


@bot.command()
async def pause(ctx):
    """ Pausa a música atual """
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("⏸ Música pausada!")
    else:
        await ctx.send("❌ Não há música tocando no momento!")


@bot.command()
async def resume(ctx):
    """ Retoma a música pausada """
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("▶️ Música retomada!")
    else:
        await ctx.send("❌ Não há música pausada no momento!")


@bot.command()
async def leave(ctx):
    """ Faz o bot sair do canal de voz e limpa a fila """
    if ctx.voice_client and ctx.voice_client.is_connected():
        await ctx.voice_client.disconnect()
        queue.clear()
        bot.is_playing = False
        await ctx.send("👋 Saindo do canal de voz e limpando a fila...")
    else:
        await ctx.send("❌ Não estou em um canal de voz!")


bot.cancela_adicao = False


@bot.command()
async def clear(ctx):

    global queue
    queue.clear()
    bot.cancela_adicao = True  # Ativa o bloqueio de novas músicas
    await ctx.send(
        "🗑️ Todas as músicas foram removidas da fila"
        )


load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
bot.run(TOKEN)
