'''

'''

import json
import logging
import asyncio
import traceback
from typing import Optional, Union, List
import asyncio
# from datetime import datetime, timedelta
import textwrap
import io
from contextlib import redirect_stdout

import discord
from discord.ext import commands

import embeds
from embeds import std_embed

from utilities.utils import get_channel, SnowFlake, backup_interviews_to_db, get_webhook, save_settings, clear_all_interviews, send_embed
from exceptions import NotTeamMember
from Interviews import Interviews, Interview
from uiElements import BoolPage

from PNDiscordBot import PNBot
import db

ZERO_WIDTH_CHAR = " ‌‌‌ "
TRIANGLE_EMOJI = "⚠ "

magic_word = "acceptable"

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s")
log = logging.getLogger("PNBot")

bot = PNBot(command_prefix="ib!",
            max_messages=5000,
            # description="A bot for interviewing new members.\n",
            owner_id=389590659335716867,
            case_insensitive=True)
# client.remove_command("help")  # Remove the built in help command so we can make the about section look nicer.


@bot.event
async def on_ready():
    log.info('Connected using discord.py {}!'.format(discord.__version__))
    log.info('Username: {0.name}, ID: {0.id}'.format(bot.user))
    log.info("Connected to {} servers.".format(len(bot.guilds)))

    activity = discord.Game("{}help".format(bot.command_prefix))
    await bot.change_presence(status=discord.Status.online, activity=activity)

    # FIXME: On_ready can happen again. Make sure that we do not load multiple instances of Interviews.
    await open_interviews.init_archive_and_log_channel()

    all_interviews = await db.get_all_interviews(bot.db)
    await bot.open_interviews.load_db(all_interviews)

    # raid_lvl = await db.

    log.info("Loaded {} interviews from database.".format(len(bot.open_interviews.interviews)))
    log.info('------')


def is_team_member():
    async def predicate(ctx: commands.Context):

        if ctx.guild is None:  # Double check that we are not in a DM.
            raise commands.NoPrivateMessage()

        bot: 'PNBot' = ctx.bot
        author: discord.Member = ctx.author
        role = discord.utils.get(author.roles, id=guild_settings["team_role_id"])
        if role is None:
            raise NotTeamMember()
        return True
    return commands.check(predicate)


def cleanup_code(content):
    """Automatically removes code blocks from the code."""
    # remove ```py\n```
    if content.startswith('```') and content.endswith('```'):
        return '\n'.join(content.split('\n')[1:-1])

    # remove `foo`
    return content.strip('` \n')


@commands.is_owner()
@bot.command(pass_context=True, hidden=True, name='eval')
async def _eval(ctx, *, body: str):
    """Evaluates a code"""

    env = {
        #'bot': self.bot,
        'client': bot,
        'ctx': ctx,
        'channel': ctx.channel,
        'author': ctx.author,
        'guild': ctx.guild,
        'message': ctx.message#,
        # '_': self._last_result
    }

    env.update(globals())

    body = cleanup_code(body)
    stdout = io.StringIO()

    to_compile = f'async def func():\n{textwrap.indent(body, "  ")}'

    try:
        exec(to_compile, env)
    except Exception as e:
        return await ctx.send(f'```py\n{e.__class__.__name__}: {e}\n```')

    func = env['func']
    try:
        with redirect_stdout(stdout):
            ret = await func()
    except Exception as e:
        value = stdout.getvalue()
        await ctx.send(f'```py\n{value}{traceback.format_exc()}\n```')
    else:
        value = stdout.getvalue()
        try:
            await ctx.message.add_reaction('\u2705')
        except:
            pass

        if ret is None:
            if value:
                await ctx.send(f'```py\n{value}\n```')
        else:
            # self._last_result = ret
            await ctx.send(f'```py\n{value}{ret}\n```')


@commands.is_owner()
@bot.command(name="test", hidden=True, )
async def test_cmd(ctx: commands.Context):  # , channel_name: str):
    raid_lvl = await db.get_raid_level(ctx.bot.db, ctx.guild.id)
    log.info(raid_lvl)




# @commands.is_owner()
# @bot.command(name="reload_questions")
# async def reload_questions(ctx):
#
#     with open('guildSettings.json') as json_data_file:
#         global guild_settings
#         guild_settings = json.load(json_data_file)
#     ctx.send("Reloaded settings")


