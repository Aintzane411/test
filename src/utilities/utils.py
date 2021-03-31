"""

"""
import logging
import json
from typing import Optional, TYPE_CHECKING, List, Union

import asyncio
import discord
from discord.ext import commands
from discord.embeds import EmptyEmbed

from utilities.moreColors import pn_orange
from exceptions import NotTeamMember, NotMember, NotTeamOrPotentialMember

if TYPE_CHECKING:
    from PNDiscordBot import PNBot
    from pDB import RoleCategory, AllowedRole

log = logging.getLogger("PNBot")


class SnowFlake:
    def __init__(self, _id: int):
        self.id = _id


class CachedMessage:
    def __init__(self, author_id, author_name, author_pfp, message, timestamp):
        pass


async def get_channel(client: commands.Bot, channel_id: int) -> Optional[discord.TextChannel]:
    """
    Gets the channel from the cache and falls back on an API call if it's not in the cache.
    """
    channel = client.get_channel(channel_id)
    if channel is None:
        log.warning("Channel {} is not in the cache. Falling back to API call".format(channel_id))
        try:
            channel = await client.fetch_channel(channel_id)
        except discord.errors.NotFound:
            return None
    return channel


# ---------- JSON Methods ---------- #
# def backup_interviews(interviews, interview_file_path: str = './data/interview_dump.json'):
#     num_of_interviews = len(interviews.interviews)
#     with open(interview_file_path, 'w') as jdump:
#         jdump.write(interviews.dump_json())
#     log.info("{} interviews backed up".format(num_of_interviews))


def clear_all_interviews(interview_file_path: str = './data/interview_dump.json'):

    with open(interview_file_path, 'w') as jdump:
        jdump.write(json.dumps({"interviews": []}, indent=4))


def save_settings(settings, settings_file_path: str = 'guildSettings.json'):
    with open(settings_file_path, 'w') as jdump:
        json.dump(settings, jdump, indent=4)
    log.info("Settings backed up")


# ---------- DB Methods ---------- #
async def backup_interviews_to_db(interviews):
    await interviews.save_to_db()
    log.info("{} interviews backed up".format(len(interviews.interviews)))


async def get_webhook(client: commands.Bot, channel: discord.TextChannel) -> discord.Webhook:
    """
    Gets the existing webhook from the guild and channel specified. Creates one if it does not exist.
    """

    existing_webhooks = await channel.webhooks()
    webhook = discord.utils.get(existing_webhooks, user=client.user)

    if webhook is None:
        log.warning("Webhook did not exist in channel {}! Creating new webhook!".format(channel.name))
        webhook = await channel.create_webhook(name="PNestBot", reason="Creating webhook for PNest Interview Bot")

    return webhook


async def send_embed(ctx: commands.Context, title: Optional[str] = None, desc: Optional[str] = None, color: Optional[discord.Color] = None, content: Optional[str] = None) -> discord.Message:
    """Constructs and sends a basic embed."""
    _embed = None
    if title is not None or desc is not None:
        _embed = pn_embed(title, desc, color)

    return await ctx.send(content=content, embed=_embed)


def pn_embed(title: Optional[str] = None, desc: Optional[str] = None, color: Optional[discord.Color] = None) -> discord.Embed:
    """Constructs a basic embed with color defaulting to pn_orange instead of black."""
    if title is None:
        title = discord.embeds.EmptyEmbed

    if desc is None:
        desc = discord.embeds.EmptyEmbed

    if color is None:
        color = pn_orange()

    _embed = discord.Embed(title=title, description=desc, color=color)
    return _embed


def is_team_member():
    async def predicate(ctx: commands.Context):

        if ctx.guild is None:  # Double check that we are not in a DM.
            raise commands.NoPrivateMessage()

        bot: 'PNBot' = ctx.bot
        author: discord.Member = ctx.author
        guild_settings = bot.guild_settings(ctx.guild.id)
        role = discord.utils.get(author.roles, id=guild_settings["team_role_id"]) if guild_settings is not None else None
        if role is None:
            raise NotTeamMember()
        return True
    return commands.check(predicate)


