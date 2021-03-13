"""
Cog containing commands for detecting & purging inactive users.

Part of PNBot.
"""

import logging
from typing import TYPE_CHECKING, Optional, Dict, List, Union, Tuple

import pDB
import eCommands
import asyncio
import dateparser
from utilities.pluralKitAPI import get_pk_message, PKAPIUnavailable, CouldNotConnectToPKAPI, UnknownPKError
from utilities.utils import is_team_member, send_long_msg, send_long_embed
from utilities.moreColors import pn_orange
from datetime import datetime
from embeds import std_embed
from utilities.paginator import FieldPages, TextPages, Pages, UnnumberedPages

from uiElements import StringReactPage, BoolPage

import discord
from discord.ext import commands

if TYPE_CHECKING:
    from PNDiscordBot import PNBot
    import asyncpg


log = logging.getLogger(__name__)


class UserManagement(commands.Cog):

    def __init__(self, bot):

        self.bot: 'PNBot' = bot
        self.pool: asyncpg.pool.Pool = bot.db

    """ --- on_* Functions --- """
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        author: Union[discord.Member, discord.User] = message.author

        if author.id != self.bot.user.id and message.guild is not None:  # Don't log our own messages or DM messages.

            message_contents = message.content if message.content != '' else None

            if message_contents is not None or len(message.attachments) > 0:
                msg_con = message_contents
                # msg_con = "a"
                webhook_author_name = message.author.display_name if message.webhook_id is not None else None
                await pDB.cache_message(self.bot.db, message.guild.id, message.id, message.author.id, msg_con, datetime.utcnow())

        # await self.bot.process_commands(message)


    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        """
        Fires on every deleted message.
        Cleans deleted messages from cache, and updates PK messages with PK Details.
        :param payload:
        :type payload:
        :return:
        :rtype:
        """
        async def cleanup_message_cache():
            if db_cached_message is not None:
                await pDB.delete_cached_message(self.bot.db, payload.guild_id, db_cached_message.message_id)

        if payload.guild_id is None:
            return  # We are in a DM, Don't log the message

        # # Get the cached msg from the DB (if possible). Will be None if msg does not exist in DB
        db_cached_message = await pDB.get_cached_message(self.bot.db, payload.guild_id, payload.message_id)

        try:
            pk_msg = await get_pk_message(payload.message_id)
            pk_api_errors = False
            if pk_msg is not None and self.verify_message_is_preproxy_message(payload.message_id, pk_msg):
                # We have confirmed that the message is a pre-proxied message.
                await self.update_cache_pk_message_details(payload.guild_id, pk_msg)
                await cleanup_message_cache()
                return  # Message was a pre-proxied message deleted by PluralKit. Return instead of logging message.

        except PKAPIUnavailable as e:
            # await miscUtils.log_error_msg(self.bot, e)
            log.error(e)
            pk_api_errors = True

        except UnknownPKError as e:
            # await miscUtils.log_error_msg(self.bot, e)
            log.error(e)
            pk_api_errors = True

        await cleanup_message_cache()

    def verify_message_is_preproxy_message(self, message_id: int, pk_response: Dict) -> bool:
        # Compare the proxied msg id reported from the API with this messages id
        #   to determine if this message is actually a proxyed message.
        if 'id' in pk_response:  # Message ID (Discord Snowflake) of the proxied message
            pk_message_id = int(pk_response['id'])
            if message_id == pk_message_id:
                # This is a false positive. We actually do need to log the message.
                return False
            else:
                # Message is indeed a preproxied message
                return True
        else:
            # Message is indeed a preproxied message
            return True

    async def update_cache_pk_message_details(self, guild_id: int, pk_response: Dict):

        error_msg = []
        error_header = '[cache_pk_message_details]: '
        if 'id' in pk_response:  # Message ID (Discord Snowflake) of the proxied message
            message_id = int(pk_response['id'])
        else:
            # If we can not pull the message ID there is no point in continuing.
            msg = "'WARNING! 'id' not in PK msg API Data. Aborting JSON Decode!"
            error_msg.append(msg)
            logging.warning(msg)
            # await miscUtils.log_error_msg(self.bot, error_msg, header=f"{error_header}!ERROR!")
            return

        if 'sender' in pk_response:  # User ID of the account that sent the pre-proxied message. Presumed to be linked to the PK Account
            sender_discord_id = int(pk_response['sender'])
        else:
            sender_discord_id = None
            msg = "WARNING! 'Sender' not in MSG Data"
            error_msg.append(msg)

        if 'system' in pk_response and 'id' in pk_response['system']:  # PK System Id
            system_pk_id = pk_response['system']['id']
        else:
            system_pk_id = None
            msg = "WARNING! 'system' not in MSG Data or 'id' not in system data!"
            error_msg.append(msg)

        if 'member' in pk_response and 'id' in pk_response['member']:  # PK Member Id
            member_pk_id = pk_response['member']['id']
        else:
            member_pk_id = None
            msg = "WARNING! 'member' not in MSG Data or 'id' not in member data!"
            error_msg.append(msg)

        # TODO: Remove verbose Logging once feature deemed to be stable .
        logging.debug(
            f"Updating msg: {message_id} with Sender ID: {sender_discord_id}, System ID: {system_pk_id}, Member ID: {member_pk_id}")
        await pDB.update_cached_message_pk_details(self.bot.db, guild_id, message_id, system_pk_id, member_pk_id,
                                                   sender_discord_id)

        if len(error_msg) > 0:
            # await miscUtils.log_error_msg(self.bot, error_msg, header=error_header)
            log.error(error_msg)


    async def add_cache_pk_message_details(self, guild_id: int, pk_response: Dict, timestamp, content):

        error_msg = []
        if 'id' in pk_response:  # Message ID (Discord Snowflake) of the proxied message
            message_id = int(pk_response['id'])
        else:
            # If we can not pull the message ID there is no point in continuing.
            msg = "'WARNING! 'id' not in PK msg API Data. Aborting JSON Decode!"
            error_msg.append(msg)
            logging.warning(msg)
            # await miscUtils.log_error_msg(self.bot, error_msg, header=f"{error_header}!ERROR!")
            return

        if 'sender' in pk_response:  # User ID of the account that sent the pre-proxied message. Presumed to be linked to the PK Account
            sender_discord_id = int(pk_response['sender'])
        else:
            sender_discord_id = None
            msg = "WARNING! 'Sender' not in MSG Data"
            error_msg.append(msg)

        if 'system' in pk_response and 'id' in pk_response['system']:  # PK System Id
            system_pk_id = pk_response['system']['id']
        else:
            system_pk_id = None
            msg = "WARNING! 'system' not in MSG Data or 'id' not in system data!"
            error_msg.append(msg)

        if 'member' in pk_response and 'id' in pk_response['member']:  # PK Member Id
            member_pk_id = pk_response['member']['id']
        else:
            member_pk_id = None
            msg = "WARNING! 'member' not in MSG Data or 'id' not in member data!"
            error_msg.append(msg)

        # TODO: Remove verbose Logging once feature deemed to be stable .
        logging.debug(
            f"adding msg: {message_id} with Sender ID: {sender_discord_id}, System ID: {system_pk_id}, Member ID: {member_pk_id}")

        # await pDB.update_cached_message_pk_details(self.bot.db, guild_id, message_id, system_pk_id, member_pk_id,
        #                                            sender_discord_id)
        try:
            await pDB.cache_pk_message(self.bot.db, guild_id, message_id, sender_discord_id, content, timestamp, system_pk_id, member_pk_id)
        except Exception as e:
            log.error(e)

        if len(error_msg) > 0:
            # await miscUtils.log_error_msg(self.bot, error_msg, header=error_header)
            log.error(error_msg)


    """                                   '''
    --- Manual Find Inactive User Commands---
    """


    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    @eCommands.group(name="filtered_inactive_members", aliases=["filt_inactive_mem"],
                     brief="Lists all members who have not posted in a given timeframe and with other filters.",
                     category="User Management")
    async def filtered_inactive_members(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(self.filtered_inactive_members)


    @filtered_inactive_members.command(name="join_date",
                                       examples=["'2 weeks' '1 year'", "'4/5/2020' '2/9/2020'"])
    async def by_join_date(self, ctx: commands.Context, last_active: str, time_on_pn: str):
        la_timestamp = dateparser.parse(last_active, settings={'TIMEZONE': 'UTC'})
        pn_timestamp = dateparser.parse(time_on_pn, settings={'TIMEZONE': 'UTC'})

        if la_timestamp is None:
            await ctx.send(f"Error! Unable to determine when {la_timestamp} is!")
            return

        if la_timestamp > datetime.utcnow():
            await ctx.send(f"Error! {la_timestamp} is in the future!!!")
            return

        if pn_timestamp is None:
            await ctx.send(f"Error! Unable to determine when {la_timestamp} is!")
            return

        if pn_timestamp > datetime.utcnow():
            await ctx.send(f"Error! {la_timestamp} is in the future!!!")
            return

        await self.filtered_find_inactive_members(ctx, la_timestamp, pn_timestamp)

    async def filtered_find_inactive_members(self, ctx: commands.Context, last_active: datetime, time_on_pn: Optional[datetime] = None):

        # if time_on_pn is None:
        #     time_on_pn = datetime.min

        status_msg = await ctx.send(embed=std_embed("Searching for inactive members..",
                                                    f"Getting members who have not posted since {last_active.strftime('%b %d, %Y, %I:%M %p UTC')}.\nRetrieving message counts..."))

        messages = await pDB.get_all_cached_messages_after_timestamp(self.bot.db, last_active, ctx.guild.id)
        # await asyncio.sleep(1)

        progress_str = f"Rummaging through {len(messages)} messages.\n" \
                       f"Cross referencing all messages against all current users...\n **Processing! Processing!! Processing!!!**"

        embed = std_embed("Searching for inactive members.......", progress_str)
        await status_msg.edit(embed=embed)
        # await ctx.send(embed=embed)
        # await asyncio.sleep(1)

        inactive_members = []
        inactive_members_text = []
        guild: discord.Guild = ctx.guild
        guild_members = guild.fetch_members(
            limit=None)  # Using the API call because we want to be sure we get all the members.
        async for member in guild_members:
            member: discord.Member
            active = discord.utils.get(messages, user_id=member.id)
            if not active and not member.bot:
                if time_on_pn is None or member.joined_at > time_on_pn:
                    inactive_members.append(member)

        inactive_members.sort(key=lambda x: x.joined_at, reverse=True)

        for inactive_mem in inactive_members:
            time_on_pn_str = self.time_on_pn(inactive_mem)
            inactive_members_text.append(
                f"<@!{inactive_mem.id}> - {inactive_mem.name}#{inactive_mem.discriminator}: Joined {time_on_pn_str}")

        await status_msg.edit(embed=std_embed("Finished searching for inactive members!", ""))

        page_header = f"\nThere are {len(inactive_members)} members that have been inactive since {last_active.strftime('%b %d, %Y, %I:%M %p UTC')}.\n  \n"
        # inactive_members_text.insert(0, page_header)
        page = UnnumberedPages(ctx=ctx, entries=inactive_members_text, per_page=25)
        page.embed.title = page_header  # "Search Complete!"
        page.embed.color = pn_orange()
        await page.paginate()


    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    @eCommands.command(name="inactive_members", aliases=["inactive_mem"],
                       brief="Lists all members who have not posted in a given timeframe.",
                       examples=['1 day and 6 hours ago', "4/5/2020"],
                       category="User Management")
    async def whos_inactive(self, ctx: commands.Context, *, how_long_ago: str):

        timestamp = dateparser.parse(how_long_ago, settings={'TIMEZONE': 'UTC'})

        if timestamp is None:
            await ctx.send(f"Error! Unable to determine when {how_long_ago} is!")
            return

        if timestamp > datetime.utcnow():
            await ctx.send(f"Error! {how_long_ago} is in the future!!!")
            return

        status_msg = await ctx.send(embed=std_embed("Searching for inactive members..", f"Getting members who have not posted since {timestamp.strftime('%b %d, %Y, %I:%M %p UTC')}.\nRetrieving message counts..."))

        messages = await pDB.get_all_cached_messages_after_timestamp(self.bot.db, timestamp, ctx.guild.id)
        # await asyncio.sleep(1)

        progress_str = f"Rummaging through {len(messages)} messages.\n" \
                       f"Cross referencing all messages against all current users...\n **Processing! Processing!! Processing!!!**"

        embed = std_embed("Searching for inactive members.......", progress_str)
        await status_msg.edit(embed=embed)
        # await ctx.send(embed=embed)
        # await asyncio.sleep(1)

        inactive_members = []
        inactive_members_text = []
        guild: discord.Guild = ctx.guild
        guild_members = guild.fetch_members(limit=None)  # Using the API call because we want to be sure we get all the members.
        async for member in guild_members:
            member: discord.Member
            active = discord.utils.get(messages, user_id=member.id)
            if not active and not member.bot:
                inactive_members.append(member)

        inactive_members.sort(key=lambda x: x.joined_at, reverse=True)
        for inactive_mem in inactive_members:
            time_on_pn_str = self.time_on_pn(inactive_mem)
            inactive_members_text.append(f"<@!{inactive_mem.id}> - {inactive_mem.name}#{inactive_mem.discriminator}: Joined {time_on_pn_str}")

        await status_msg.edit(embed=std_embed("Finished searching for inactive members!", ""))

        page_header = f"\nThere are {len(inactive_members)} members that have been inactive since {timestamp.strftime('%b %d, %Y, %I:%M %p UTC')}.\n  \n"
        # inactive_members_text.insert(0, page_header)
        page = UnnumberedPages(ctx=ctx, entries=inactive_members_text, per_page=25)
        page.embed.title = page_header#"Search Complete!"
        page.embed.color = pn_orange()
        await page.paginate()

        # await ctx.send(embed=std_embed("Search Complete!", f"\nI have found {len(inactive_members)} members that have been inactive since {timestamp.strftime('%b %d, %Y, %I:%M %p UTC')}.\n"))


    # @commands.has_permissions(manage_messages=True)
    # @commands.guild_only()
    # @eCommands.command(name="list_post_rate", aliases=["post_rate"],
    #                    brief="Lists all members who have not posted in a given timeframe.",
    #                    examples=['1 day and 6 hours ago', "4/5/2020"],
    #                    category="User Management")
    # async def post_rate(self, ctx: commands.Context, *, how_long_ago: str):
    #
    #     timestamp = dateparser.parse(how_long_ago, settings={'TIMEZONE': 'UTC'})
    #
    #     if timestamp is None:
    #         await ctx.send(f"Error! Unable to determine when {how_long_ago} is!")
    #         return
    #
    #     if timestamp > datetime.utcnow():
    #         await ctx.send(f"Error! {how_long_ago} is in the future!!!")
    #         return
    #
    #     status_msg = await ctx.send(embed=std_embed("Searching for inactive members..",
    #                                                 f"Getting members who have not posted since {timestamp.strftime('%b %d, %Y, %I:%M %p UTC')}.\nRetrieving message counts..."))
    #
    #     messages = await pDB.get_all_cached_messages_after_timestamp(self.bot.db, timestamp, ctx.guild.id)
    #     # await asyncio.sleep(1)
    #
    #     progress_str = f"Rummaging through {len(messages)} messages.\n" \
    #                    f"Cross referencing all messages against all current users...\n **Processing! Processing!! Processing!!!**"
    #
    #     embed = std_embed("Searching for inactive members.......", progress_str)
    #     await status_msg.edit(embed=embed)
    #     # await ctx.send(embed=embed)
    #     # await asyncio.sleep(1)
    #
    #     inactive_members = []
    #     inactive_members_text = []
    #     guild: discord.Guild = ctx.guild
    #     guild_members = guild.fetch_members(
    #         limit=None)  # Using the API call because we want to be sure we get all the members.
    #     async for member in guild_members:
    #         member: discord.Member
    #         active = discord.utils.get(messages, user_id=member.id)
    #         if not active and not member.bot:
    #             inactive_members.append(member)
    #
    #     inactive_members.sort(key=lambda x: x.joined_at, reverse=True)
    #     for inactive_mem in inactive_members:
    #         time_on_pn_str = self.time_on_pn(inactive_mem)
    #         inactive_members_text.append(
    #             f"<@!{inactive_mem.id}> - {inactive_mem.name}#{inactive_mem.discriminator}: Joined {time_on_pn_str}")
    #
    #     await status_msg.edit(embed=std_embed("Finished searching for inactive members!", ""))
    #
    #     page_header = f"\nThere are {len(inactive_members)} members that have been inactive since {timestamp.strftime('%b %d, %Y, %I:%M %p UTC')}.\n  \n"
    #     # inactive_members_text.insert(0, page_header)
    #     page = UnnumberedPages(ctx=ctx, entries=inactive_members_text, per_page=25)
    #     page.embed.title = page_header  # "Search Complete!"
    #     page.embed.color = pn_orange()
    #     await page.paginate()


    """                        
    --- Message Cache Commands  ---
                                """
    @commands.is_owner()
    @commands.guild_only()
    @eCommands.command(name="build_msg_cache",
                       brief="",
                       examples=['1 day and 6 hours ago', "4/5/2020"],
                       category="User Management")
    async def build_msg_cache(self, ctx: commands.Context, start_date: str, end_date: str, category: discord.CategoryChannel, ):
        timestamp: datetime = dateparser.parse(end_date, settings={'TIMEZONE': 'UTC'})

        if timestamp is None:
            await ctx.send(f"Error! Unable to determine when {end_date} is!")
            return

        if timestamp > datetime.utcnow():
            await ctx.send(f"Error! {end_date} is in the future!!!")
            return

        embed = std_embed(title="Building Message Cache", desc=f"\nNow downloading and storing message counts since {timestamp.strftime('%b %d, %Y, %I:%M %p UTC')} .....\n \n"
                                                               f"**This WILL take a while, both due to Discord rate limits and to be nice to Plural Kit :)**\n"
                                                               f"Status Updates will be sent periodically in this channel.\n")
        await ctx.send(embed=embed)
        await asyncio.sleep(2)

        guild: discord.Guild = ctx.guild
        channels: List[discord.TextChannel] = guild.text_channels

        dots = 0
        embed = std_embed(title=f"Building In Progress{'.'*(dots+3)}", desc=f"\n**Retrieving {len(channels)} Channels**")
        status_msg = await ctx.send(embed=embed)
        await asyncio.sleep(1)

        total_msg_count = 0
        channel_count = 0
        for channel in channels:
            ch_msg_count = 0
            channel_count += 1

            async for message in channel.history(limit=None, after=timestamp):
                message: discord.Message
                ch_msg_count += 1
                total_msg_count += 1
                if not message.author.bot:
                    log.info("Adding Norm msg to cache")
                    await pDB.cache_message(self.pool, guild.id, message.id, message.author.id, message.content, message.created_at)

                elif message.webhook_id is not None:
                    # log.info("Found Web Hook MSG")
                    try:
                        pk_response = pk_msg = await get_pk_message(message.id)
                        pk_api_errors = False
                        if pk_msg is not None:  # and self.verify_message_is_preproxy_message(message.id, pk_msg):
                            # We have confirmed that the message is a pre-proxied message.
                            # await self.update_cache_pk_message_details(payload.guild_id, pk_msg)
                            log.info("Adding PK msg to cache")
                            await self.add_cache_pk_message_details(guild.id, pk_response, message.created_at, message.content)
                            await asyncio.sleep(0.2)

                    except PKAPIUnavailable as e:
                        # await miscUtils.log_error_msg(self.bot, e)
                        log.error(e)
                        pk_api_errors = True

                    except UnknownPKError as e:
                        # await miscUtils.log_error_msg(self.bot, e)
                        log.error(e)
                        pk_api_errors = True
                log.info(f"\n**Retrieving messages from {channel.name}**\n Retrieved {total_msg_count} messages so far.")
                if ch_msg_count % 100 == 0:
                    dots = dots + 1 if dots < 10 else 0
                    embed = std_embed(title=f"Building In Progress{'.' * (dots + 3)}",
                                      desc=f"\n**Retrieving messages from {channel.name}. Channel# {channel_count}/{len(channels)}**\n Retrieved {total_msg_count} messages so far.")
                    await status_msg.edit(embed=embed)
                    await asyncio.sleep(1)

        embed = std_embed(title=f"Message Cache Complete",
                          desc=f"\n**Message Cache Complete. Retrieved {total_msg_count} messages.**")
        await status_msg.edit(embed=embed)
        await asyncio.sleep(1)


    @is_team_member()
    @commands.guild_only()
    @eCommands.command(name="list_nonmembers",
                       brief="Displays a list of all users who are not yet members and how long the have been present.",
                       examples=[""],
                       category="User Management")
    async def list_nonmembers(self, ctx: commands.Context):

        guild_settings = self.bot.guild_settings(ctx.guild.id)
        member_role_id = guild_settings["member_role_id"] if guild_settings is not None else None

        guild: discord.Guild = ctx.guild
        guild_members = guild.fetch_members(limit=None)  # Using the API call because we want to be sure we get all the members.

        non_members_count = 0
        non_members_str = ""
        async for user in guild_members:
            user: Union[discord.Member, discord.User]
            roles: List[discord.Role] = user.roles
            is_member = discord.utils.get(roles, id=member_role_id)
            if not is_member:
                non_members_count += 1

                time_on_pn_str = self.time_on_pn(user)
                non_members_str += f"<@!{user.id}> - {user.name}#{user.discriminator}: Joined {time_on_pn_str}\n"

        await send_long_embed(ctx, f"**There are {non_members_count} users who have not yet been greeted:**", non_members_str)


    def time_on_pn(self, member: discord.Member) -> str:
        join_date = member.joined_at
        time_on_pn = datetime.utcnow() - join_date
        if time_on_pn.days > 0:
            time_on_pn_str = f"**{time_on_pn.days}** days ago."
        else:
            hours = time_on_pn.seconds // 3600
            minutes = (time_on_pn.seconds % 3600) // 60

            if hours > 0:
                time_on_pn_str = f"**{hours + (minutes / 60):.2f}** hours ago."
            else:
                seconds = time_on_pn.seconds % 60
                time_on_pn_str = f"**{minutes + (seconds / 60):.2f}** minutes ago."
        return time_on_pn_str

    """                     
    --- Post Count Commands ---
                            """
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    @eCommands.command(name="get_user_post_count", aliases=["user_post_count"],
                       brief="Lists how many messaged (including w/ PK) a user has posted in a given timeframe.",
                       examples=['@Hibiki 1 day and 6 hours ago', "12374839475644433 4/5/2020"],
                       category="User Management")
    async def user_post_count(self, ctx: commands.Context, member: discord.Member, *, how_long_ago: str):

        timestamp = dateparser.parse(how_long_ago, settings={'TIMEZONE': 'UTC'})

        if timestamp is None:
            await ctx.send(f"Error! Unable to determine when {how_long_ago} is!")
            return

        if timestamp > datetime.utcnow():
            await ctx.send(f"Error! {how_long_ago} is in the future!!!")
            return

        status_msg = await ctx.send(embed=std_embed("Searching for posts..",
                                                    f"Searching for posts since {timestamp.strftime('%b %d, %Y, %I:%M %p UTC')}.\nRetrieving message counts..."))

        messages = await pDB.get_all_cached_messages_after_timestamp(self.bot.db, timestamp, ctx.guild.id)
        # await asyncio.sleep(1)

        progress_str = f"Rummaging through {len(messages)} messages.\n" \
                       f"**Processing! Processing!! Processing!!!**"

        embed = std_embed("Searching for posts.......", progress_str)
        await status_msg.edit(embed=embed)
        # await ctx.send(embed=embed)
        # await asyncio.sleep(1)

        post_count = 0

        guild: discord.Guild = ctx.guild
        for msg in messages:
            if msg.user_id == member.id:
                post_count += 1

        await status_msg.edit(embed=std_embed("Finished searching for posts!", f"<@!{member.id}> - {member.name}#{member.discriminator} has made **{post_count}** since {timestamp.strftime('%b %d, %Y, %I:%M %p UTC')}/n"
                                                                               f"They joined on "))

    """                     
    --- Manual Give/Remove Inactive User Commands ---
                                                  """


def setup(bot):
    bot.add_cog(UserManagement(bot))
