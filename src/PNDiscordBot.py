"""
"""
import sys
import logging
import traceback

from typing import TYPE_CHECKING, Optional, Dict

import discord
from discord.ext import commands

from Interviews import Interviews

if TYPE_CHECKING:
    import asyncpg

log = logging.getLogger(__name__)


extensions = (
    # -- Command Extensions -- #
    'cogs.helpCmd',
    'cogs.roles',
)


class PNBot(commands.Bot):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db: Optional[asyncpg.pool.Pool] = None
        self.open_interviews: Optional[Interviews] = None
        self._guild_settings: Dict[int, Dict] = {}  # Dict of Guild Settings acceced by
        self.primary_guild_id: int = 0

    def load_cogs(self):
        for extension in extensions:
            try:
                self.load_extension(extension)
                log.info(f"Loaded {extension}")
            except Exception as e:
                log.info(f'Failed to load extension {extension}.', file=sys.stderr)
                traceback.print_exc()


    def guild_settings(self, guild_id: int) -> Optional[Dict]:
        """
        Get the guild settings for a guild.
        """
        if guild_id in self._guild_settings:
            return self._guild_settings[guild_id]
        return None

    def guild_setting(self, guild_id: int, key):
        """
        Get the guild settings for a guild.
        """
        if guild_id in self._guild_settings:
            if key in self._guild_settings[guild_id][key]:
                return self._guild_settings[guild_id][key]
        return None


    def load_guild_settings(self, guild_id: int, settings: Dict):
        self._guild_settings[guild_id] = settings


    async def get_message(self, message_id: int, channel_id: Optional[int] = None):
        """Attempts to retrieve a message via ID from the cache, if it can't be found and a channel_id is provided, it will then attempt to fetch the message from Discord. """

        message = discord.utils.get(self.cached_messages, id=message_id)
        if message is not None:
            return message

        if channel_id is not None:
            channel: discord.TextChannel = self.get_channel(channel_id)
            if channel is not None and isinstance(channel, discord.TextChannel):
                try:
                    message = await channel.fetch_message(message_id)
                    return message
                except (discord.NotFound, discord.Forbidden, discord.HTTPException) as e:
                    log.info(e)
                    return None