@commands.is_owner()
@bot.command(name="reset_inter")
async def reset_interviews(ctx):

    clear_all_interviews()
    ctx.send("Reloaded settings")


@commands.is_owner()
@bot.command(name="invite")
async def invite(ctx: commands.Context):
    """
    Manage Server:
    Manage Roles: Setting channel override permissions.
    Manage Channels: Adding and removing temp interview channels
    Manage Webhooks: Adding webhook for archiving messages
    Read Messages: So we can read messages
    Embed Links:
    Read Message History: So we can archive channel before deletion
    Send Messages: So we can send messages

    Manage Messages: Actually probably unneded as the messages get deleted by the channel being deleted...

    Add reactions: So we can prepopulate reactions for button commands
    :param ctx:
    :return:
    """

    invite_url = "https://discordapp.com/oauth2/authorize?client_id=646689608096153620&scope=bot&permissions=805399664"
    await ctx.send(invite_url)


# --- Raid Protection Commands --- #
raid_protection_desc = [
    "No protection is enabled.",

    "Members will no longer be able to view the interview channels or the welcome channel."]#,

    # f"Personalized interview channels will no longer be automatically created. Instead greeters will need to create them using the `{bot.command_prefix}open` command.\n"
    # f"New people joining will be shown a message in the welcome channel that a raid is ongoing and that interviews for any potential legitimate members will be processed as soon as we can get to them.\n"
    # f"Lastly, a status channel will be created for the team that will help track all members who join. "
    # f"This will help to prevent any bad actors from hanging around and to prevent any potentially legitimate users from getting missed."
# ]


@is_team_member()
@commands.guild_only()
@bot.group(name="raid_level", brief="Sets / shows the level of raid protection.",
           description="This command allows you to set how aggressive PNBot is at protecting against raids.\n"
                       "Each level contains it's protections plus all the protections of the levels below it.\n"
                       "The current options are:\n\n"
                       f"**0**: {raid_protection_desc[0]}\n"
                       f"**1**: {raid_protection_desc[1]}\n"
                       # f"**2**: {raid_protection_desc[2]}"
           )
async def raid_protection(ctx: commands.Context):
    if ctx.invoked_subcommand is None:
        await ctx.send_help(raid_protection)


@is_team_member()
@commands.guild_only()
@raid_protection.command(name="set")
async def set_raid_lvl(ctx: commands.Context, raid_level: int):
    if 0 <= raid_level < 2:
        await db.upsert_raid_level(ctx.bot.db, ctx.guild.id, raid_level)

        if raid_level == 0:
            current_raid_lvl_desc = raid_protection_desc[0]
        else:
            current_raid_lvl_desc = ""
            for i in range(1, raid_level+1):
                current_raid_lvl_desc += f"{raid_protection_desc[i]}\n"

        msg = f"This servers raid protection level has been set to: **{raid_level}**\n" \
              f"The following protections are now in place:\n{current_raid_lvl_desc}"
    else:
        msg = f"{raid_level} is not a valid option."

    await send_embed(ctx, desc=msg)


@is_team_member()
@commands.guild_only()
@raid_protection.command(name="show")
async def show_raid_lvl(ctx: commands.Context):
    raid_lvl = await db.get_raid_level(ctx.bot.db, ctx.guild.id)

    if raid_lvl == 0:
        current_raid_lvl_desc = raid_protection_desc[0]
    else:
        current_raid_lvl_desc = ""
        for i in range(1, raid_lvl + 1):
            current_raid_lvl_desc += f"{raid_protection_desc[i]}\n"

    msg = f"The current raid protection level is: **{raid_lvl}**\n" \
          f"The following protections are now in place:\n{current_raid_lvl_desc}"

    await send_embed(ctx, desc=msg)


# --- Configuration Commands --- #

# @commands.has_permissions(manage_messages=True)
@commands.is_owner()  # TODO: Test and set back to allow w/ manage message
@commands.guild_only()
@bot.group(name="set_msg", brief="Lets you set configurable messages.",
           description="Lets you set configurable messages.")
async def set_msg(ctx: commands.Context):
    if ctx.invoked_subcommand is None:
        await ctx.send_help(set_msg)


@set_msg.command(name="rejection", brief="Sets the rejection message",
                 description="Displays/set the rejection message. The message field is optional. If it is included the rejection message will be changed. Otherwise, the current message will be show.")
