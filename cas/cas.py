import asyncio
import concurrent.futures
import io
import mimetypes
import typing

import aiohttp
import aiohttp.web
import discord
from redbot.core import commands
from wand.image import Image
import wand.exceptions


class Cas(commands.Cog):
    """Content-aware-scale"""

    def __init__(self, bot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=5
        )

    @commands.command('cas')
    @commands.guild_only()
    async def cas(self, ctx, scale: typing.Optional[float] = 0.5, target: typing.Union[discord.Member, str] = None):
        """Scales an image using content-aware-scale

        Target can be a URL or a guild member.
        """
        loop = asyncio.get_running_loop()

        if 0 > scale or scale > 2:
            return await ctx.send('Scaling failed because the scale factor is not allowed!')

        scale_progress = discord.Embed(
            title='Content Aware Scaling',
            description=':inbox_tray:   Downloading image'
        )
        scaling_message = await ctx.send(embed=scale_progress)

        if ctx.message.attachments:
            image = ctx.message.attachments[0]

            img = await image.read()
        elif type(target) is discord.Member:
            target = target.avatar_url_as(static_format='png')
            img = await target.read()
        elif target is None:
            target = ctx.author.avatar_url_as(static_format='png')
            img = await target.read()
        else:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(target) as resp:
                        img = await resp.read()
            except (aiohttp.ClientError, aiohttp.web.HTTPException):
                scale_progress.description = ':x:   Download failed'
                return await scaling_message.edit(embed=scale_progress)

        scale_progress.description = ':hourglass:   Scaling image'
        await scaling_message.edit(embed=scale_progress)

        try:
            img = io.BytesIO(img)
            with Image(file=img) as img:
                if img.animation:
                    img.iterator_reset()
                    await loop.run_in_executor(
                        self.executor, img.liquid_rescale, int(img.width * scale), int(img.height * scale)
                    )
                    while img.iterator_next():
                        await loop.run_in_executor(
                            self.executor, img.liquid_rescale, int(img.width*scale), int(img.height*scale)
                        )
                else:
                    await loop.run_in_executor(
                        self.executor, img.liquid_rescale, int(img.width*scale), int(img.height*scale)
                    )

                scale_progress.description = ':outbox_tray:   Uploading'
                await scaling_message.edit(embed=scale_progress)

                file = io.BytesIO(img.make_blob())

                upload = discord.File(fp=file, filename=f'result{mimetypes.guess_extension(img.mimetype)}')
                await ctx.send(file=upload)
                await scaling_message.delete()
        except wand.exceptions.MissingDelegateError:
            scale_progress.description = ':x:   Cannot read file type'
            return await scaling_message.edit(embed=scale_progress)
