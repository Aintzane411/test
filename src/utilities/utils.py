"""

"""
import logging
import json
from typing import Optional

import discord
from discord.ext import commands

from utilities.moreColors import pn_orange

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


async def send_embed(ctx: commands.Context, title: Optional[str] = None, desc: Optional[str] = None, color: Optional[discord.Color] = None, content: Optional[str] = None):
    """Constructs and sends a basic embed."""
    if title is None:
        title = discord.embeds.EmptyEmbed

    if desc is None:
        desc = discord.embeds.EmptyEmbed

    if color is None:
        color = pn_orange()

    embed = discord.Embed(title=title, description=desc, color=color)
    await ctx.send(content=content, embed=embed)



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