async def set_rejection_message(ctx: commands.Context, *, message: Optional[str] = None):
    if message is not None:
        try:
            test_message = message.format(guild=ctx.guild, user=ctx.author)
            await ctx.send("Message changed!\nHere is your new rejection message (displayed with configurable guild and user options filled out):\n{space}".format(space=ZERO_WIDTH_CHAR))
            await ctx.send(test_message)
            guild_settings['rejection_message'] = message
            save_settings(guild_settings)
        except AttributeError as e:
            await ctx.send("Invalid Guild or User Options!")
            await ctx.send("{}".format(e))
    else:
        await ctx.send("Current rejection message:\n{space}".format(space=ZERO_WIDTH_CHAR))
        await ctx.send("{}".format(guild_settings['rejection_message']))


@set_msg.command(name="welcome", brief="Sets the welcome message",
                 description="Displays/set the welcome message. The message field is optional. If it is included the welcome message will be changed. Otherwise, the current message will be show.")
async def set_welcome_message(ctx: commands.Context, *, message: Optional[str] = None):
    if message is not None:
        try:
            test_message = message.format(guild=ctx.guild, user=ctx.author)
            await ctx.send("Message changed!\nHere is your new welcome message (displayed with configurable guild and user options filled out):\n{space}".format(space=ZERO_WIDTH_CHAR))
            await ctx.send(test_message)
            guild_settings['welcome_message'] = message
            save_settings(guild_settings)
        except AttributeError as e:
            await ctx.send("Invalid Guild or User Options!")
            await ctx.send("{}".format(e))
    else:
        await ctx.send("Current welcome message:\n{space}".format(space=ZERO_WIDTH_CHAR))
        await ctx.send("{}".format(guild_settings['welcome_message']))


@set_msg.command(name="approved", brief="Displays/set the approved message",
                 description="Displays/set the approved message")
async def set_approved_message(ctx: commands.Context, *, message: Optional[str] = None):
    if message is not None:
        try:
            test_message = message.format(guild=ctx.guild, user=ctx.author)
            await ctx.send("Message changed!\nHere is your new approved message (displayed with configurable guild and user options filled out):\n{space}".format(space=ZERO_WIDTH_CHAR))
            await ctx.send(test_message)
            guild_settings['approved_message'] = message
            save_settings(guild_settings)
        except AttributeError as e:
            await ctx.send("Invalid Guild or User Options!")
            await ctx.send("{}".format(e))
    else:
        await ctx.send("Current approved message:\n{space}".format(space=ZERO_WIDTH_CHAR))
        await ctx.send("{}".format(guild_settings['approved_message']))


# @commands.has_permissions(manage_messages=True)
@commands.is_owner()  # TODO: Test and set back to allow w/ manage message
@commands.guild_only()
@bot.group(name="questions", brief="Display / modify interview questions.",
           description="Lets you see the list of current questions, add new questions, modify current questions, remove questions, and reorder questions.\n")
async def questions_cmd(ctx: commands.Context):
    if ctx.invoked_subcommand is None:
        await ctx.send_help(questions_cmd)


@questions_cmd.command(name="list", brief="Lists all interview questions.")
async def list_questions_cmd(ctx: commands.Context):
    await list_questions(ctx)


async def list_questions(ctx: commands.Context):

    if len(guild_settings['interview_questions']) > 0:

        await ctx.send("Interview Questions:\n{}".format(ZERO_WIDTH_CHAR))

        questions_msg = ''
        for i, question in enumerate(guild_settings['interview_questions']):
            questions_msg += "**{}:**  {}\n".format(i+1, question)

        message_chunks = textwrap.wrap(questions_msg, width=2000, replace_whitespace=False)
        for chunk in message_chunks:
            await ctx.send(chunk)
            await asyncio.sleep(1)
    else:
        await ctx.send("There are no interview questions currently setup!")


@questions_cmd.command(name="add", brief="Add a new interview question.")
async def add_question(ctx: commands.Context, *, new_question: str):

    guild_settings['interview_questions'].append(new_question)
    save_settings(guild_settings)
    await ctx.send("Added new interview question!")


