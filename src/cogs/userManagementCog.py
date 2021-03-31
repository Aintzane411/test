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
from utilities.utils import is_team_member, send_long_msg, send_long_embed, pn_embed
from utilities.moreColors import pn_orange
from datetime import datetime, timedelta
from embeds import std_embed
from utilities.paginator import FieldPages, TextPages, Pages, UnnumberedPages

from uiElements import StringReactPage, BoolPage

import discord
from discord.ext import commands

if TYPE_CHECKING:
    from PNDiscordBot import PNBot
    import asyncpg


log = logging.getLogger(__name__)


def get_cooldown_room_id_from_role_id(cooldown_configs: List[Dict[str, int]], role_id: int) -> Optional[int]:
    for cooldown_config in cooldown_configs:
        cooldown_role_id: int = cooldown_config['role']
        cooldown_channel_id: int = cooldown_config['channel']
        if role_id == cooldown_role_id:
            return cooldown_channel_id
    return None


def get_role_id_from_cooldown_room_id(cooldown_configs: List[Dict[str, int]], room_id: int) -> Optional[int]:
    for cooldown_config in cooldown_configs:
        cooldown_role_id: int = cooldown_config['role']
        cooldown_channel_id: int = cooldown_config['channel']
        if room_id == cooldown_channel_id:
            return cooldown_role_id
    return None


def get_users_cooldown_role(cooldown_configs: List[Dict[str, int]], member: Union[discord.User, discord.Member]) -> Optional[discord.Role]:

    for cooldown_config in cooldown_configs:
        cooldown_role_id: int = cooldown_config['role']
        in_cooldown = discord.utils.get(member.roles, id=cooldown_role_id)
        if in_cooldown is not None:
            return in_cooldown
    return None


def get_users_cooldown_role_channel_and_number(cooldown_configs: List[Dict[str, int]], member: Union[discord.User, discord.Member]) -> Tuple[Optional[discord.Role], Optional[discord.TextChannel], int]:
    """
    If a user is in a cooldown channel (determined by if they have a cooldown role), return the role, channel and channel number (1 indexed)
    Otherwise, we return None, None, 0
    :param cooldown_configs:
    :type cooldown_configs:
    :param member:
    :type member:
    :return:
    :rtype:
    """
    guild: discord.Guild = member.guild
    for i, cooldown_config in enumerate(cooldown_configs):
        cooldown_role_id: int = cooldown_config['role']
        cooldown_channel_id: int = cooldown_config['channel']
        cooldown_role = discord.utils.get(member.roles, id=cooldown_role_id)
        if cooldown_role is not None:
            cooldown_channel = discord.utils.get(guild.channels, id=cooldown_channel_id)
            return cooldown_role, cooldown_channel, i+1

    return None, None, 0


async def isolate_inactive_member(ctx: commands.Context, member: Union[discord.User, discord.Member],
                                  roles_to_keep: List[discord.Role]):
    inactive_level_one_id: int = ctx.bot.guild_setting(ctx.guild.id, 'inactive_level_one_role_id')  # 815335443285147679
    inactive_level_two_id: int = ctx.bot.guild_setting(ctx.guild.id, 'inactive_level_two_role_id')  # 815335449194659911

    log.info(f"Getting users roles from Discord")
    # allowed_roles = await pDB.get_roles_in_guild(self.pool, ctx.guild.id)
    user_roles: List[discord.Role] = member.roles[1:]  # Get all the roles EXCEPT @everyone.

    log.info("Adding removed roles to DB")
    roles_to_remove = []
    for role in user_roles:
        keep = discord.utils.get(roles_to_keep, id=role.id)

        if keep is None:
            roles_to_remove.append(role)
            await pDB.add_role_tmp_removed_from_user(ctx.bot.db, ctx.guild.id, member.id, role.id)

    log.info("Removing roles from user")
    roles_unable_to_remove = []
    for role in roles_to_remove:
        try:
            await member.remove_roles(role, reason="Member was moved to Welcome Back due to inactivity.")
        except discord.Forbidden:
            roles_unable_to_remove.append(role)
            log.info("Could not remove all roles due to permissions")
    log.info("Temp Remove Complete. Adding Inactive Role")


    if len(roles_unable_to_remove) > 0:
        unremovable_roles_str = ""
        for role in roles_unable_to_remove:
            unremovable_roles_str += f"{role.mention}, "
        await ctx.send(embed=pn_embed(title=f"**Unable to remove the following roles from {member.display_name}**",
                                      desc=unremovable_roles_str))

    await member.add_roles(discord.Object(inactive_level_one_id), reason="Member was moved to Welcome Back due to inactivity.")

    await pDB.add_inactivity_event(ctx.bot.db, ctx.guild.id, member.id, current_level=1, previous_level=0, reason=None)

    welcome_back_channel_id: int = ctx.bot.guild_setting(ctx.guild.id, 'welcome_back_channel_id')
    guild: discord.Guild = ctx.guild
    welcome_back_ch: discord.TextChannel = guild.get_channel(welcome_back_channel_id)
    if welcome_back_ch is not None:
        await welcome_back_ch.send("\N{Waving Hand Sign}")
        await welcome_back_ch.send(f"Hey there! Long time no see {member.display_name}!!!!\n"
                                   f"\N{ZERO WIDTH SPACE}\n"
                                   f"No worries, you're not in trouble or anything, you've just been moved to this channel since it's been a while since you last spoke here at Nest. This way we can better protect our members.\n"
                                   f"\N{ZERO WIDTH SPACE}\n"
                                   f"You're still more than welcome here and we would absolutely love to get to talk to you again \N{Slightly Smiling Face}\n"
                                   f"Just say hi and a staff member will restore your access to the rest of the server.")


async def restore_inactive_member(ctx: commands.Context, member: Union[discord.User, discord.Member]):
    inactive_level_one_id: List[int] = ctx.bot.guild_setting(ctx.guild.id, 'inactive_level_one_role_id')
    # inactive_level_two_id: List[int] = self.bot.guild_setting(ctx.guild.id, 'inactive_level_two_role_id')

    log.info(f"Removing Inactive Role")
    await member.remove_roles(discord.Object(inactive_level_one_id),
                              reason="Member was is no longer considered inactive")

    log.info(f"Getting users roles from DB")
    user_roles: List[pDB.RoleRemovedFromUser] = await pDB.get_roles_tmp_removed_from_user(ctx.bot.db,
                                                                                          ctx.guild.id,
                                                                                          member.id)

    log.info("Restoring removed roles to user")
    roles_unable_to_add = []
    for role in user_roles:
        try:
            await member.add_roles(role, reason="Member was is no longer considered inactive")
        except discord.Forbidden:
            roles_unable_to_add.append(role)
            log.info("Could not add all roles due to permissions")

    if len(roles_unable_to_add) > 0:
        guild: discord.Guild = ctx.guild
        unaddable_roles_str = ""
        for raw_role in roles_unable_to_add:
            role = guild.get_role(raw_role.id)
            unaddable_roles_str += f"{role.mention}, "
        await ctx.send(embed=pn_embed(title=f"**Unable to add back the following roles to {member.display_name}**",
                                      desc=unaddable_roles_str))

    log.info("Removing stored roles from DB")
    await pDB.delete_inactive_member_removed_roles(ctx.bot.db, ctx.guild.id, member.id)

    await pDB.add_inactivity_event(ctx.bot.db, ctx.guild.id, member.id, 0, 1, None)
    log.info("Restoration Complete")