def is_team_or_potential_member():
    async def predicate(ctx: commands.Context):

        if ctx.guild is None:  # Double check that we are not in a DM.
            raise commands.NoPrivateMessage()

        bot: 'PNBot' = ctx.bot
        author: discord.Member = ctx.author
        guild_settings = bot.guild_settings(ctx.guild.id)
        team_role = discord.utils.get(author.roles, id=guild_settings["team_role_id"]) if guild_settings is not None else None
        member_role = discord.utils.get(author.roles, id=guild_settings["member_role_id"]) if guild_settings is not None else None

        if member_role is None or team_role is not None:
            return True

        raise NotTeamOrPotentialMember()

    return commands.check(predicate)


def is_server_member():
    async def predicate(ctx: commands.Context):

        if ctx.guild is None:  # Double check that we are not in a DM.
            raise commands.NoPrivateMessage()

        bot: 'PNBot' = ctx.bot
        author: discord.Member = ctx.author
        guild_settings = bot.guild_settings(ctx.guild.id)
        member_role = discord.utils.get(author.roles, id=guild_settings["member_role_id"]) if guild_settings is not None else None
        if member_role is None:
            team_role = discord.utils.get(author.roles, id=guild_settings["team_role_id"]) if guild_settings is not None else None
            if team_role is None:
                raise NotMember()
        return True
    return commands.check(predicate)


async def purge_deleted_roles(ctx: commands.Context, allowed_roles: List['AllowedRole']) -> List[int]:
    """Deletes any roles that may linger in the DB that have already been deleted in discord."""

    guild_roles: List[discord.Role] = ctx.guild.roles[1:]  # Get all the roles from the guild EXCEPT @everyone.
    purged_roles = []
    for allowed_role in allowed_roles:
        if discord.utils.get(guild_roles, id=allowed_role.role_id) is None:
            purged_roles.append(allowed_role.role_id)

            await allowed_role.remove(ctx.bot.db)

    return purged_roles


async def send_long_msg(channel: [discord.TextChannel, commands.Context], message: str, code_block: bool = False, code_block_lang: str = "python"):

    if code_block:
        if len(code_block_lang) > 0:
            code_block_lang = code_block_lang + "\n"
        code_block_start = f"```{code_block_lang}"
        code_block_end = "```"
        code_block_extra_length = len(code_block_start) + len(code_block_end)
        chunks = split_text(message, max_size=2000 - code_block_extra_length)
        message_chunks = [code_block_start + chunk + code_block_end for chunk in chunks]

    else:
        message_chunks = split_text(message, max_size=2000)

    for chunk in message_chunks:
        await channel.send(chunk)


async def send_long_embed(channel: [discord.TextChannel, commands.Context], title: str, message: str):

    message_chunks = split_text(message, max_size=2000)

    for i, chunk in enumerate(message_chunks):
        if len(message_chunks) > 1:
            embed_title = f"{title} ({i+1}/{len(message_chunks)})"
        else:
            embed_title = title
        embed = pn_embed(embed_title, chunk)
        await channel.send(embed=embed)
        await asyncio.sleep(0.5)


def split_text(text: Union[str, List], max_size: int = 2000, delimiter: str = "\n") -> List[str]:
    """Splits the input text such that no entry is longer that the max size """
    delim_length = len(delimiter)

    if isinstance(text, str):
        if len(text) < max_size:
            return [text]
        text = text.split(delimiter)
    else:
        if sum(len(i) for i in text) < max_size:
            return ["\n".join(text)]

    output = []
    tmp_str = ""
    count = 0
    for fragment in text:
        fragment_length = len(fragment) + delim_length
        if fragment_length > max_size:
            raise ValueError("A single line exceeded the max length. Can not split!")  # TODO: Find a better way than throwing an error.
        if count + fragment_length > max_size:
            output.append(tmp_str)
            tmp_str = ""
            count = 0

        count += fragment_length
        tmp_str += f"{fragment}{delimiter}"

    output.append(tmp_str)

    return output