@questions_cmd.command(name="remove", brief="Remove an interview question.")
async def remove_question(ctx: commands.Context):
    await list_questions(ctx)  # Send the list of questions

    num_of_questions = len(guild_settings['interview_questions'])
    if num_of_questions > 0:
        await ctx.send("Please enter the question number you wish to remove. (Valid entries are 1 - {})".format(num_of_questions))

        def check(m):
            return m.author.id == ctx.author.id
        try:
            msg = await bot.wait_for('message', timeout=120.0, check=check)
            try:
                question_number = int(msg.content)
                if question_number > 0 and question_number <= num_of_questions:
                    removed_question = guild_settings['interview_questions'].pop(question_number - 1)
                    save_settings(guild_settings)
                    await ctx.send("Removed question number **{}**:".format(question_number))
                    await ctx.send(removed_question)
                else:
                    await ctx.send(
                        "`{}` is not a valid number from 1 - {}".format(msg.content[:1000], num_of_questions))
            except ValueError:
                await ctx.send("`{}` is not a valid number from 1 - {}".format(msg.content[:1000], num_of_questions))

        except asyncio.TimeoutError:
            await ctx.send("Command timed out.")


# @questions_cmd.command(name="move", brief="Move an interview question to a new position.")
# async def move_question(ctx: commands.Context):
#     await list_questions(ctx)  # Send the list of questions
#
#     num_of_questions = len(guild_settings['interview_questions'])
#     if num_of_questions > 0:
#         await ctx.send("Please enter the question number you wish to move. (Valid entries are 1 - {})".format(num_of_questions))
#
#         def check(m):
#             return m.author.id == ctx.author.id
#         try:
#             question_number = await client.wait_for('message', timeout=120.0, check=check)
#             await ctx.send(
#                 "Please enter the new position (Valid entries are 1 - {}".format(num_of_questions))
#             new_position = await client.wait_for('message', timeout=120.0, check=check)
#
#             try:
#                 question_number = int(question_number.content)
#                 new_position = int(new_position.content)
#                 guild_settings['interview_questions'].pop([question_number - 1])
#                 save_settings(guild_settings)
#             except ValueError or IndexError:
#                 await ctx.send("Invalid input")
#
#         except asyncio.TimeoutError:
#             await ctx.send("Command timed out.")


@commands.is_owner()
@bot.command(name="dump")
async def dump_interviews(ctx: commands.Context):
    log.info("Dumping interviews")
    await backup_interviews_to_db(open_interviews)


@is_team_member()
@commands.guild_only()
@bot.command(name="status", brief="Display the status of ongoing interviews")
async def status_of_interviews(ctx: commands.Context):

    if len(open_interviews.interviews) > 0:
        await ctx.send("Active Interviews:")
        for interview in open_interviews.interviews:
            await ctx.send(str(interview))
    else:
        await ctx.send("There are no active interviews.")


@is_team_member()
@commands.guild_only()
@bot.command(name="greet", brief="Closes the interview and gives them the member role.",
             description="Closes the interview and gives them the member role.\n"
                         " If the user is an alt-account, the original account should be @ed in the greet command.", usage="[@alt-Account]")
async def approve_user(ctx: commands.Context, alt_account: Optional[discord.Member] = None):

    guild: discord.Guild = ctx.guild
    interview_channel: discord.TextChannel = ctx.channel

    interview = open_interviews.get_by_channel_id(interview_channel.id)
    if interview is None:
        await ctx.channel.send("No interview is open in this channel!")
        return

    if interview.interview_type == interview.EXISTING_USER:  # User is an alt-account and thus does not need to read the rules again.
        await approve_existing_user(ctx, interview, alt_account)
    else:
        await approve_new_user(ctx, interview, alt_account)


async def approve_existing_user(ctx: commands.Context, interview, alt_account: Optional[discord.Member]):

    # User is an alt-account and thus does not need to read the rules again.
    conf_msg = None
    if alt_account is None:
        conf_msg = "No valid member account was specified!" \
                   " When greeting an alt-account, the related account must be included in the greet command."  # TODO: Improve this error message

    if alt_account is not None and alt_account.id == interview.member.id:
        conf_msg = "Can not greet alt-account, the member specified is the same as the member you are trying to greet! " \
                   "When greeting an alt-account, the related account must be included in the greet command."  # TODO: Improve this error message

    if conf_msg is not None:
        conf_page = BoolPage(body=f"{conf_msg}\nDo you wish to greet {interview.member.display_name} anyways?")
        if not await conf_page.run(ctx):
            await ctx.send("Command Canceled.")
            return

    await greet_user(ctx, interview, alt_account)