async def move_member_into_isolation_room(ctx: commands.Context, member: Union[discord.User, discord.Member], isolation_role: Union[discord.Role, discord.Object], reason="", inactive_event=False, cooldown_event=False):

    log.info(f"Getting users roles from Discord")
    user_roles: List[discord.Role] = member.roles[1:]  # Get all the roles EXCEPT @everyone.

    log.info("Adding removed roles to DB")
    roles_to_remove = []
    for role in user_roles:
        roles_to_remove.append(role)
        await pDB.add_role_tmp_removed_from_user(ctx.bot.db, ctx.guild.id, member.id, role.id)

    log.info("Removing roles from user")
    roles_unable_to_remove = []
    for role in roles_to_remove:
        try:
            await member.remove_roles(role, reason=reason)
        except discord.Forbidden:
            roles_unable_to_remove.append(role)
            log.info("Could not remove all roles due to permissions")
    log.info("Member Isolation Complete. Adding Isolation Role")

    if len(roles_unable_to_remove) > 0:
        unremovable_roles_str = ""
        for role in roles_unable_to_remove:
            unremovable_roles_str += f"{role.mention}, "
        await ctx.send(embed=pn_embed(title=f"**Unable to remove the following roles from {member.display_name}**",
                                      desc=unremovable_roles_str))

    await member.add_roles(isolation_role, reason=reason)

    if inactive_event:
        await pDB.add_inactivity_event(ctx.bot.db, ctx.guild.id, member.id, current_level=1, previous_level=0, reason=None)
        welcome_back_channel_id: int = ctx.bot.guild_setting(ctx.guild.id, 'welcome_back_channel_id')
        guild: discord.Guild = ctx.guild
        welcome_back_ch: discord.TextChannel = guild.get_channel(welcome_back_channel_id)
        if welcome_back_ch is not None:
            await welcome_back_ch.send("\N{Waving Hand Sign}")
            await welcome_back_ch.send(f"Hey there! Long time no see {member.display_name}!!!!\n"
                                       f"\N{ZERO WIDTH SPACE}\n"
                                       f"No worries, you're not in trouble or anything, you've just been moved to this channel since it's been a while since you last spoke here at Nest. This way we can better protect our members.\n"
                                       f"\N{ZERO WIDTH SPACE}\n"
                                       f"You're still more than welcome here and we would absolutely love to get to talk to you again \N{Slightly Smiling Face}\n"
                                       f"Just say hi and a staff member will restore your access to the rest of the server.")


async def move_member_out_of_isolation_room(ctx: commands.Context, member: Union[discord.User, discord.Member], isolation_role: Union[discord.Role, discord.Object], reason="", inactive_event=False, cooldown_event=False):


    log.info(f"Removing Isolation Role {isolation_role}")
    await member.remove_roles(isolation_role, reason=reason)

    log.info(f"Getting users roles from DB")
    user_roles: List[pDB.RoleRemovedFromUser] = await pDB.get_roles_tmp_removed_from_user(ctx.bot.db,
                                                                                          ctx.guild.id,
                                                                                          member.id)

    log.info("Restoring removed roles to user")
    roles_unable_to_add = []
    for role in user_roles:
        try:
            await member.add_roles(role, reason=reason)
        except discord.Forbidden:
            roles_unable_to_add.append(role)
            log.info("Could not add all roles due to permissions")

    if len(roles_unable_to_add) > 0:
        guild: discord.Guild = ctx.guild
        unaddable_roles_str = ""
        for raw_role in roles_unable_to_add:
            role = guild.get_role(raw_role.id)
            unaddable_roles_str += f"{role.mention}, "
        await ctx.send(embed=pn_embed(title=f"**Unable to add back the following roles to {member.display_name}**",
                                      desc=unaddable_roles_str))

    log.info("Removing stored roles from DB")
    await pDB.delete_inactive_member_removed_roles(ctx.bot.db, ctx.guild.id, member.id)

    if inactive_event:
        await pDB.add_inactivity_event(ctx.bot.db, ctx.guild.id, member.id, 0, 1, None)

    log.info("Restoration Complete")



