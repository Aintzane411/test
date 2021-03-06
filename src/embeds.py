"""

"""
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Optional, Union

import discord
from discord.embeds import EmptyEmbed

from utilities.utils import pn_embed, make_ordinal
from utilities.moreColors import pn_orange

if TYPE_CHECKING:
    from utilities.roleParser import ParsedRoles

def exception_w_message(message: discord.Message) -> discord.Embed:
    embed = discord.Embed()
    embed.colour = 0xa50000
    embed.title = message.content
    guild_id = message.guild.id if message.guild else "DM Message"

    embed.set_footer(text="Server: {}, Channel: {}, Sender: <@{}> - {}#{}".format(
        message.author.name, message.author.discriminator, message.author.id,
        guild_id, message.channel.id))
    return embed


def archive_header(interview_name: str, interview_user_id: int, thumbnail_url: str, start_time: datetime, message=None):
    interview_header = "Interview with {}".format(interview_name)
    embed = discord.Embed(color=discord.Colour.dark_gold(), timestamp=start_time)
    if message is not None:
        embed.description = message

    embed.set_thumbnail(url=thumbnail_url)
    embed.set_author(name=interview_header)
    embed.set_footer(text="User ID: {}".format(interview_user_id))

    return embed


def log_greet(member_role_id: int, new_account: discord.Member, greeter_account: discord.Member, linked_account: Optional[discord.Member] = None):
    # Description contains 0width char between \n  \n
    embed = discord.Embed(description="<@{}> was given the <@&{member}> role by <@{}>\n  ‌‌‌ \n{}'s ID: `{}`".format(new_account.id, greeter_account.id, new_account.name, new_account.id, member=member_role_id),
                          color=0x2ECC71, timestamp=datetime.utcnow())

    embed.set_author(name="{} greeted {}".format(greeter_account.name, new_account.name))
    if linked_account is not None:
        embed.add_field(name="Linked Account:", value="This Member is related to: <@{}>\n{}'s ID: `{}`".format(linked_account.id, linked_account.name, linked_account.id))

    embed.set_footer(text="Greeter {}'s ID: {}".format(greeter_account.name, greeter_account.id))

    avatar = new_account.avatar_url_as(
        static_format="png")  # Need to use format other than WebP for image to display on iOS. (I think this is a recent discord bug.)
    embed.set_thumbnail(url=avatar)

    return embed


def log_deny(new_account: discord.Member, greeter_account: discord.Member, linked_account: Optional[discord.Member] = None):
    # Description contains 0width char between \n  \n
    embed = discord.Embed(description="<@{}> was denied membership by <@{}>\n  ‌‌‌ \n{}'s ID: `{}`".format(new_account.id, greeter_account.id, new_account.name, new_account.id),
                          color=discord.Colour.dark_red(), timestamp=datetime.utcnow())

    embed.set_author(name="{} denied membership for {}".format(greeter_account.name, new_account.name))
    if linked_account is not None:
        embed.add_field(name="Linked Account:", value="This Member is related to: <@{}>\n{}'s ID: `{}`".format(linked_account.id, linked_account.name, linked_account.id))

    embed.set_footer(text="Greeter {}'s ID: {}".format(greeter_account.name, greeter_account.id))

    avatar = new_account.avatar_url_as(
        static_format="png")  # Need to use format other than WebP for image to display on iOS. (I think this is a recent discord bug.)
    embed.set_thumbnail(url=avatar)

    return embed


def log_welcome_back(reactivated_account: discord.Member, inactive_count: int, deactive_time: timedelta):
    # Description contains 0width char between \n  \n

    if deactive_time.days > 0:
        deactive_time_str = f"**{deactive_time.days}** days"
    else:
        hours = deactive_time.seconds // 3600
        minutes = (deactive_time.seconds % 3600) // 60

        if hours > 0:
            deactive_time_str = f"**{hours + (minutes / 60):.2f}** hours"
        else:
            seconds = deactive_time.seconds % 60
            deactive_time_str = f"**{minutes + (seconds / 60):.2f}** minutes"

    embed = discord.Embed(title=f"Welcome Back {reactivated_account.display_name}!",
                          description=f"<@{reactivated_account.id}> is no longer an inactive member.\n"
                                      f"This is the **{make_ordinal(inactive_count)}** time they have had their server access restored becoming inactive.\nIt took {deactive_time_str} for the user to regain access.\n  ‌‌‌ \n{reactivated_account.name}'s ID: `{reactivated_account.id}`",
                          color=pn_orange(), timestamp=datetime.utcnow())

    avatar = reactivated_account.avatar_url_as(
        static_format="png")  # Need to use format other than WebP for image to display on iOS. (I think this is a recent discord bug.)
    embed.set_thumbnail(url=avatar)

    return embed


def std_embed(title: Optional[str] = EmptyEmbed, desc: Optional[str] = EmptyEmbed, color: Optional[discord.Color] = None) -> discord.Embed:
    """Helper for creating embeds"""
    if color is None:
        color = pn_orange()

    embed = discord.Embed(title=title,
                          description=desc,
                          color=color)
    return embed


def add_and_removed_roles_embed(roles: 'ParsedRoles', disallowed_field_name=None, remove_roles_msg: bool = False) -> discord.Embed:

    add_remove_txt = "removed" if remove_roles_msg else "added"

    if disallowed_field_name is None:
        disallowed_field_name = f"The following roles are not allowed to be {add_remove_txt} by PNBot:"

    status_embed = pn_embed(title=f"{len(roles.good_roles)} out of {len(roles.good_roles) + len(roles.bad_roles) + len(roles.disallowed_roles)} roles {add_remove_txt}")

    if len(roles.good_roles) > 0:
        good_roles_msg = ", ".join([f"<@&{role.id}>" for role in roles.good_roles])
        status_embed.add_field(name=f"Successfully {add_remove_txt}:", value=good_roles_msg, inline=False)

    if len(roles.disallowed_roles) > 0:
        disallowed_roles_msg = ", ".join([f"<@&{role.id}>" for role in roles.disallowed_roles])

        status_embed.add_field(
            name=disallowed_field_name,
            value=disallowed_roles_msg, inline=False)

    if len(roles.bad_roles) > 0:
        bad_roles_msg = ", ".join([f"{role}" for role in roles.bad_roles])
        suggestion_strs = [f"<@&{role.best_match.id}>" for role in roles.bad_roles if
                           role.best_match is not None]
        suggestion_msg = f"\n\nDid you mean? \n{', '.join(set(suggestion_strs))}" if len(suggestion_strs) > 0 else ""

        status_embed.add_field(name="Could not find the following (check spelling and capitalization):",
                               value=f"{bad_roles_msg}{suggestion_msg}\n\N{ZERO WIDTH SPACE}", inline=False)

    return status_embed