async def approve_new_user(ctx: commands.Context, interview, alt_account: Optional[discord.Member]):
    # TODO: This might be able to crash if we have someone who has a high role than the bot.

    if len(interview.rule_confirmations) <= 0:
        confirmation = BoolPage(name=None,
                                body="⚠ It does not appear that {} has read the rules yet. Do you wish to approve them anyways?".format(
                                    interview.member.display_name))
        response = await confirmation.run(ctx)
        if response is None or not response:
            await ctx.channel.send("Okay.")
            return

    await greet_user(ctx, interview, alt_account)
    return


async def greet_user(ctx: commands.Context, interview, alt_account: Optional[discord.Member]):
    """Gives the user the Member role, sends a welcome message, logs the greet, then closes the interview """

    await interview.member.add_roles(SnowFlake(guild_settings['member_role_id']),
                                     reason="The user was granted membership by {}#{}.".format(ctx.author.display_name, ctx.author.discriminator))
    await ctx.channel.send(guild_settings['approved_message'].format(guild=ctx.guild, user=interview.member))

    embed = embeds.log_greet(guild_settings['member_role_id'], interview.member, ctx.author, alt_account)
    await open_interviews.log_channel.send(embed=embed)
    await open_interviews.close_interview(interview)
    return


@is_team_member()
@commands.guild_only()
@bot.command(name="deny", brief="Closes the interview, then kicks the user after 5 minutes.",
             description="This command closes the interview, sends a message explaining that the user is not a good fit for the server, then after 5 minutes kicks the user from the server.\n"
                         "Must be used in an active interview channel.")
async def deny_user(ctx: commands.Context):

    guild: discord.Guild = ctx.guild
    interview_channel: discord.TextChannel = ctx.channel

    interview = open_interviews.get_by_channel_id(interview_channel.id)
    if interview is None:
        await ctx.send("No interview is open in this channel!")
        return

    conf_msg = BoolPage(name="Are you sure?")
    await conf_msg.run(ctx)
    if conf_msg.response:
        await ctx.send(guild_settings['rejection_message'].format(guild=guild, user=interview.member))

        embed = embeds.log_deny(interview.member, ctx.author)
        await open_interviews.log_channel.send(embed=embed)
        await open_interviews.close_interview(interview)

        log.info(f"Automatically kicking {interview.member}")

        await interview.member.kick(reason=f"User was kicked because they were denied membership by {ctx.author.display_name}")
    else:
        await ctx.send("Command Canceled")


@is_team_member()
@commands.guild_only()
@bot.command(name="close", brief="Closes the interview. Gives no roles and sends no acceptance or rejection message.")
async def close_interview(ctx: commands.Context, member: Optional[discord.Member] = None):
    #Do we need this? Should it be renamed? What's it's ultimate purpose?

    guild: discord.Guild = ctx.guild
    interview_channel: discord.TextChannel = ctx.channel

    if member is None:
        interview = open_interviews.get_by_channel_id(interview_channel.id)
        if interview is None:
            await ctx.channel.send("No interview is open in this channel!")
            return
    else:
        interview = open_interviews.get_by_member(member.id)
        if interview is None:
            await ctx.channel.send("User {} has no open interview!".format(member.display_name))
            return

    await ctx.channel.send("Closing interview.".format(interview.member.display_name))
    await open_interviews.close_interview(interview)


@is_team_member()
@commands.guild_only()
@bot.command(name="open", brief="Manually open an interview channel for a user.", usage='[User Account]')
async def open_interview(ctx: commands.Context, member: discord.Member):

    interview = open_interviews.get_by_member(member.id)
    if interview is not None:
        await ctx.channel.send("An interview is already open for this user in <#{}>".format(interview.channel.id))
        return

    guild: discord.Guild = ctx.guild
    current_raid_lvl = await db.get_raid_level(bot.db, member.guild.id)
    await create_interview(guild, member, current_raid_lvl)


@is_team_member()
@commands.guild_only()
@bot.command(name="restart", brief="Restarts the interview.", usage='<User Account>')
async def restart_interview(ctx: commands.Context, member: Optional[discord.Member] = None):

    guild: discord.Guild = ctx.guild
    interview_channel: discord.TextChannel = ctx.channel

    if member is None:
        interview = open_interviews.get_by_channel_id(interview_channel.id)
        if interview is None:
            await ctx.channel.send("No interview is open in this channel!")
            return
    else:
        interview = open_interviews.get_by_member(member.id)
        if interview is None:
            await ctx.channel.send("User {} has no open interview!".format(member.display_name))
            return

    await interview.restart()