class IsolateInactiveMembers:
    navigation_buttons = [
        # ("\N{Leftwards Black Arrow}", "left_button"),
        ("\N{Black Rightwards Arrow}", "right_button"),
    ]

    confirmation_buttons = [
        ("\N{Bar Chart}", "show_list"),
        ("✅", "accept_button"),
    ]

    def __init__(self, bot: 'PNBot'):

        self.bot: 'PNBot' = bot
        self.pool: asyncpg.pool.Pool = bot.db

        self.buttons = self.navigation_buttons[:]

        # Vars that get dealt with later
        self.ctx: Optional[commands.Context] = None
        self.ui: Optional[StringReactPage] = None
        # self.embed = pn_embed()

        self.selected_filters = {}
        self.selected_filters_text_list = ["Current Search Parameters:"]

        self.messages = None
        self.selected_inactive_members = []
        self.showing_user_list = False


    @property
    def current_parameters(self):
        return "\n".join(self.selected_filters_text_list)

    async def run(self, ctx: commands.Context):
        """Initializes remaining variables and starts the command."""
        self.ctx = ctx

        # self.ui = StringReactPage(embed=self.embed, buttons=self.buttons, remove_msgs=False, edit_in_place=True)
        self.ui = StringReactPage(embed=pn_embed(), buttons=self.buttons, remove_msgs=False, edit_in_place=True)

        should_cont = await self.memberPostSearchDepthQuestion()
        if not should_cont:
            return await self.canceled()

        if self.selected_filters['last_active'] is not None:
            last_active: datetime = self.selected_filters['last_active']
            last_active_msg = f" since {last_active.strftime('%b %d, %Y')}"
        else:
            last_active: datetime = dateparser.parse("2000-01-01")
            last_active_msg = f" out of all post stored by PNBot"

        should_cont = await self.memberPostQuantityQuestion()
        if not should_cont:
            return await self.canceled()

        should_cont = await self.memberJoinDateQuestion()
        if not should_cont:
            return await self.canceled()

        earliest_join_date = self.selected_filters['join_date'] if self.selected_filters['join_date'] is not None else None
        latest_join_date = datetime.utcnow() - timedelta(days=1)
        await self.display_processing_msg()

        inactive_level_one_id: List[int] = ctx.bot.guild_setting(ctx.guild.id, 'inactive_level_one_role_id')  # 815335443285147679
        inactive_level_two_id: List[int] = ctx.bot.guild_setting(ctx.guild.id, 'inactive_level_two_role_id')  # 815335449194659911
        member_role = ctx.bot.guild_setting(ctx.guild.id, 'member_role_id')
        staff_role_id = ctx.bot.guild_setting(ctx.guild.id, 'team_role_id')


        guild: discord.Guild = ctx.guild
        guild_members = guild.fetch_members(limit=None)  # Using the API call because we want to be sure we get all the members.
        members_to_check = []
        inactive_members = []
        async for member in guild_members:
            member: discord.Member
            is_member = discord.utils.get(member.roles, id=member_role)
            is_team = discord.utils.get(member.roles, id=staff_role_id)
            if not member.bot and is_member is not None:  # and is_team is not None:
                in_inact_one = discord.utils.get(member.roles, id=inactive_level_one_id)
                in_inact_two = discord.utils.get(member.roles, id=inactive_level_two_id)
                if in_inact_one is None and in_inact_two is None:
                    if member.joined_at < latest_join_date and (earliest_join_date is None or member.joined_at > earliest_join_date):
                        members_to_check.append(member)
                        messages = await pDB.get_cached_messages_after_timestamp(self.pool, last_active, guild.id, member.id)
                        active = discord.utils.get(messages, user_id=member.id)
                        if not active:

                                join_date_msg = f"Joined: {member.joined_at.strftime('%b %d, %Y')}" if member.joined_at is not None else "Could not determine when they joined."
                                inact_mem_text = f"<@!{member.id}> - {member.name}#{member.discriminator}, Posts: **{len(messages)}**{last_active_msg},  {join_date_msg}"
                                inactive_members.append((member, inact_mem_text))


        inactive_members.sort(key=lambda x: x[0].joined_at, reverse=True)
        self.selected_inactive_members = inactive_members

        should_cont = await self.confirm_selected_parameters(len(inactive_members))
        if not should_cont:
            return await self.canceled()

        self.selected_inactive_members = self.selected_inactive_members[:self.selected_filters['member_count']]

        inactive_members = self.selected_inactive_members
        for i, (inactive_member, inact_str) in enumerate(inactive_members):
            if i % 1 == 0:
                await self.display_moving_users_msg(inactive_member, i, len(inactive_members))
            await isolate_inactive_member(ctx, inactive_member, [])

        await self.display_moving_users_msg(None, len(inactive_members), len(inactive_members))

        # Clean up and remove the reactions
        # status_embed = pn_embed(title=f"{len(inactive_members)} members isolated", desc=f"{len(inactive_members)} members isolated")
        # await self.ui.finish(status_embed)
        await self.ui.finish()
        await self.show_paginated_user_list()



    async def canceled(self):
        last_embed = pn_embed(title="❌ Isolating Inactive Members Canceled!",
                              desc=f"No Members have been moved to **{'Welcome Back'}**")
        await self.ui.finish(last_embed=last_embed)


    async def show_paginated_user_list(self):
        page_header = f"Inactive Member List"
        # inactive_members_text.insert(0, page_header)
        page = UnnumberedPages(ctx=self.ctx, entries=[x[1][:133] for x in self.selected_inactive_members], per_page=15)
        page.embed.title = page_header  # "Search Complete!"
        page.embed.color = pn_orange()
        await page.paginate()

    async def display_processing_msg(self):
        embed = pn_embed(title="Searching for inactive members",
                         desc=f"Processing.... This may take a while....\n{self.current_parameters}\n\N{ZERO WIDTH SPACE}\n")
        await self.ui.page_message.edit(embed=embed)

    async def display_moving_users_msg(self, member, members_moved: int, total_members_to_be_moved: int):
        member_str = member.display_name if member is not None else "."
        embed = pn_embed(title=f"Currently Moving {total_members_to_be_moved} to Welcome Back",
                         desc=f"Moving {member_str}.... This may take a while....\n**{members_moved}** out of **{total_members_to_be_moved}** have been moved to Welcome Back")
        await self.ui.page_message.edit(embed=embed)


    async def memberPostSearchDepthQuestion(self, error_msg_embed: Optional[discord.Embed] = None):
        """

        :param error_msg_embed: The function can be called recursively if the user enters invalid input. This parameter should contain the error message embed in that case.
        :type error_msg_embed:
        :return:
        :rtype:
        """
        log.info(f"Running memberPostSearchDepthQuestion")
        self.ui.embed = error_msg_embed or pn_embed(title="Setting Inactivity Parameters",
                        desc=f"How far back should we search for member posts?\n\nReact to \N{Black Rightwards Arrow} to search all stored posts.")

        # self.ui = StringReactPage(embed=self.embed, buttons=self.buttons, remove_msgs=False, edit_in_place=True)

        response = await self.ui.run(self.ctx)#, new_embed=error_msg_embed)
        if response is None:
            return False

        if response.c() == 'right_button':
            self.selected_filters['last_active'] = None
            self.selected_filters_text_list.append(f"Searching through messages since: **All**")
            return True

        la_timestamp = dateparser.parse(response.c(), settings={'TIMEZONE': 'UTC'})

        if la_timestamp is None:
            return await self.memberPostSearchDepthQuestion(pn_embed(
                title="Setting Inactivity Parameters",
                desc=f"Error! Unable to determine when {response.c()} is! Please try again or skip to the next question.\n\nHow far back should we search for member posts?\n\nReact to \N{Black Rightwards Arrow} to search all stored posts."
            ))

        if la_timestamp > datetime.utcnow():
            return await self.memberPostSearchDepthQuestion(pn_embed(
                title="Setting Inactivity Parameters",
                desc=f"Error! {response.c()} is in the future!!! Please try again or skip to the next question.\n\nHow far back should we search for member posts?\n\nReact to \N{Black Rightwards Arrow} to search all stored posts."
            ))


        self.selected_filters['last_active'] = la_timestamp
        self.selected_filters_text_list.append(f"Searching through messages since: **{self.selected_filters['last_active'].strftime('%b %d, %Y')}**")
        return True


    async def memberPostQuantityQuestion(self, error_msg_embed: Optional[discord.Embed] = None):
        """

        :param error_msg_embed: The function can be called recursively if the user enters invalid input. This parameter should contain the error message embed in that case.
        :type error_msg_embed:
        :return:
        :rtype:
        """
        log.info(f"Running memberPostQuantityQuestion")
        if self.selected_filters['last_active'] is not None:
            embed_desc = f"What's the threshold for maximum number of posts a member could have made since {self.selected_filters['last_active'].strftime('%b %d, %Y')}?\n\N{ZERO WIDTH SPACE}\n" \
                         f"{self.current_parameters}\n\N{ZERO WIDTH SPACE}\n" \
                         f"React to \N{Black Rightwards Arrow} to select the default (0 Posts)."

        else:
            embed_desc = f"What's the threshold for maximum number of posts a member could have made?\n\N{ZERO WIDTH SPACE}\n" \
                         f"{self.current_parameters}\n\N{ZERO WIDTH SPACE}\n" \
                         f"React to \N{Black Rightwards Arrow} to select the default (0 Posts)."

        self.ui.embed = error_msg_embed or pn_embed(title="Setting Inactivity Parameters", desc=embed_desc)

        # self.ui = StringReactPage(embed=self.embed, buttons=self.buttons, remove_msgs=False, edit_in_place=True)

        response = await self.ui.run(self.ctx)#, new_embed=error_msg_embed)
        if response is None:
            return False

        if response.c() == 'right_button':
            self.selected_filters['post_count'] = 0
            self.selected_filters_text_list.append(f"Members who have made less than **0** posts in the search timespan")
            return True

        try:
            post_count = int(response.c())

        except ValueError:
            return await self.memberPostQuantityQuestion(pn_embed(
                title="Setting Inactivity Parameters",
                desc=f"Error! Unable to convert {response.c()} to a number! Please try again or skip to the next question.\n\N{ZERO WIDTH SPACE}\n{embed_desc}"
            ))


        self.selected_filters['post_count'] = post_count
        self.selected_filters_text_list.append(f"Members who have made less than **{post_count}** posts in the search timespan.")
        return True


    async def memberJoinDateQuestion(self, error_msg_embed: Optional[discord.Embed] = None):
        """

        :param error_msg_embed: The function can be called recursively if the user enters invalid input. This parameter should contain the error message embed in that case.
        :type error_msg_embed:
        :return:
        :rtype:
        """
        log.info(f"Running memberJoinDateQuestion")
        embed_desc = f"What's the cutoff time for when a member joined?\n\N{ZERO WIDTH SPACE}\n" \
                     f"{self.current_parameters}\n\N{ZERO WIDTH SPACE}\n" \
                     f"React to \N{Black Rightwards Arrow} to select the default (No Cutoff)."

        self.ui.embed = error_msg_embed or pn_embed(title="Setting Inactivity Parameters", desc=embed_desc)

        # self.ui = StringReactPage(embed=self.embed, buttons=self.buttons, remove_msgs=False, edit_in_place=True)

        response = await self.ui.run(self.ctx) #, new_embed=error_msg_embed)
        if response is None:
            return False

        if response.c() == 'right_button':
            self.selected_filters['join_date'] = None
            self.selected_filters_text_list.append(f"Members who joined after: **N/A**")
            return True


           # if time_on_pn is None or member.joined_at > time_on_pn:
           #          inactive_members.append(member)

        join_timestamp = dateparser.parse(response.c(), settings={'TIMEZONE': 'UTC'})

        if join_timestamp is None:
            return await self.memberJoinDateQuestion(pn_embed(
                title="Setting Inactivity Parameters",
                desc=f"Error! Unable to determine when {response.c()} is! Please try again or skip to the next question.\n\N{ZERO WIDTH SPACE}\n{embed_desc}"
            ))


        if join_timestamp > datetime.utcnow():
            return await self.memberJoinDateQuestion(pn_embed(
                title="Setting Inactivity Parameters",
                desc=f"Error! {response.c()} is in the future!!! Please try again or skip to the next question.\n\N{ZERO WIDTH SPACE}\n{embed_desc}"
            ))


        self.selected_filters['join_date'] = join_timestamp
        self.selected_filters_text_list.append(
            f"Members who joined after: **{self.selected_filters['join_date'].strftime('%b %d, %Y')}**")

        return True


    async def confirm_selected_parameters(self, num_of_members_found: int, error_msg_embed: Optional[discord.Embed] = None, recurse = False):
        """

        :param error_msg_embed: The function can be called recursively if the user enters invalid input. This parameter should contain the error message embed in that case.
        :type error_msg_embed:
        :return:
        :rtype:
        """

        log.info(f"Running confirm_selected_parameters")
        embed_desc = f"We have found **{num_of_members_found}** members that match the search parameters detailed below. \n" \
                     f"{self.current_parameters}\n\N{ZERO WIDTH SPACE}\n" \
                     f"Options:\n" \
                     f"Click on the {self.confirmation_buttons[0][0]} to display the list of inactive members.\n" \
                     f"Click on the {self.confirmation_buttons[1][0]} to move all **{num_of_members_found}** members to **{'Welcome Back'}**.\n" \
                     f"Enter a specific number of members to move to **{'Welcome Back'}**\n" \
                     f"Click on the {self.ui.cancel_emoji} to cancel."

        self.ui.embed = error_msg_embed or pn_embed(title=f"Found {num_of_members_found} Members.", desc=embed_desc)
        if not recurse:
            await self.ui.update_buttons(self.confirmation_buttons)
        response = await self.ui.run(self.ctx)  # , new_embed=error_msg_embed)

        if response is None:
            return False

        if response.c() == 'accept_button':
            self.selected_filters['member_count'] = num_of_members_found
            self.selected_filters_text_list.append(f"All Inactive Members")
            return True

        if response.c() == 'show_list':
            if not self.showing_user_list:
                self.showing_user_list = True
                await self.show_paginated_user_list()
            return await self.confirm_selected_parameters(num_of_members_found, recurse=True)

        try:
            member_count = int(response.c())
        except ValueError:
            return await self.confirm_selected_parameters(num_of_members_found, pn_embed(
                title=f"Found {num_of_members_found} Members.",
                desc=f"Error! Unable to convert {response.c()} to a number! Please try again or choose a different option.\n\N{ZERO WIDTH SPACE}\n{embed_desc}"
            ), recurse=True)

        self.selected_filters['member_count'] = member_count
        self.selected_filters_text_list.append(f"Limiting to the **{member_count}** most recent inactive members.")

        return True


