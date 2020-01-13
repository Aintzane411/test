import discord
from datetime import datetime
from typing import Optional, Union


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