@commands.guild_only()
@bot.command(name="pause", brief="Pauses the interview.")
async def pause_interview(ctx: commands.Context):

    interview_channel: discord.TextChannel = ctx.channel

    interview = open_interviews.get_by_channel_id(interview_channel.id)
    if interview is None:
        await ctx.channel.send("No interview is open in this channel!")
        return

    await interview.pause()


# TODO: Interviewies need to be able to use this command.
@commands.guild_only()
@bot.command(name="resume", brief="Resumes the interview.")
async def resume_interview(ctx: commands.Context):
    interview_channel: discord.TextChannel = ctx.channel

    interview = open_interviews.get_by_channel_id(interview_channel.id)
    if interview is None:
        await ctx.channel.send("No interview is open in this channel!")
        return

    await interview.resume()


# ---- Command Error Handling ----- #
@bot.event
async def on_command_error(ctx, error):
    if type(error) == discord.ext.commands.NoPrivateMessage:
        await ctx.send("⚠ This command can not be used in DMs!!!")
        return
    elif type(error) == discord.ext.commands.CommandNotFound:
        await ctx.send("⚠ Invalid Command!!!")
        return
    elif type(error) == discord.ext.commands.MissingPermissions:
        await ctx.send("⚠ You need the **Manage Messages** permission to use this command".format(error.missing_perms))
        return
    elif type(error) == NotTeamMember:
        await ctx.send("⚠ You must be a Team Member to use this command!")
        return
    elif type(error) == discord.ext.commands.MissingRequiredArgument:
        await ctx.send("⚠ {}".format(error))
    elif type(error) == discord.ext.commands.BadArgument:
        await ctx.send("⚠ {}".format(error))
    else:
        await ctx.send("⚠ {}".format(error))
        raise error


# ----- Discord Events ----- #
@bot.event
async def on_message(message: discord.Message):

    if message.author.id != bot.user.id:  # Don't log our own messages.

        message_contents = message.content if message.content != '' else None
        found = False
        for mention in message.role_mentions:
            if mention.id == guild_settings['team_role_id']:
                found = True
                break

        if found:
            channel: discord.TextChannel = message.channel
            author: discord.Member = message.author

            interview = open_interviews.get_by_member(author.id)
            if interview is None:
                await bot.process_commands(message)
                return

            log.info("{} confirmed reading the rules: {}".format(interview.member.display_name, message_contents))

            possible_rule_confirmation = message_contents
            await interview.append_rule_confirmations(possible_rule_confirmation)

    await bot.process_commands(message)


@bot.event
async def on_error(event_name, *args):
    log.exception("Exception from event {}".format(event_name))

    if 'error_log_channel' not in config:
        return
    error_log_channel = bot.get_channel(config['error_log_channel'])

    embed = None
    # Determine if we can get_by_member more info, otherwise post without embed
    if args and type(args[0]) == discord.Message:
        message: discord.Message = args[0]
        embeds.exception_w_message(message)
    elif args and type(args[0]) == discord.RawMessageUpdateEvent:
        log.error("After Content:{}.".format(args[0].data['content']))
        if args[0].cached_message is not None:
            log.error("Before Content:{}.".format(args[0].cached_message.content))
    # Todo: Add more

    traceback_message = "```python\n{}```".format(traceback.format_exc())
    traceback_message = (traceback_message[:1993] + ' ...```') if len(traceback_message) > 2000 else traceback_message
    await error_log_channel.send(content=traceback_message, embed=embed)


async def get_category(guild: discord.Guild, category_id: int) -> discord.CategoryChannel:
    for category in guild.categories:
        if category.id == category_id:
            return category
    raise Exception("Category {} is not in guild {}".format(category_id, guild.id))  # TODO: Don't use base exception.


async def handle_joining_user(guild: discord.Guild, member: discord.Member, raid_level: int):
    """
    Based on the current raid protection level, either start the interview as normal, or do what else is required based on current raid level.
    """
    if raid_level <= 1:
        await create_interview(guild, member, raid_level)
    else:
        pass