def make_ordinal(n: int) -> str:
    """
    Convert an integer into its ordinal representation::

        make_ordinal(0)   => '0th'
        make_ordinal(3)   => '3rd'
        make_ordinal(122) => '122nd'
        make_ordinal(213) => '213th'
    """
    suffix = ['th', 'st', 'nd', 'rd', 'th', 'th', 'th', 'th', 'th', 'th']

    if n < 0:
        n *= -1

    n = int(n)

    if n % 100 in (11, 12, 13):
        s = 'th'
    else:
        s = suffix[n % 10]

    return str(n) + s
    # if numb < 20:  # determining suffix for < 20
    #     if numb == 1:
    #         suffix = 'st'
    #     elif numb == 2:
    #         suffix = 'nd'
    #     elif numb == 3:
    #         suffix = 'rd'
    #     else:
    #         suffix = 'th'
    # else:  # determining suffix for > 20
    #     tens = str(numb)
    #     tens = tens[-2]
    #     unit = str(numb)
    #     unit = unit[-1]
    #     if tens == "1":
    #         suffix = "th"
    #     else:
    #         if unit == "1":
    #             suffix = 'st'
    #         elif unit == "2":
    #             suffix = 'nd'
    #         elif unit == "3":
    #             suffix = 'rd'
    #         else:
    #             suffix = 'th'
    # return str(numb) + suffix


class GuildSettings:

    def __init__(self, file_name: str = "guildSettings.json"):
        self.archive_enabled = True
        try:
            with open(file_name) as idc_json_data_file:
                id_config = json.load(idc_json_data_file)
                self.__dict__ = id_config
        except FileNotFoundError:
            self.archive_enabled = False
            # Category IDs
            self.interview_category_id = 646696026094174228

            # Channel IDs
            self.archive_channel_id = 647148287710724126
            self.welcome_channel_id = 433448714523246612
            self.log_channel_id = 647487542484271115

            # Role IDs
            self.greeter_role_id = 646693327978102815
            self.member_role_id = 646738204560588809
            self.archive_enabled = True
            self.store_settings("All")

    def __setattr__(self, name, value):
        self.__dict__[name] = value
        if name != "archive_enabled" and self.archive_enabled:
            self.store_settings(name)

    # @property
    # def interview_category_id(self):
    #     return self._interview_category_id
    #
    # @interview_category_id.setter
    # def interview_category_id(self, value):
    #     self._interview_category_id = value
    #     self.store_settings()
    #
    # @property
    # def archive_channel_id(self):
    #     return self._archive_channel_id
    #
    # @archive_channel_id.setter
    # def archive_channel_id(self, value):
    #     self._archive_channel_id = value
    #     self.store_settings()
    #
    # @property
    # def welcome_channel_id(self):
    #     return self._welcome_channel_id
    #
    # @welcome_channel_id.setter
    # def welcome_channel_id(self, value):
    #     self._welcome_channel_id = value
    #     self.store_settings()
    #
    # @property
    # def log_channel_id(self):
    #     return self._log_channel_id
    #
    # @log_channel_id.setter
    # def log_channel_id(self, value):
    #     self._log_channel_id = value
    #     self.store_settings()
    #
    # @property
    # def greeter_role_id(self):
    #     return self._greeter_role_id
    #
    # @greeter_role_id.setter
    # def greeter_role_id(self, value):
    #     self._greeter_role_id = value
    #     self.store_settings()
    #
    # @property
    # def member_role_id(self):
    #     return self._member_role_id
    #
    # @member_role_id.setter
    # def member_role_id(self, value):
    #     self._member_role_id = value
    #     self.store_settings()

    def store_settings(self, name):
        print("Archiving Settings. {} was changed.".format(name))



if __name__ == '__main__':
    settings = SettingsHandler()

    print(settings.interview_category_id)
    settings.interview_category_id = 1234567890
    print(settings.interview_category_id)

    print("Done")