class IsolateInactiveStaff:
    navigation_buttons = [
        # ("\N{Leftwards Black Arrow}", "left_button"),
        ("\N{Black Rightwards Arrow}", "right_button"),
    ]

    confirmation_buttons = [
        ("\N{Bar Chart}", "show_list"),
        # ("✅", "accept_button"),
    ]

    def __init__(self, bot: 'PNBot'):

        self.bot: 'PNBot' = bot
        self.pool: asyncpg.pool.Pool = bot.db

        self.buttons = self.navigation_buttons[:]

        # Vars that get dealt with later
        self.ctx: Optional[commands.Context] = None
        self.ui: Optional[StringReactPage] = None
        # self.embed = pn_embed()

        self.staff_role_id = 0

        self.selected_filters = {}
        self.selected_filters_text_list = ["Current Search Parameters:"]

        self.messages = None
        self.selected_inactive_members = []
        self.showing_user_list = False


    @property
    def current_parameters(self):
        return "\n".join(self.selected_filters_text_list)

    async def run(self, ctx: commands.Context):
        """Initializes remaining variables and starts the command."""
        self.ctx = ctx

        self.staff_role_id = self.ctx.bot.guild_setting(self.ctx.guild.id, 'team_role_id')
        self.selected_filters_text_list.append(f"Is a Staff Member (Has the <@&{self.staff_role_id}> Role)")


        # self.ui = StringReactPage(embed=self.embed, buttons=self.buttons, remove_msgs=False, edit_in_place=True)
        self.ui = StringReactPage(embed=pn_embed(), buttons=self.buttons, remove_msgs=False, edit_in_place=True)

        should_cont = await self.memberPostSearchDepthQuestion()
        if not should_cont:
            return await self.canceled()

        last_active: datetime = self.selected_filters['last_active'] if self.selected_filters['last_active'] is not None else dateparser.parse("2019-01-01")

        should_cont = await self.memberPostQuantityQuestion()
        if not should_cont:
            return await self.canceled()

        should_cont = await self.memberJoinDateQuestion()
        if not should_cont:
            return await self.canceled()

        earliest_join_date = self.selected_filters['join_date'] if self.selected_filters['join_date'] is not None else None
        latest_join_date = datetime.utcnow() - timedelta(days=1)
        await self.display_processing_msg()

        # inactive_level_one_id: List[int] = ctx.bot.guild_setting(ctx.guild.id, 'inactive_level_one_role_id')  # 815335443285147679
        # inactive_level_two_id: List[int] = ctx.bot.guild_setting(ctx.guild.id, 'inactive_level_two_role_id')  # 815335449194659911

        member_role = ctx.bot.guild_setting(ctx.guild.id, 'member_role_id')
        staff_role_id = ctx.bot.guild_setting(ctx.guild.id, 'team_role_id')


        guild: discord.Guild = ctx.guild
        guild_members = guild.fetch_members(limit=None)  # Using the API call because we want to be sure we get all the members.
        members_to_check = []
        inactive_members = []
        async for member in guild_members:
            member: discord.Member
            is_member = discord.utils.get(member.roles, id=member_role)
            is_team = discord.utils.get(member.roles, id=staff_role_id)
            if not member.bot and is_team is not None:
                in_inact_one = None  # discord.utils.get(member.roles, id=inactive_level_one_id)
                in_inact_two = None  # discord.utils.get(member.roles, id=inactive_level_two_id)
                if in_inact_one is None and in_inact_two is None:
                    if member.joined_at < latest_join_date and (earliest_join_date is None or member.joined_at > earliest_join_date):
                        members_to_check.append(member)
                        messages = await pDB.get_cached_messages_after_timestamp(self.pool, last_active, guild.id, member.id)
                        active = discord.utils.get(messages, user_id=member.id)
                        if not active:
                                join_date_msg = f"Joined: {member.joined_at.strftime('%b %d, %Y')}" if member.joined_at is not None else "Could not determine when they joined."
                                inact_mem_text = f"<@!{member.id}> - {member.name}#{member.discriminator}, Posts: **{len(messages)}** since {last_active.strftime('%b %d, %Y')}, {join_date_msg}"
                                inactive_members.append((member, inact_mem_text))

        inactive_members.sort(key=lambda x: x[0].joined_at, reverse=True)
        self.selected_inactive_members = inactive_members

        await self.ui.finish()
        await self.show_paginated_user_list()
        return

        should_cont = await self.confirm_selected_parameters(len(inactive_members))


        if not should_cont:
            return await self.canceled()

        self.selected_inactive_members = self.selected_inactive_members[:self.selected_filters['member_count']]

        inactive_members = self.selected_inactive_members
        for i, (inactive_member, inact_str) in enumerate(inactive_members):
            if i % 1 == 0:
                await self.display_moving_users_msg(inactive_member, i, len(inactive_members))
            await isolate_inactive_member(ctx, inactive_member, [])

        await self.display_moving_users_msg(None, len(inactive_members), len(inactive_members))

        # Clean up and remove the reactions
        # status_embed = pn_embed(title=f"{len(inactive_members)} members isolated", desc=f"{len(inactive_members)} members isolated")
        # await self.ui.finish(status_embed)
        await self.ui.finish()
        await self.show_paginated_user_list()



    # async def canceled(self):
    #     last_embed = pn_embed(title="❌ Isolating Inactive Members Canceled!",
    #                           desc=f"No Members have been moved to **{'Welcome Back'}**")
    #     await self.ui.finish(last_embed=last_embed)


    async def canceled(self):
        last_embed = pn_embed(title="❌ Searching for inactive staff canceled!")
        await self.ui.finish(last_embed=last_embed)


    async def show_paginated_user_list(self):
        page_header = f"Inactive Staff List"
        # inactive_members_text.insert(0, page_header)
        page = UnnumberedPages(ctx=self.ctx, entries=[x[1][:133] for x in self.selected_inactive_members], per_page=15)
        page.embed.title = page_header  # "Search Complete!"
        page.embed.color = pn_orange()
        await page.paginate()

    async def display_processing_msg(self):
        embed = pn_embed(title="Searching for inactive staff",
                         desc=f"Processing.... This may take a while....\n{self.current_parameters}\n\N{ZERO WIDTH SPACE}\n")
        await self.ui.page_message.edit(embed=embed)

    # async def display_moving_users_msg(self, member, members_moved: int, total_members_to_be_moved: int):
    #     member_str = member.display_name if member is not None else "."
    #     embed = pn_embed(title=f"Currently Moving {total_members_to_be_moved} to Welcome Back",
    #                      desc=f"Moving {member_str}.... This may take a while....\n**{members_moved}** out of **{total_members_to_be_moved}** have been moved to Welcome Back")
    #     await self.ui.page_message.edit(embed=embed)


    async def memberPostSearchDepthQuestion(self, error_msg_embed: Optional[discord.Embed] = None):
        """

        :param error_msg_embed: The function can be called recursively if the user enters invalid input. This parameter should contain the error message embed in that case.
        :type error_msg_embed:
        :return:
        :rtype:
        """
        log.info(f"Running memberPostSearchDepthQuestion")
        self.ui.embed = error_msg_embed or pn_embed(title="Setting Inactivity Parameters",
                        desc=f"How far back should we search for staff posts?\n\nReact to \N{Black Rightwards Arrow} to search all stored posts.")

        # self.ui = StringReactPage(embed=self.embed, buttons=self.buttons, remove_msgs=False, edit_in_place=True)

        response = await self.ui.run(self.ctx)#, new_embed=error_msg_embed)
        if response is None:
            return False

        if response.c() == 'right_button':
            self.selected_filters['last_active'] = None
            self.selected_filters_text_list.append(f"Searching through messages since: **All**")
            return True

        la_timestamp = dateparser.parse(response.c(), settings={'TIMEZONE': 'UTC'})

        if la_timestamp is None:
            return await self.memberPostSearchDepthQuestion(pn_embed(
                title="Setting Inactivity Parameters",
                desc=f"Error! Unable to determine when {response.c()} is! Please try again or skip to the next question.\n\nHow far back should we search for staff posts?\n\nReact to \N{Black Rightwards Arrow} to search all stored posts."
            ))

        if la_timestamp > datetime.utcnow():
            return await self.memberPostSearchDepthQuestion(pn_embed(
                title="Setting Inactivity Parameters",
                desc=f"Error! {response.c()} is in the future!!! Please try again or skip to the next question.\n\nHow far back should we search for staff posts?\n\nReact to \N{Black Rightwards Arrow} to search all stored posts."
            ))


        self.selected_filters['last_active'] = la_timestamp
        self.selected_filters_text_list.append(f"Searching through messages since: **{self.selected_filters['last_active'].strftime('%b %d, %Y')}**")
        return True


    async def memberPostQuantityQuestion(self, error_msg_embed: Optional[discord.Embed] = None):
        """

        :param error_msg_embed: The function can be called recursively if the user enters invalid input. This parameter should contain the error message embed in that case.
        :type error_msg_embed:
        :return:
        :rtype:
        """
        log.info(f"Running memberPostQuantityQuestion")
        if self.selected_filters['last_active'] is not None:
            embed_desc = f"What's the threshold for maximum number of posts a staff could have made since {self.selected_filters['last_active'].strftime('%b %d, %Y')}?\n\N{ZERO WIDTH SPACE}\n" \
                         f"{self.current_parameters}\n\N{ZERO WIDTH SPACE}\n" \
                         f"React to \N{Black Rightwards Arrow} to select the default (0 Posts)."

        else:
            embed_desc = f"What's the threshold for maximum number of posts a staff could have made?\n\N{ZERO WIDTH SPACE}\n" \
                         f"{self.current_parameters}\n\N{ZERO WIDTH SPACE}\n" \
                         f"React to \N{Black Rightwards Arrow} to select the default (0 Posts)."

        self.ui.embed = error_msg_embed or pn_embed(title="Setting Inactivity Parameters", desc=embed_desc)

        # self.ui = StringReactPage(embed=self.embed, buttons=self.buttons, remove_msgs=False, edit_in_place=True)

        response = await self.ui.run(self.ctx)#, new_embed=error_msg_embed)
        if response is None:
            return False

        if response.c() == 'right_button':
            self.selected_filters['post_count'] = 0
            self.selected_filters_text_list.append(f"Staff who have made less than **0** posts in the search timespan")
            return True

        try:
            post_count = int(response.c())

        except ValueError:
            return await self.memberPostQuantityQuestion(pn_embed(
                title="Setting Inactivity Parameters",
                desc=f"Error! Unable to convert {response.c()} to a number! Please try again or skip to the next question.\n\N{ZERO WIDTH SPACE}\n{embed_desc}"
            ))


        self.selected_filters['post_count'] = post_count
        self.selected_filters_text_list.append(f"Staff who have made less than **{post_count}** posts in the search timespan.")
        return True


    async def memberJoinDateQuestion(self, error_msg_embed: Optional[discord.Embed] = None):
        """

        :param error_msg_embed: The function can be called recursively if the user enters invalid input. This parameter should contain the error message embed in that case.
        :type error_msg_embed:
        :return:
        :rtype:
        """
        log.info(f"Running memberJoinDateQuestion")
        embed_desc = f"What's the cutoff time for when a staff joined?\n\N{ZERO WIDTH SPACE}\n" \
                     f"{self.current_parameters}\n\N{ZERO WIDTH SPACE}\n" \
                     f"React to \N{Black Rightwards Arrow} to select the default (No Cutoff)."

        self.ui.embed = error_msg_embed or pn_embed(title="Setting Inactivity Parameters", desc=embed_desc)

        # self.ui = StringReactPage(embed=self.embed, buttons=self.buttons, remove_msgs=False, edit_in_place=True)

        response = await self.ui.run(self.ctx) #, new_embed=error_msg_embed)
        if response is None:
            return False

        if response.c() == 'right_button':
            self.selected_filters['join_date'] = None
            self.selected_filters_text_list.append(f"Staff who joined after: **N/A**")
            return True


           # if time_on_pn is None or member.joined_at > time_on_pn:
           #          inactive_members.append(member)

        join_timestamp = dateparser.parse(response.c(), settings={'TIMEZONE': 'UTC'})

        if join_timestamp is None:
            return await self.memberJoinDateQuestion(pn_embed(
                title="Setting Inactivity Parameters",
                desc=f"Error! Unable to determine when {response.c()} is! Please try again or skip to the next question.\n\N{ZERO WIDTH SPACE}\n{embed_desc}"
            ))


        if join_timestamp > datetime.utcnow():
            return await self.memberJoinDateQuestion(pn_embed(
                title="Setting Inactivity Parameters",
                desc=f"Error! {response.c()} is in the future!!! Please try again or skip to the next question.\n\N{ZERO WIDTH SPACE}\n{embed_desc}"
            ))


        self.selected_filters['join_date'] = join_timestamp
        self.selected_filters_text_list.append(
            f"Staff who joined after: **{self.selected_filters['join_date'].strftime('%b %d, %Y')}**")

        return True


    async def confirm_selected_parameters(self, num_of_members_found: int, error_msg_embed: Optional[discord.Embed] = None, recurse = False):
        """

        :param error_msg_embed: The function can be called recursively if the user enters invalid input. This parameter should contain the error message embed in that case.
        :type error_msg_embed:
        :return:
        :rtype:
        """

        log.info(f"Running confirm_selected_parameters")
        embed_desc = f"We have found **{num_of_members_found}** Staff that match the search parameters detailed below. \n" \
                     f"{self.current_parameters}\n\N{ZERO WIDTH SPACE}\n" \
                     f"Click on the {self.confirmation_buttons[0][0]} to display the list of inactive Staff.\n"

                     # f"Options:\n" \
                     # f"Click on the {self.confirmation_buttons[0][0]} to display the list of inactive Staff.\n" \
                     # f"Click on the {self.confirmation_buttons[1][0]} to move all **{num_of_members_found}** members to **{'Welcome Back'}**.\n" \
                     # f"Enter a specific number of members to move to **{'Welcome Back'}**\n" \
                     # f"Click on the {self.ui.cancel_emoji} to cancel."

        self.ui.embed = error_msg_embed or pn_embed(title=f"Found {num_of_members_found} Members.", desc=embed_desc)
        # if not recurse:
        #     await self.ui.update_buttons(self.confirmation_buttons)
        response = await self.ui.run(self.ctx)  # , new_embed=error_msg_embed)

        if response is None:
            return False

        # if response.c() == 'accept_button':
        #     self.selected_filters['member_count'] = num_of_members_found
        #     self.selected_filters_text_list.append(f"All Inactive Members")
        #     return True

        if response.c() == 'show_list':
            if not self.showing_user_list:
                self.showing_user_list = True
                await self.show_paginated_user_list()
            return await self.confirm_selected_parameters(num_of_members_found, recurse=True)

        # try:
        #     member_count = int(response.c())
        # except ValueError:
        #     return await self.confirm_selected_parameters(num_of_members_found, pn_embed(
        #         title=f"Found {num_of_members_found} Members.",
        #         desc=f"Error! Unable to convert {response.c()} to a number! Please try again or choose a different option.\n\N{ZERO WIDTH SPACE}\n{embed_desc}"
        #     ), recurse=True)
        #
        # self.selected_filters['member_count'] = member_count
        # self.selected_filters_text_list.append(f"Limiting to the **{member_count}** most recent inactive members.")

        return True