async def create_interview(guild: discord.Guild, member: discord.Member, raid_level: int = 0):
    """
    Creates an interview channel for a given member, then starts the interview.
    """

    interview_category: discord.CategoryChannel = await get_category(guild, guild_settings['interview_category_id'])

    channel_name = "{}-Interview".format(member.name, member.discriminator)
    channel_topic = "Temporary interview room for {}".format(member.name)
    member_role = guild.get_role(guild_settings['member_role_id'])
    ignore_interview_role: discord.Role = guild.get_role(guild_settings["hide_interviews_id"])
    greeter_role = guild.get_role(guild_settings['team_role_id'])

    new_perms = category_perms = interview_category.overwrites  # Inherit perms from the category.

    new_perms[greeter_role] = discord.PermissionOverwrite(send_messages=True, read_messages=True)  # Greeters
    new_perms[member] = discord.PermissionOverwrite(send_messages=True, read_messages=True)  # The user who just joined
    new_perms[ignore_interview_role] = discord.PermissionOverwrite(send_messages=False, read_messages=False)  # Does nothing on Nest...

    # Add role overrides for any user with the ignore_interview role
    ignored_members = ignore_interview_role.members
    for ignore_member in ignored_members:
        new_perms[ignore_member] = discord.PermissionOverwrite(send_messages=False, read_messages=False)

    if raid_level == 0:  # No Raid Protection Enabled.
        new_perms[guild.default_role] = discord.PermissionOverwrite(send_messages=False, read_messages=True)  # @Everyone
        new_perms[member_role] = discord.PermissionOverwrite(send_messages=False, read_messages=True)  # The Member Role

    else:  # Raid Protection Enabled
        new_perms[guild.default_role] = discord.PermissionOverwrite(send_messages=False, read_messages=False)  # @Everyone
        new_perms[member_role] = discord.PermissionOverwrite(send_messages=False, read_messages=False)  # The Member Role

    # Create the channel
    interview_channel = await guild.create_text_channel(channel_name, category=interview_category,
                                                        topic=channel_topic, overwrites=new_perms)

    await asyncio.sleep(1)  # Wait a sec after the channel is created before sending anything.

    await interview_channel.send(guild_settings['welcome_message'].format(guild=guild, user=member))

    await asyncio.sleep(1)  # Wait another sec before opening the interview.

    # Open the interview.
    interview = await open_interviews.new_interview(member, interview_channel)


@bot.event
async def on_member_join(member: discord.Member):
    event_type = "member_join"
    log.info("{}#{} Joined".format(member.name, member.discriminator))
    if not member.bot:
        # Create temp interview channel
        guild: discord.Guild = member.guild
        current_raid_lvl = await db.get_raid_level(bot.db, member.guild.id)
        await create_interview(guild, member, current_raid_lvl)


@bot.event
async def on_member_remove(member: discord.Member):
    event_type = "member_leave"

    if not member.bot:
        interview = open_interviews.get_by_member(member_id=member.id)
        if interview is not None:
            message = "{user.name} left {guild.name} before finishing their interview.".format(user=member, guild=member.guild)
            await open_interviews.close_interview(interview, message=message)
            await backup_interviews_to_db(open_interviews)


@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):

    interview = bot.open_interviews.get_by_channel_id(payload.channel_id)
    if interview is not None:
        await interview.check_add_reactions(payload)


@bot.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):

    interview = bot.open_interviews.get_by_channel_id(payload.channel_id)
    if interview is not None:
        await interview.check_remove_reactions(payload)

if __name__ == '__main__':
    #
    # with open('config.json') as json_data_file:
    #     config = json.load(json_data_file)
    #
    # with open('guildSettings.json') as json_data_file:
    #     guild_settings = json.load(json_data_file)
    #     bot.primary_guild_id = 433446063022538753
    #     # bot.load_guild_settings(433446063022538753, guild_settings)  # PN Server.

    with open('testConfigs/config.dev.json') as json_data_file:
        config = json.load(json_data_file)

    with open('testConfigs/guildSettings.json') as json_data_file:
        guild_settings = json.load(json_data_file)
        bot.primary_guild_id = 641244873902784522
        # bot.load_guild_settings(641244873902784522, guild_settings)  # Test Server.

    bot.db = config['db_address']
    asyncio.get_event_loop().run_until_complete(db.create_tables(bot.db))

    open_interviews = Interviews(bot, guild_settings)  # ToDo: open_interviews should be a class member of bot.
    bot.open_interviews = open_interviews

    bot.command_prefix = config['bot_prefix']
    bot.load_cogs()
    bot.run(config['token'])

    log.info("cleaning Up and shutting down")
    asyncio.get_event_loop().run_until_complete(backup_interviews_to_db(open_interviews))
    # backup_interviews(open_interviews)
