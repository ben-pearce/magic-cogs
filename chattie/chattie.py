import discord
import typing
from redbot.core import commands, data_manager, checks, Config
import markovify
import markovify.splitters
import aiofiles
import os
import pickle
import asyncio


class Chattie(commands.Cog):
    """Markov chatbot"""

    def __init__(self, bot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

        self.config = Config.get_conf(self, identifier=439283409324832098)

        default_guild = {
            'learn': True,
            'learn_channels': [],
            'speak_channels': []
        }
        self.config.register_guild(**default_guild)

    @commands.group('chattie')
    @checks.admin_or_permissions(manage_guild=True)
    async def _chattie(self, ctx):
        """Command group for chattie!"""

    @_chattie.group('set')
    async def _chattie_set(self, ctx):
        """Settings for chattie"""

    @_chattie_set.command('learn')
    async def _chattie_set_learn(self, ctx):
        """Sets whether or not chattie will learn from conversation

        Note: Requires that at least 1 learn channel is set with [p]chattie set source add [channel]"""
        current_setting = await self.config.guild(ctx.guild).learn()
        await self.config.guild(ctx.guild).learn.set(not current_setting)

        source_channels = ', '.join(await self.config.guild(ctx.guild).learn_channels())

        await ctx.send(f'I will learn from conversations in **{source_channels}**'
                       if not current_setting else
                       'I will not learn from conversations')

    @_chattie_set.group('source')
    async def _chattie_set_source(self, ctx):
        """Control which channels chattie will learn from"""

    @_chattie_set_source.command('add')
    async def _chattle_set_source_add(self, ctx, channel: discord.TextChannel):
        """Add a channel to be learned from"""

        learn_channels = await self.config.guild(ctx.guild).learn_channels()
        if channel.id not in learn_channels:
            learn_channels.append(channel.id)
            await ctx.send(f'<#{channel.id}> is now a learn channel')
            await self.config.guild(ctx.guild).learn_channels.set(learn_channels)
        else:
            await ctx.send(f'<#{channel.id}> is already a learn channel')

    @_chattie_set_source.command('remove')
    async def _chattle_set_source_remove(self, ctx, channel: discord.TextChannel):
        """Stop a channel being learned from"""

        learn_channels = await self.config.guild(ctx.guild).learn_channels()
        if channel.id in learn_channels:
            learn_channels.remove(channel.id)
            await ctx.send(f'<#{channel.id}> is no longer a learn channel')
            await self.config.guild(ctx.guild).learn_channels.set(learn_channels)
        else:
            await ctx.send(f'<#{channel.id}> is not a learn channel')

    @_chattie_set_source.command('list')
    async def _chattle_set_source_list(self, ctx):
        """List current learn channels"""

        learn_channels = await self.config.guild(ctx.guild).learn_channels()
        learn_channels_embed = discord.Embed(
            title='Learn channels',
            description=', '.join([f'<#{channel}>' for channel in learn_channels]) if learn_channels else 'None'
        )
        await ctx.send(embed=learn_channels_embed)

    @_chattie_set.group('speak')
    async def _chattie_set_speak(self, ctx):
        """Control which channels chattie will speak in"""

    @_chattie_set_speak.command('add')
    async def _chattle_set_speak_add(self, ctx, channel: discord.TextChannel):
        """Add a channel for chattie to speak in"""

        speak_channels = await self.config.guild(ctx.guild).speak_channels()
        if channel.id not in speak_channels:
            speak_channels.append(channel.id)
            await ctx.send(f'I can now speak in <#{channel.id}>')
            await self.config.guild(ctx.guild).speak_channels.set(speak_channels)
        else:
            await ctx.send(f'I can already speak in <#{channel.id}>')

    @_chattie_set_speak.command('remove')
    async def _chattle_set_speak_remove(self, ctx, channel: discord.TextChannel):
        """Stop chattie from speaking in a channel"""

        speak_channels = await self.config.guild(ctx.guild).speak_channels()
        if channel.id in speak_channels:
            speak_channels.remove(channel.id)
            await ctx.send(f'I can no longer speak in <#{channel.id}>')
            await self.config.guild(ctx.guild).speak_channels.set(speak_channels)
        else:
            await ctx.send(f'I cannot speak in <#{channel.id}>')

    @_chattie_set_speak.command('list')
    async def _chattle_set_speak_list(self, ctx):
        """List current speaking channels

        Note: If there are none, then bot will speak anywhere"""

        speak_channels = await self.config.guild(ctx.guild).speak_channels()
        speak_channels_embed = discord.Embed(
            title='Speak channels',
            description=', '.join([f'<#{channel}>' for channel in speak_channels]) if speak_channels else 'None'
        )
        await ctx.send(embed=speak_channels_embed)

    @_chattie.group('train')
    async def _chattie_train(self, ctx):
        """Train chattie bot"""

    def _get_guild_corpa_path(self, guid_id):
        cog_data_path = data_manager.cog_data_path(self)
        corpa_path = os.path.join(str(cog_data_path), 'corpa')

        return os.path.join(corpa_path, f'{guid_id}.pkl')

    def _tidy_sentence(self, sentence):
        sentence = sentence.strip()
        if len(sentence) == 0:
            return str()
        if not sentence.endswith('.'):
            sentence += '. '
        return sentence

    @_chattie_train.command('channel')
    @commands.guild_only()
    async def _chattie_train_channel(self, ctx, channel: typing.Optional[discord.TextChannel] = None,
                                     limit: typing.Optional[int] = 100,
                                     erase_memory: typing.Optional[bool] = False):
        """Train chattie bot from channel message history"""
        if channel is None:
            channel = ctx.channel

        training_embed = discord.Embed(
            title='Training',
            description=f':brain: Training from channel {channel}'
        )
        training_msg = await ctx.send(embed=training_embed)

        corpus = str()
        async for message in channel.history(limit=limit):
            corpus += self._tidy_sentence(message.clean_content)

        if len(corpus) > 0:
            model = markovify.Text(corpus)

            corpa_path = self._get_guild_corpa_path(ctx.guild.id)

            if os.path.isfile(corpa_path) and not erase_memory:
                async with aiofiles.open(corpa_path, 'rb') as f:
                    data = pickle.loads(await f.read())
                    original_model = markovify.Text.from_dict(data)
                    model = markovify.combine([original_model, model])

            async with aiofiles.open(corpa_path, 'wb') as f:
                await f.write(pickle.dumps(model.to_dict()))

            training_embed.description = ':white_check_mark: Successfully trained!'
            await training_msg.edit(embed=training_embed)
        else:
            training_embed.description = ':x: No data found to train with'
            await training_msg.edit(embed=training_embed)

    @commands.Cog.listener()
    async def on_message_without_command(self, message):
        ctx = await self.bot.get_context(message)

        if message.guild is not None \
                and ctx.prefix is None \
                and message.author != self.bot.user:
            corpa_path = self._get_guild_corpa_path(message.guild.id)

            if not os.path.isfile(corpa_path):
                return

            model = None
            learn = await self.config.guild(message.guild).learn()
            learn_channels = await self.config.guild(message.guild).learn_channels()
            speak_channels = await self.config.guild(message.guild).speak_channels()

            if learn and message.channel.id in learn_channels:
                async with aiofiles.open(corpa_path, 'rb+') as f:
                    data = pickle.loads(await f.read())
                    original_model = markovify.Text.from_dict(data)

                    corpus = self._tidy_sentence(message.clean_content)

                    if len(corpus) > 0:
                        model = markovify.Text(corpus)
                        model = markovify.combine([original_model, model])
                        await f.seek(0)
                        await f.write(pickle.dumps(model.to_dict()))
                        await f.truncate()
                    else:
                        model = original_model

            if self.bot.user in message.mentions and (message.channel.id in speak_channels or not speak_channels):
                if model is None:
                    async with aiofiles.open(corpa_path, 'rb') as f:
                        data = pickle.loads(await f.read())
                        model = markovify.Text.from_dict(data)

                sentence = model.make_sentence()

                async with message.channel.typing():
                    if sentence:
                        await asyncio.sleep(len(sentence) / 20)
                        await message.channel.send(sentence)
                    else:
                        await asyncio.sleep(.2)
                        await message.channel.send(':thinking:')