class UserManagement(commands.Cog):

    def __init__(self, bot):

        self.bot: 'PNBot' = bot
        self.pool: asyncpg.pool.Pool = bot.db

    """ --- on_* Listener Functions --- """
# region on_DiscordEvent Listener Functions

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        author: Union[discord.Member, discord.User] = message.author

        if author.id != self.bot.user.id and message.guild is not None:  # Don't log our own messages or DM messages.
            # if not author.bot:
            message_contents = message.content if message.content != '' else None

            if message_contents is not None or len(message.attachments) > 0:
                msg_con = message_contents

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


    @commands.Cog.listener()
    async def on_member_join(self, member: Union[discord.User, discord.Member]):
        log.info(f"Member Joined. Logging.")
        await pDB.add_join_event(self.pool, member.guild.id, member.id)
        await asyncio.sleep(10)
        # TODO: Find and parse the GG Join Log


    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        log.info(f"The role {role.name} was deleted from {role.guild.name}")
        await pDB.delete_role_tmp_removed_from_all_user(self.pool, role.guild.id, role.id)


    """ --- on_* Listener Helper Functions --- """

    @staticmethod
    def verify_message_is_preproxy_message(message_id: int, pk_response: Dict) -> bool:
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

# endregion

    """                                '''
    --- Isolate Inactive User Commands ---
    """


    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    @eCommands.command(name="find_inactive_staff", aliases=["show_inactive_staff"],
                       brief="Finds inactive Staff",
                       examples=[''],
                       category="User Management")
    async def isolate_all_inactive_staff(self, ctx: commands.Context):

        ui = IsolateInactiveStaff(self.bot)
        await ui.run(ctx)



    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    @eCommands.command(name="find_and_move_inactive", aliases=["isolate_inact"],
                       brief="Finds and moves inactive members",
                       examples=[''],
                       category="User Management")
    async def isolate_all_inactive(self, ctx: commands.Context):

        ui = IsolateInactiveMembers(self.bot)
        await ui.run(ctx)


    @is_team_member()
    @commands.guild_only()
    @eCommands.command(name="welcome_back", aliases=["restore_member", "restore_members"],
                       brief="Restores membership to indicated members.",
                       examples=[''],
                       category="User Management")
    async def restore_members(self, ctx: commands.Context, members: commands.Greedy[discord.Member]):
        inactive_level_one_id: int = ctx.bot.guild_setting(ctx.guild.id, 'inactive_level_one_role_id')
        inactive_level_two_id: int = ctx.bot.guild_setting(ctx.guild.id, 'inactive_level_two_role_id')

        embed = pn_embed(f"Moving {len(members)} Members out of Welcome Back.", f"Working.... Please Wait....")
        msg = await ctx.send(embed=embed)

        activated_members = []
        for i, member in enumerate(members):
            member: Union[discord.Member, discord.User]
            inactive_role_ids: List[int] = [inactive_level_one_id, inactive_level_two_id]
            for inactive_role_id in inactive_role_ids:
                currently_inactive = discord.utils.get(member.roles, id=inactive_role_id)
                if currently_inactive is not None:

                    embed = pn_embed(f"Welcoming {len(members)} members.", f"Restoring access for {member.display_name}.\nWorking.... Please Wait.... {i+1}/{len(members)}.")
                    await msg.edit(embed=embed)
                    await restore_inactive_member(ctx, member)

                    activated_members.append(member)
                else:
                    await ctx.send(embed=pn_embed(title="Warning!", desc=f"{member.display_name} is not in #Welcome Back!"))
                    activated_members.append(member)

        if len(activated_members) < 1:
            embed = pn_embed("Error! Could not restore access! Please attempt to do so manually.")
        elif len(activated_members) != len(members):
            embed = pn_embed(f"Error! Could not restore access for {len(members) - len(activated_members)} members! Please attempt to do so manually.")
        elif len(activated_members) == 1:
            embed = pn_embed(f"Welcome Back {members[0].display_name}!")
        else:
            embed = pn_embed(f"Welcome Back Everyone!.",
                             f"Restored Access for {len(activated_members)} Members.")
        await msg.edit(embed=embed)


    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    @eCommands.command(name="mark_inactive", aliases=["isolate_member", "isolate_members"],
                       brief="Moves the indicated members to Inactive Channel.",
                       examples=['@Hibiki @Beryl'],
                       category="User Management")
    async def isolate_members(self, ctx: commands.Context, members: commands.Greedy[discord.Member]):
        inactive_level_one_id: int = ctx.bot.guild_setting(ctx.guild.id, 'inactive_level_one_role_id')
        inactive_level_two_id: int = ctx.bot.guild_setting(ctx.guild.id, 'inactive_level_two_role_id')

        embed = pn_embed(f"Moving {len(members)} Members to Welcome Back.", f"Working.... Please Wait....")
        msg = await ctx.send(embed=embed)

        moved_members = []
        for i, member in enumerate(members):
            member: Union[discord.Member, discord.User]
            # inactive_role_ids: List[int] = [inactive_level_one_id, inactive_level_two_id]
            # for inactive_role_id in inactive_role_ids:
            currently_inactive_1 = discord.utils.get(member.roles, id=inactive_level_one_id)
            currently_inactive_2 = discord.utils.get(member.roles, id=inactive_level_two_id)

            if currently_inactive_1 is None and currently_inactive_2 is None:
                embed = pn_embed(f"Moving {len(members)} members to Welcome Back.",
                                 f"Moving {member.display_name} to Welcome Back.\nWorking.... Please Wait.... Moving Member #{i + 1} / {len(members)}.")
                await msg.edit(embed=embed)

                await isolate_inactive_member(ctx, member, [])
                # await self.temp_remove_roles(ctx, member, "Member has been determined to be inactive.", [])
                # await member.add_roles(discord.Object(inactive_level_one_id), reason="Member has been determined to be inactive.")

                moved_members.append(member)

        embed = pn_embed(f"Member Moving Complete.",
                         f"Moved {len(moved_members)} Members into Welcome Back.")
        await msg.edit(embed=embed)



    """                                    '''
    --- Manual Find Inactive User Commands ---
    """

    #
    # @commands.has_permissions(manage_messages=True)
    # @commands.guild_only()
    # @eCommands.group(name="show_inactive_staff", aliases=["find_inactive_staff"],
    #                  brief="Lists all staff who have not posted in a given timeframe and with other filters.",
    #                  category="User Management")
    # async def filtered_inactive_members(self, ctx: commands.Context):
    #     if ctx.invoked_subcommand is None:
    #         await ctx.send_help(self.filtered_inactive_members)
    #
    #
    # @filtered_inactive_members.command(name="join_date",
    #                                    examples=["'2 weeks' '1 year'", "'4/5/2020' '2/9/2020'"])
    # async def by_join_date(self, ctx: commands.Context, last_active: str, time_on_pn: str):
    #     la_timestamp = dateparser.parse(last_active, settings={'TIMEZONE': 'UTC'})
    #     pn_timestamp = dateparser.parse(time_on_pn, settings={'TIMEZONE': 'UTC'})
    #
    #     if la_timestamp is None:
    #         await ctx.send(f"Error! Unable to determine when {la_timestamp} is!")
    #         return
    #
    #     if la_timestamp > datetime.utcnow():
    #         await ctx.send(f"Error! {la_timestamp} is in the future!!!")
    #         return
    #
    #     if pn_timestamp is None:
    #         await ctx.send(f"Error! Unable to determine when {la_timestamp} is!")
    #         return
    #
    #     if pn_timestamp > datetime.utcnow():
    #         await ctx.send(f"Error! {la_timestamp} is in the future!!!")
    #         return
    #
    #     await self.filtered_find_inactive_members(ctx, la_timestamp, pn_timestamp)
    #
    # async def filtered_find_inactive_members(self, ctx: commands.Context, last_active: datetime, time_on_pn: Optional[datetime] = None):
    #
    #     # if time_on_pn is None:
    #     #     time_on_pn = datetime.min
    #
    #     status_msg = await ctx.send(embed=std_embed("Searching for inactive members..",
    #                                                 f"Getting members who have not posted since {last_active.strftime('%b %d, %Y, %I:%M %p UTC')}.\nRetrieving message counts..."))
    #
    #     messages = await pDB.get_all_cached_messages_after_timestamp(self.bot.db, last_active, ctx.guild.id)
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
    #             if time_on_pn is None or member.joined_at > time_on_pn:
    #                 inactive_members.append(member)
    #
    #     inactive_members.sort(key=lambda x: x.joined_at, reverse=True)
    #
    #     for inactive_mem in inactive_members:
    #         time_on_pn_str = self.time_on_pn(inactive_mem)
    #         inactive_members_text.append(
    #             f"<@!{inactive_mem.id}> - {inactive_mem.name}#{inactive_mem.discriminator}: Joined {time_on_pn_str}")
    #
    #     await status_msg.edit(embed=std_embed("Finished searching for inactive members!", ""))
    #
    #     page_header = f"\nThere are {len(inactive_members)} members that have been inactive since {last_active.strftime('%b %d, %Y, %I:%M %p UTC')}.\n  \n"
    #     # inactive_members_text.insert(0, page_header)
    #     page = UnnumberedPages(ctx=ctx, entries=inactive_members_text, per_page=25)
    #     page.embed.title = page_header  # "Search Complete!"
    #     page.embed.color = pn_orange()
    #     await page.paginate()
    #
    # @filtered_inactive_members.command(name="min_posts",
    #                                    examples=["'2 weeks' '0'", "'4/5/2020' '20'"])
    # async def by_min_posts(self, ctx: commands.Context, last_active: str, less_than: int):
    #     la_timestamp = dateparser.parse(last_active, settings={'TIMEZONE': 'UTC'})
    #
    #     if la_timestamp is None:
    #         await ctx.send(f"Error! Unable to determine when {la_timestamp} is!")
    #         return
    #
    #     if la_timestamp > datetime.utcnow():
    #         await ctx.send(f"Error! {la_timestamp} is in the future!!!")
    #         return
    #
    #     await self.filtered_by_post_count_find_inactive_members(ctx, la_timestamp, less_than)
    #
    # async def filtered_by_post_count_find_inactive_members(self, ctx: commands.Context, last_active: datetime, less_than: int):
    #
    #     status_msg = await ctx.send(embed=std_embed("Searching for inactive members..",
    #                                                 f"Getting members who have posted less than {less_than} times since {last_active.strftime('%b %d, %Y, %I:%M %p UTC')}.\nRetrieving message counts..."))
    #
    #     messages = await pDB.get_all_cached_messages_after_timestamp(self.bot.db, last_active, ctx.guild.id)
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
    #     # inactive_members_text = []
    #     guild: discord.Guild = ctx.guild
    #     guild_members = guild.fetch_members(
    #         limit=None)  # Using the API call because we want to be sure we get all the members.
    #     async for member in guild_members:
    #         member: discord.Member
    #         if not member.bot:
    #             posts = list(filter(lambda x: x.user_id == member.id, messages))
    #             if len(posts) < less_than:
    #                 time_on_pn_str = self.time_on_pn(member)
    #                 inactive_members.append((member, f"<@!{member.id}> - {member.name}#{member.discriminator}: Post Count: **{len(posts)}** Joined {time_on_pn_str}"))
    #     inactive_members.sort(key=lambda x: x[0].joined_at, reverse=True)
    #
    #     await status_msg.edit(embed=std_embed("Finished searching for inactive members!", ""))
    #
    #     page_header = f"\nThere are {len(inactive_members)} members that have posted less than {less_than} times since {last_active.strftime('%b %d, %Y, %I:%M %p UTC')}.\n  \n"
    #     # inactive_members_text.insert(0, page_header)
    #     page = UnnumberedPages(ctx=ctx, entries=[x[1] for x in inactive_members], per_page=20)
    #     page.embed.title = page_header  # "Search Complete!"
    #     page.embed.color = pn_orange()
    #     await page.paginate()





    # @commands.has_permissions(manage_messages=True)
    # @commands.guild_only()
    # @eCommands.command(name="inactive_members", aliases=["inactive_mem"],
    #                    brief="Lists all members who have not posted in a given timeframe.",
    #                    examples=['1 day and 6 hours ago', "4/5/2020"],
    #                    category="User Management")
    # async def whos_inactive(self, ctx: commands.Context, *, how_long_ago: str):
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
    #     status_msg = await ctx.send(embed=std_embed("Searching for inactive members..", f"Getting members who have not posted since {timestamp.strftime('%b %d, %Y, %I:%M %p UTC')}.\nRetrieving message counts..."))
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
    #     guild_members = guild.fetch_members(limit=None)  # Using the API call because we want to be sure we get all the members.
    #     async for member in guild_members:
    #         member: discord.Member
    #         active = discord.utils.get(messages, user_id=member.id)
    #         if not active and not member.bot:
    #             inactive_members.append(member)
    #
    #     inactive_members.sort(key=lambda x: x.joined_at, reverse=True)
    #     for inactive_mem in inactive_members:
    #         time_on_pn_str = self.time_on_pn(inactive_mem)
    #         inactive_members_text.append(f"<@!{inactive_mem.id}> - {inactive_mem.name}#{inactive_mem.discriminator}: Joined {time_on_pn_str}")
    #
    #     await status_msg.edit(embed=std_embed("Finished searching for inactive members!", ""))
    #
    #     page_header = f"\nThere are {len(inactive_members)} members that have been inactive since {timestamp.strftime('%b %d, %Y, %I:%M %p UTC')}.\n  \n"
    #     # inactive_members_text.insert(0, page_header)
    #     page = UnnumberedPages(ctx=ctx, entries=inactive_members_text, per_page=25)
    #     page.embed.title = page_header#"Search Complete!"
    #     page.embed.color = pn_orange()
    #     await page.paginate()

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
                       category="User Management", hidden=True)
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
                       brief="Displays a list of all users who are not yet members.",
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
    --- Manual Give/Remove Inactive User Commands ---
                                                  """


    """                                   '''
    --- Cool Down User Commands ---
    """


    @is_team_member()
    @commands.guild_only()
    @eCommands.command(name="cooldown", aliases=["timeout"],
                       brief="Moves a user to/from cooldown.",
                       examples=['@Hibiki', "289364328796458234234", "@Hibiki @Luna",  "@Hibiki @Luna #cooldown-1"],
                       category="User Management")
    async def cooldown(self, ctx: commands.Context, members: commands.Greedy[discord.Member], cooldown_room: Optional[discord.TextChannel] = None):
        """
        This command will move one or multiple user into or out of cooldown.

        To move a user in/out of cooldown, use the command as such:
        `pn;cooldown <Member Mention or ID>`
        For example, `pn;cooldown @Hibiki`

        You can also move multiple users with a single command.
        `pn;cooldown @Hibiki @Beryl @Luna`
        This will move all the users into a single cooldown channel.

        If you want to make sure that users are moved to a specific cooldown channel, just add the channel name after the member(s) name(s)
        `pn;cooldown @Hibiki #cooldown-1` or ``pn;cooldown @Hibiki @Beryl @Luna #cooldown-2`
        """

        guild: discord.Guild = ctx.guild
        cooldown_configs: List[Dict] = ctx.bot.guild_setting(guild.id, 'cooldown_config')

        members_in_cooldown = []
        members_not_cooldown = []
        for member in members:
            member: Union[discord.Member, discord.User]
            in_cooldown = get_users_cooldown_role(cooldown_configs, member)
            if in_cooldown is None:
                members_not_cooldown.append(member)
            else:
                members_in_cooldown.append(member)

        cooldown_move_direction = "into" if len(members_not_cooldown) >= len(members_in_cooldown) else "out of"
        number_of_members_being_moved = len(members_not_cooldown) if len(members_not_cooldown) >= len(members_in_cooldown) else len(members_in_cooldown)

        if cooldown_move_direction == "into":
            # selected_cooldown_role = None
            # Figure out which channel we are moving people into.
            # First prioritize command args
            # Then prioritize if any passed members are in cooldown
            # Finally prioritize Empty channels.
            if cooldown_room is not None:
                cooldown_role_id = get_role_id_from_cooldown_room_id(cooldown_configs, cooldown_room.id)  # Staff member indicated desired channel in arguments.
                selected_cooldown_role: discord.Role = discord.utils.get(guild.roles, id=cooldown_role_id)
            else:
                if len(members_in_cooldown) > 0:  # use a cooldown room a user is in
                    for member in members_in_cooldown:
                        role, channel, channel_num = get_users_cooldown_role_channel_and_number(cooldown_configs, member)
                        if channel is not None and cooldown_room is None:
                            cooldown_room = channel
                            cooldown_role_id = get_role_id_from_cooldown_room_id(cooldown_configs, cooldown_room.id)  # Staff member indicated desired channel in arguments.
                            selected_cooldown_role: discord.Role = discord.utils.get(guild.roles, id=cooldown_role_id)
                            break

            if cooldown_room is None:  # if we still don't have a cooldown room find an empty one.

                for cooldown_config in cooldown_configs:
                    role_id = cooldown_config["role"]
                    cooldown_role: discord.Role = discord.utils.get(guild.roles, id=role_id)
                    if cooldown_role is not None and len(cooldown_role.members) == 0:
                        # room is empty.
                        cooldown_room_id = get_cooldown_room_id_from_role_id(cooldown_configs, cooldown_role.id)
                        cooldown_room = discord.utils.get(guild.channels, id=cooldown_room_id)
                        selected_cooldown_role = cooldown_role
                        break


            if cooldown_room is None:
                # Cant find a room/role. Abort
                embed = std_embed(f"Error!",
                                  "It seems that all the cooldown channels are currently full! Please either indicate a desired cooldown channel or move a user out of cooldown.")
                await ctx.send(embed=embed)
                return


            # -- Preform the move into --
            members_in_cd_st = "\n".join([member.display_name for member in members_in_cooldown])
            members_not_cd_st = "\n".join([member.display_name for member in members_not_cooldown])

            embed = std_embed(f"Moving **{number_of_members_being_moved}** Members {cooldown_move_direction} Cooldown.",
                              f"__Members Left To Be Moved:__\n{members_not_cd_st}\n"
                              f"\N{ZERO WIDTH SPACE}\n"
                              f"***Working.... Please Wait....***")
            progress_msg = await ctx.send(embed=embed)
            members_left_to_move = members_not_cooldown.copy()
            for i, member in enumerate(members_not_cooldown):
                log.info(f"Moving {member.display_name} {cooldown_move_direction} Cooldown.")
                if i > 0:
                    members_not_cd_st = "\n".join([member.display_name for member in members_left_to_move])
                    embed = std_embed(f"Moving **{number_of_members_being_moved}** Members {cooldown_move_direction} {cooldown_room.name}.",
                                      f"__Members Left To Be Moved:__\n{members_not_cd_st}\n"
                                      f"\N{ZERO WIDTH SPACE}\n"
                                      "***Working.... Please Wait....***")
                    await progress_msg.edit(embed=embed)
                """MOVE USER INTO COOLDOWN"""
                await move_member_into_isolation_room(ctx, member, selected_cooldown_role, reason="Member is being moved into Cooldown", cooldown_event=True)
                members_left_to_move.remove(member)
                members_in_cooldown.append(member)

            members_in_cd_st = "\n".join([member.display_name for member in members_in_cooldown])

            embed = std_embed(f"The following members have been moved into {cooldown_room.name}:",
                              f"{members_in_cd_st}")
            await progress_msg.edit(embed=embed)

        else:  # "out of"

            if len(members_in_cooldown) == 0:
                embed = std_embed(f"Error!",
                                  "None of those members are in a cooldown channel!")
                await ctx.send(embed=embed)
                return

            # -- Preform the move out of --
            members_in_cd_st = "\n".join([member.display_name for member in members_in_cooldown])
            # members_not_cd_st = "\n".join([member.display_name for member in members_not_cooldown])

            embed = std_embed(f"Moving **{number_of_members_being_moved}** Members {cooldown_move_direction} Cooldown.",
                              f"__Members Left To Be Moved:__\n"
                              f"{members_in_cd_st}\n"
                              f"\N{ZERO WIDTH SPACE}\n"
                              f"***Working.... Please Wait....***")
            progress_msg = await ctx.send(embed=embed)

            members_left_to_move = members_in_cooldown.copy()
            for i, member in enumerate(members_in_cooldown):
                log.info(f"Moving {member.display_name} {cooldown_move_direction} Cooldown.")
                if i > 0:
                    members_in_cd_st = "\n".join([member.display_name for member in members_left_to_move])
                    embed = std_embed(f"Moving **{number_of_members_being_moved}** Members {cooldown_move_direction} Cooldown.",
                                      f"__Members Left To Be Moved:__\n"
                                      f"{members_in_cd_st}\n"
                                      f"\N{ZERO WIDTH SPACE}\n"
                                      f"***Working.... Please Wait....***")
                    await progress_msg.edit(embed=embed)

                """MOVE USER OUT OF CHANNEL"""
                cooldown_role = get_users_cooldown_role(cooldown_configs, member)
                await move_member_out_of_isolation_room(ctx, member, cooldown_role, reason="Member is being moved out of Cooldown", cooldown_event=True)
                members_left_to_move.remove(member)
                members_not_cooldown.append(member)


            members_not_cd_st = "\n".join([member.display_name for member in members_not_cooldown])
            embed = std_embed(f"The following members have been moved {cooldown_move_direction} Cooldown:",
                              f"\n{members_not_cd_st}")
            await progress_msg.edit(embed=embed)



    @commands.is_owner()
    @commands.guild_only()
    @eCommands.command(name="remove_users_roles",
                       category="User Management", hidden=True)
    async def remove_roles(self, ctx: commands.Context, member: discord.Member):
        await self.temp_remove_roles(ctx, member, "Testing Role Removal", [])
        await ctx.send(f"Removed all roles from {member.display_name}")


    @commands.is_owner()
    @commands.guild_only()
    @eCommands.command(name="restore_users_roles",
                       category="User Management", hidden=True)
    async def restore_roles(self, ctx: commands.Context, member: discord.Member):
        await self.restore_temp_removed_roles(ctx, member, "Testing Role Restoration")
        await ctx.send(f"Restored all roles to {member.display_name}")


    async def temp_remove_roles(self, ctx: commands.Context, member: Union[discord.User, discord.Member], reason: str, roles_to_keep: List[discord.Role]):

        log.info(f"Getting users roles from Discord")
        # allowed_roles = await pDB.get_roles_in_guild(self.pool, ctx.guild.id)
        user_roles: List[discord.Role] = member.roles[1:]  # Get all the roles EXCEPT @everyone.

        log.info("Adding removed roles to DB")
        roles_to_remove = []
        for role in user_roles:
            keep = discord.utils.get(roles_to_keep, id=role.id)
            if keep is None:
                roles_to_remove.append(role)
                await pDB.add_role_tmp_removed_from_user(self.pool, ctx.guild.id, member.id, role.id)

        log.info("Removing roles from user")
        try:
            await member.remove_roles(*roles_to_remove, reason=reason)
        except discord.Forbidden:
            log.info("Could not add all roles due to permissions")

        log.info("Temp Remove Complete")


    async def restore_temp_removed_roles(self, ctx: commands.Context, member: Union[discord.User, discord.Member], reason: str):

        # allowed_roles = await pDB.get_roles_in_guild(self.pool, ctx.guild.id)
        log.info(f"Getting users roles from DB")
        user_roles: List[pDB.RoleRemovedFromUser] = await pDB.get_roles_tmp_removed_from_user(self.pool, ctx.guild.id, member.id)

        # for role in user_roles:
        log.info("Restoring removed roles to user")
        try:
            await member.add_roles(*user_roles, reason=reason)
        except discord.Forbidden:
            log.info("Could not add all roles due to permissions")

        log.info("Removing stored roles from DB")
        await pDB.delete_inactive_member_removed_roles(self.pool, ctx.guild.id, member.id)
        log.info("Restoration Complete")


    """                                   '''
    --- User Info Commands ---
    """


    # @commands.has_permissions(manage_messages=True)
    @is_team_member()
    @commands.guild_only()
    @eCommands.command(name="user_post_count",
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

        join_date_msg = f"They last joined PN on {member.joined_at.strftime('%b %d, %Y, %I:%M %p UTC')}" if member.joined_at is not None else "Could not determine when they joined."
        await status_msg.edit(embed=std_embed("Finished searching for posts!",
                                              f"<@!{member.id}> - {member.name}#{member.discriminator} has made **{post_count}** since {timestamp.strftime('%b %d, %Y, %I:%M %p UTC')}\n{join_date_msg}"))


    @is_team_member()
    @commands.guild_only()
    @eCommands.command(name="inactive_log",
                       brief="Gets various info on a user.",
                       examples=['@Hibiki', "12374839475644433"],
                       category="User Management")
    async def user_info(self, ctx: commands.Context, member: discord.Member):

        info: List['pDB.InactivityEvent'] = await pDB.get_inactivity_events(self.pool, ctx.guild.id, member.id)
        info.reverse()
        event_listing = []
        for event in info:
            event_listing.append(
                f"**{member.display_name}** went from {event.previous_lvl_str} -> **{event.current_lvl_str}** on {event.timestamp.strftime('%b %d, %Y, %I:%M %p UTC')}"
            )

        if len(event_listing) == 0:
            event_listing.append(f"{member.display_name} has no history of going inactive.")

        page_header = f"{member.display_name} Info:"

        page = UnnumberedPages(ctx=ctx, entries=event_listing, per_page=10)
        page.embed.title = page_header
        page.embed.color = pn_orange()
        await page.paginate()


def setup(bot):
    bot.add_cog(UserManagement(bot))
