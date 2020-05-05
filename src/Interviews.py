"""

"""
from __future__ import annotations

from datetime import datetime, timedelta
# import json
from typing import TYPE_CHECKING, Optional, Union, List, Dict
import asyncio
import logging
import secrets

import discord
from discord.ext import commands

import embeds
import db
from utilities.utils import get_channel, get_webhook, backup_interviews_to_db
from utilities.moreColors import pn_orange

if TYPE_CHECKING:
    from PNDiscordBot import PNBot


ZERO_WIDTH_CHAR = " ‌‌‌ "
TRIANGLE_EMOJI = "⚠ "


async def create_interview(discord_client: 'PNBot', interviews: Interviews, member: Optional[discord.Member], channel: Optional[discord.TextChannel]) -> Interview:
    interview = Interview(discord_client, interviews, member, channel)
    await interview.init()
    return interview


class Interview:
    LOG = logging.getLogger("PNBot.Interview")

    # Interview Types #
    NOT_STARTED = "not started"  # Default starting type

    # Interviews
    NEW_SYSTEM = "new system"
    NEW_QUESTIONING = "new questioning"
    NEW_SINGLET = "new singlet"
    NEW_TULPA = "new tulpa"

    # Different prompts
    EXISTING_USER = "existing member"
    OTHER = "other"

    # -- Message Defs -- #
    FINAL_INTERVIEW_MESSAGE = "Thank you!!! Be sure to read the rules extremely carefully. You will be assisted by a staff member as soon as you have done so."

    IGNORED_MESSAGES = []

    interview_tracks = (("👥", NEW_SYSTEM), ("❓", NEW_QUESTIONING), ("👤", NEW_SINGLET), ("<:tupla:652995996468379677>", NEW_TULPA), ("<:altAccount:652989510996721675>", EXISTING_USER), ("ℹ️", OTHER))
    interview_reset_emoji = "<:back:706947547305869322>"

    interview_emojis = tuple((track[0] for track in interview_tracks))

    def __init__(self, discord_bot: 'PNBot', interviews: Interviews, member: Optional[discord.Member], channel: Optional[discord.TextChannel]):

        # -- Set by init call or JSON/DB Load--
        self.bot: 'PNBot' = discord_bot
        self.interviews: Interviews = interviews
        self.member: discord.Member = member
        self.channel: discord.TextChannel = channel

        # -- Persistent (Via JSON/DB backup) --

        # Not going to change once entered into DB. No need to have setter.
        self.member_id = self.member.id if self.member is not None else None
        self.channel_id = self.channel.id if self.channel is not None else None
        self.guild_id = self.channel.guild.id if self.channel is not None else None

        # Mutable properties. Need Setters.
        self._question_number: int = 0
        self._interview_finished: bool = False

        self._paused: bool = False
        self.started: bool = False  # Not needed unless we decide to care about automatically resuming listening for reacts after reboot.

        self._interview_type = self.NOT_STARTED  # Converted.
        self._rule_confirmations = []

        # -- Not Persistent --
        self.waiting_for_msgs = False
        self.questions = self.interviews.settings['interview_questions']
        self.question_lock = asyncio.Lock()

    async def init(self):
        # Only add a new DB entry if the interview object has been instantiated with Member and Channel objects. Otherwise, the object has been instantiated for load from DB Backup.
        if self.member is not None and self.channel is not None:
            await db.add_new_interview(self.bot.db, self.guild_id, self.member_id, self.member.display_name,
                                       self.channel_id, self.question_number, self.interview_finished,
                                       self.paused, self.interview_type, read_rules=False)

            # Since this interview was just created, send prompt for interview type to get everything rolling.
            await self.send_interview_type_prompt()

    # -- Interview Type Setter/Getters -- #
    @property
    def interview_type(self):
        return self._interview_type

    async def set_interview_type(self, value):
        self._interview_type = value
        await db.update_interview_type(self.bot.db, self.channel_id, self.member_id, self._interview_type)

    # Question Number Setter/Getters
    @property
    def question_number(self):
        return self._question_number

    async def set_question_number(self, value):
        self._question_number = value
        await db.update_interview_question_number(self.bot.db, self.channel_id, self.member_id, self._question_number)

    # -- Interview Finished Setter/Getters -- #
    @property
    def interview_finished(self):
        return self._interview_finished

    async def set_interview_finished(self, value):
        self._interview_finished = value
        await db.update_interview_finished(self.bot.db, self.channel_id, self.member_id, self._interview_finished)

    # -- Interview Paused Setter/Getters -- #
    @property
    def paused(self):
        return self._paused

    async def set_paused(self, value):
        self._paused = value
        await db.update_interview_paused(self.bot.db, self.channel_id, self.member_id, self._paused)

    # -- Rule Confirmations Setter/Getters -- #
    @property
    def rule_confirmations(self):
        return self._rule_confirmations

    async def set_rule_confirmations(self, value):
        self._rule_confirmations = value
        read_rules = True if len(self._rule_confirmations) > 0 else False
        await db.update_interview_read_rules(self.bot.db, self.channel_id, self.member_id, read_rules)

    async def append_rule_confirmations(self, value):

        self._rule_confirmations.append(value)
        if len(self._rule_confirmations) == 1:
            # Since we are only storing True/False in the DB, only update the DB when it goes from False -> True. AKA 0 -> 1
            read_rules = True if len(self._rule_confirmations) > 0 else False
            await db.update_interview_read_rules(self.bot.db, self.channel_id, self.member_id, read_rules)


    def __str__(self):

        if self.interview_finished:
            overall_status = "<@{}> has completed their interview in <#{}>.".format(self.member.id, self.channel.id)
        else:
            overall_status = "<@{}> has an ongoing interview in <#{}>.".format(self.member.id, self.channel.id)

        read_rules = "They have read the rules." if len(self.rule_confirmations) > 0 else "They have NOT read the rules."

        if self.interview_type == self.NOT_STARTED:
            interview_track = "They have not yet selected an interview type."
        elif self.interview_type == self.NEW_SYSTEM:
            interview_track = "They are a new user, taking the system interview."
        elif self.interview_type == self.NEW_QUESTIONING:
            interview_track = "They are a new user, taking the questioning interview."
        elif self.interview_type == self.NEW_SINGLET:
            interview_track = "They are a new user, taking the singlet interview."
        elif self.interview_type == self.EXISTING_USER:
            interview_track = "They are an alt-account of an existing member."
            read_rules = ""
        elif self.interview_type == self.OTHER:
            interview_track = "They have selected other."
        else:
            interview_track = "ERROR: UNKNOWN INTERVIEW TYPE!!!"

        output = "{} {} {}".format(overall_status, interview_track, read_rules)
        return output


    def __eq__(self, other):
        if isinstance(other, Interview):
            if self.member_id == other.member_id and self.channel_id == other.channel_id and self.guild_id == other.guild_id:
                return True
        return False


    # ----- Interview State Control Methods ----- #

    async def start_interview_track(self):

        if self.interview_type == self.NEW_SYSTEM or self.interview_type == self.NEW_QUESTIONING or self.interview_type == self.NEW_SINGLET or self.interview_type == self.NEW_TULPA:
            await self.ask_interview_questions()

        elif self.interview_type == self.EXISTING_USER:
            await self.start_existing_system_prompt()

        elif self.interview_type == self.OTHER:
            await self.start_other_prompt()

        elif self.interview_type == self.NOT_STARTED:
            # We should never get here, default to contacting team member.
            await self.start_other_prompt()


    async def restart(self, soft_restart: bool = False):
        """
        Restarts the interview to the beginning.
        :param soft_restart: If False a new interview type prompt is sent out. If True no new interview type prompt is sent out.
        :type soft_restart: bool
        """

        await self.set_question_number(0)
        await self.set_interview_finished(False)
        await self.set_interview_type(self.NOT_STARTED)

        await self.set_paused(False)  # Just added but makes sense....

        self.waiting_for_msgs = False
        if not soft_restart:
            await self.send_interview_type_prompt()


    async def send_interview_type_prompt(self):
        # Ready_msg has a 0width char in the beginning.
        # ready_msg = await self.channel.send(
        #     " ‌‌‌ \nIf your system is new to {guild.name}, please click ✅ when you are ready to start your interview. \nIf your system already has an account on {guild.name}, please click 👥.\n".format(guild=self.channel.guild, user=self.member))
        tulpa_emoji = "<:tupla:652995996468379677>"
        alt_account_emoji = "<:altAccount:652989510996721675>"
        new_user_interview_prompt = " ‌‌‌ \nIf you are **new to {guild.name}** or have been **gone for more than 30 days**  please click on the reaction that applies to you:\n\n" \
                                    "*Plural System:* 👥\n" \
                                    "*Questioning whether or not you are a system:* ❓\n" \
                                    "*Singlet (A person who is not plural):* 👤\n" \
                                    "*Looking to make a tulpa:* {tulpa}\n\n".format(guild=self.channel.guild,
                                                                                    user=self.member,
                                                                                    tulpa=tulpa_emoji)
        alt_account_prompt = "If you already have an account on {guild.name}, please click {emoji}.\n\n".format(
            guild=self.channel.guild, user=self.member, emoji=alt_account_emoji)
        other_prompt = "If you need to speak to {guild.name} staff, if you would prefer to take your interview over DM, or for anything else, please click ℹ️\n".format(
            guild=self.channel.guild, user=self.member)

        # ready_msg = await self.channel.send(
        #     " ‌‌‌ \nIf you are a system and you are new to {guild.name}, please click 👥 when you are send_interview_type_prompt to start your interview. \n"
        #     "If you already have an account on {guild.name}, please click 👥.\n".format(
        #         guild=self.channel.guild, user=self.member))
        embed = discord.Embed(color=pn_orange())
        embed.description = new_user_interview_prompt + alt_account_prompt + other_prompt
        # ready_msg = await self.channel.send(new_user_interview_prompt+alt_account_prompt+other_prompt)
        ready_msg = await self.channel.send(embed=embed)

        for emoji, _ in self.interview_tracks:
            await ready_msg.add_reaction(emoji)


    async def check_add_reactions(self, payload: discord.RawReactionActionEvent):

        # Begin checking the different possible react actions.
        if await self.check_interview_type_reaction(payload.emoji, payload.user_id):
            # Begin the interview.
            return
        else:
            # Interview is already happening, reaction made by user who is not the interviewie, etc.
            # Try to remove the invalid reaction.
            message: discord.Message = await self.bot.get_message(payload.message_id, payload.channel_id)
            if message is not None:
                member: Union[discord.Member, discord.User] = payload.member if payload.member is not None else self.bot.get_user(payload.user_id)

                if member is not None and member.id != self.bot.user.id:  # Don't remove our own reactions lol.
                    # Todo: Permissions check (manage_messages)
                    try:
                        await message.remove_reaction(payload.emoji, member)
                    except (discord.InvalidArgument, discord.HTTPException):
                        return


    async def check_interview_type_reaction(self, emoji: discord.PartialEmoji, user_id: int):

        # ensure that the person reacting is the interviewee and that the reaction is a valid interview type emoji
        if user_id != self.member.id or str(emoji) not in self.interview_emojis:
            return False

        # If the interview track has already been set, abort.
        if self.interview_type != self.NOT_STARTED:
            if str(emoji) == self.interview_reset_emoji:
                return True
            return False

        # Start the interview
        self.started = True

        for interview_emoji, interview_tract in self.interview_tracks:
            if str(emoji) == interview_emoji:
                await self.set_interview_type(interview_tract)

        # Now that the interviewee has chosen an interview type, we can start their specific interview.
        await self.start_interview_track()

        # The reaction matched with this check and has been completed successfully. Return True.
        return True


    async def check_remove_reactions(self, payload: discord.RawReactionActionEvent):

        # Begin checking the different possible react actions.
        if await self.check_interview_type_reaction_remove(payload.emoji, payload.user_id):
            return
        else:
            return


    async def check_interview_type_reaction_remove(self, emoji: discord.PartialEmoji, user_id: int):
        """
        Checks to see if the interview track should be reset based on who removed the reaction and which reaction was removed.
        """

        # ensure that the reaction removed belongs to the interviewee and that the reaction is a valid interview type emoji
        if user_id != self.member.id or str(emoji) not in self.interview_emojis:
            return False

        # If the interview track has not been set, abort because this is a weird state to be in.....
        if self.interview_type == self.NOT_STARTED:
            return False

        for interview_emoji, interview_tract in self.interview_tracks:
            if str(emoji) == interview_emoji:
                if interview_tract != self.interview_type:
                    return False

        team_role: discord.Role = self.channel.guild.get_role(self.interviews.settings['team_role_id'])
        team_role_name = discord.utils.escape_mentions(f"@{team_role}") if team_role is not None else "Staff"

        await self.channel.send(f"\N{zero width space} \n"
                                f"Interview Type has been reset. Please chose another interview type by clicking on another reaction above or ping {team_role_name} for assistance.\n"
                                f"\N{zero width space}")

        await self.restart(soft_restart=True)


    # ----- Ask interview questions/prompts Methods ----- #


    async def ask_interview_questions(self):
        def check(m: discord.Message):
            return m.author.id == self.member.id and m.channel == self.channel and self.paused is False and m.content.strip().lower() != "{}pause".format(self.bot.command_prefix)
        self.waiting_for_msgs = True

        # Use a Asyncio.Lock() to prevent multiple instances of ask_interview_questions() asking questions to the same interviewee at the same time.
        # if not self.question_lock.locked():  # No need to try asking questions since another ask_interview_questions() is already at work!
        #     async with self.question_lock:  # Get the lock
        self.LOG.info(f"Got the lock for {self.member.display_name} questions")
        interview_type = self.interview_type
        while True and not self.interview_finished:
            await self.send_next_interview_question()
            msg = await self.bot.wait_for('message', check=check)
            if interview_type != self.interview_type:
                # the interview type changed! Bail!
                break

            self.LOG.info(msg.content)
            if self.question_number >= len(self.questions[self.interview_type]):
                async with self.channel.typing():
                    await asyncio.sleep(1.5)
                    # self.interview_finished = True
                    await self.channel.send(self.FINAL_INTERVIEW_MESSAGE)
                    await self.set_interview_finished(True)
                break
        # else:
        #     self.LOG.info(f"{self.member.display_name} questions are locked!")

        self.LOG.info(f"Finished asking {self.member.display_name} questions")


    async def send_next_interview_question(self):
        try:
            if not self.paused:
                async with self.channel.typing():
                    await asyncio.sleep(1.1)
                    await self.channel.send(self.questions[self.interview_type][self.question_number])
                    # self.question_number += 1
                    await self.set_question_number(self.question_number + 1)
        except Exception as e:
            self.LOG.exception(e)

    async def start_existing_system_prompt(self):
        # self.interview_finished = True
        await self.set_interview_finished(True)
        await self.channel.send("Please have your account that is already present on {guild.name} vouch that this new account belongs to them in <#{}> and then ping staff.".format(self.interviews.settings['welcome_channel_id'], guild=self.channel.guild, user=self.member))

    async def start_other_prompt(self):
        # self.interview_finished = True
        await self.set_interview_finished(True)
        other_prompt_message = "{user.display_name} would you please tell us how we may help you and a <@&{team_role_id}> member will be with you as soon as possible. Thank you!".format(guild=self.channel.guild, user=self.member, team_role_id=self.interviews.settings['team_role_id'])
        await self.channel.send(other_prompt_message)


    # ----- Pause & Resume Methods ----- #


    async def pause(self):
        # self.paused = True
        await self.set_paused(True)
        await self.channel.send("The interview has been paused. You may resume the interview with `{}resume`".format(self.bot.command_prefix))

    async def resume(self):
        # self.paused = False
        if not self.interview_finished and self.interview_type != self.NOT_STARTED:

            await self.channel.send("The interview has been resumed.")
            if self.question_number > 0:
                # self.question_number -= 1
                await self.set_question_number(self.question_number - 1)
            if self.waiting_for_msgs:
                await self.send_next_interview_question()
            else:  # TODO: Remove the start_interview track? We might need to reset the reactions though....
                await self.start_interview_track()

    async def prompt_to_resume(self):
        if not self.interview_finished and self.interview_type != self.NOT_STARTED:
            await self.channel.send("Apologies for the interruption, Please type **{}resume** to continue your interview.".format(self.bot.command_prefix))


    # ----- JSON & DB Methods ----- #


    def dump_dict(self):
        data = dict(
            member_id=self.member.id,
            channel_id=self.channel.id,
            question_number=self.question_number,
            interview_finished=self.interview_finished,
            paused=self.paused,
            interview_type =self.interview_type,
            rule_confirmations=self.rule_confirmations
        )
        return data

    def dump_json(self):
        raise NotImplementedError
        # return json.dumps(self.dump_dict, indent=4)

    async def save_to_db(self):
        self.LOG.info("Interview: save_to_db()")
        self.LOG.info(f"Saving {self.member.display_name}'s interview")
        read_rules = True if len(self.rule_confirmations) > 0 else False
        await db.update_interview_all_mutable(self.bot.db, self.channel_id, self.member_id, self.question_number, self.interview_finished, self.paused, self.interview_type, read_rules)

    async def load_json(self, json_data: dict):
        """
        Loads all the appropriate data from a dictionary to create a fully functional Interview Object.
        Is currently used by Interview.load_db(db_dict) to load data from the DB
        """
        # raise NotImplementedError
        # Still used by self.load_db()

        # TODO: Add error handling.

        # Load the following directly instead of usiing the setter as it doesn't make sense to backup the variables to the DB right after loading them from the DB.
        self._question_number = json_data["question_number"]
        self._interview_finished = json_data["interview_finished"]
        self._paused = json_data["paused"]
        self._interview_type = json_data['interview_type']
        self._rule_confirmations = json_data["rule_confirmations"]

        self.channel_id = json_data["channel_id"]

        self.channel = await get_channel(self.bot, json_data["channel_id"])

        self.member_id = json_data["member_id"]

        self.guild_id = json_data["guild_id"]

        if self.channel is not None:
            self.member = self.channel.guild.get_member(json_data["member_id"])
        else:
            self.LOG.warning(f"Could not find channel matching: {self.channel_id}!! Interview for {self.member_id} will not be loaded!!")

        if self.member is None and self.channel is not None:
            self.LOG.warning(
                f"Found channel matching {self.channel_id}({self.channel.name}), but could not find member matching: {self.member_id}!! Corresponding interview will not be loaded!!")

        # Check to see if we were able to successfully load the interview
        if self.member is not None and self.channel is not None:

            # Since we just loaded the interview from the DB it is save to assume that the interview process was interrupted
            # Let the interviewee know he may use the resume command
            await self.prompt_to_resume()
            return self
        else:
            # Either (or both) member and channel are None,
            # which means that the member is no longer in the guild or that the channel no longer exists (Or discord/d.py has messed up?....)

            # If the member is None we definitely need to remove the interview from the DB (Do we need to archive the channel if it exists?)
            # If the channel is None then we should also remove the interview from the DB.
            if self.channel is None:
                # Start with checking channel since it's easier.
                await db.delete_interview(self.bot.db, self.channel_id, self.member_id)
            elif self.member is None:
                # TODO: Take care of the channel that still exists.
                await db.delete_interview(self.bot.db, self.channel_id, self.member_id)

            return None

    async def load_db(self, db_dict: dict):
        json_dict = db_dict
        json_dict['rule_confirmations'] = ['dummy_conf'] if db_dict['read_rules'] else []
        return await self.load_json(json_dict)


class Interviews:
    LOG = logging.getLogger("PNBot.Interviews")

    # -- Time Definitions -- #
    TIME_BETWEEN_DISPLAYING_TIMESTAMPS = 5  # In Minutes
    MINUTES_TO_WAIT_BEFORE_ARCHIVE = 5  # In Minutes

    # -- Message Defs -- #
    FINAL_ARCHIVE_NOTICE = "**Archiving Channel!**"

    IGNORED_MESSAGES = [FINAL_ARCHIVE_NOTICE] + Interview.IGNORED_MESSAGES

    def __init__(self, discord_bot: 'PNBot', settings: Dict):
        self.settings = settings
        self.interviews: List[Interview] = []
        self.bot: 'PNBot' = discord_bot
        self.archive_channel: discord.TextChannel = None
        self.archive_channel_webhook: discord.Webhook = None
        self.log_channel = None
        self.archiving_in_progress = False

    def get_by_member(self, member_id: int):
        for interview in self.interviews:
            if interview.member.id == member_id:
                return interview
        return None

    def get_by_channel_id(self, channel_id: int):
        for interview in self.interviews:
            if interview.channel.id == channel_id:
                return interview
        return None

    async def new_interview(self, member: discord.Member, channel: discord.TextChannel) -> Interview:
        interview = Interview(self.bot, self, member, channel)
        self.interviews.append(interview)

        # Initialize and start the Interview.
        await interview.init()
        return interview

    async def init_archive_and_log_channel(self):
        if self.archive_channel is None:
            self.LOG.info("Getting Archive Channel object")
            self.archive_channel = await get_channel(self.bot, self.settings['archive_channel_id'])
            self.archive_channel_webhook = await get_webhook(self.bot, self.archive_channel)
        if self.log_channel is None:
            self.LOG.info("Getting Log Channel object")
            self.log_channel = await get_channel(self.bot, self.settings['log_channel_id'])

    async def close_interview(self, interview, archive=True, message=None):
        self.LOG.info("Closing interview for {}".format(interview.member.display_name))
        self.interviews.remove(interview)
        if message is not None:
            await interview.channel.send(message)

        if archive:
            await self.archive_interview_webhooks(interview, message)
        await interview.channel.delete()
        await db.delete_interview(self.bot.db, interview.channel_id, interview.member_id)
        await backup_interviews_to_db(self)

    async def archive_interview_webhooks(self, interview, message=None):

        if self.archiving_in_progress:
            archive_in_progress_message = await interview.channel.send("** Archiving of other channel in progress. This channel has been queued to be archived.**")
        else:
            archive_in_progress_message = None

        while self.archiving_in_progress:
            await asyncio.sleep(5)

        if archive_in_progress_message is not None:
            await archive_in_progress_message.delete()

        self.archiving_in_progress = True

        try:
            time_remaining = 60 * self.MINUTES_TO_WAIT_BEFORE_ARCHIVE
            archiving_channel_notice: discord.Message = await interview.channel.send("**Archiving Channel in {:.0f} minutes!**".format(time_remaining/60))
            while time_remaining > 0:
                await asyncio.sleep(60)
                time_remaining -= 60
                await archiving_channel_notice.edit(content="**Archiving Channel in {:.0f} minutes!**".format(time_remaining/60))
            await archiving_channel_notice.edit(content=self.FINAL_ARCHIVE_NOTICE)

            await asyncio.sleep(1)
            messages: List[discord.Message] = await interview.channel.history(limit=500, oldest_first=True).flatten()

            await self.archive_channel.send("```     ```")
            avatar = interview.member.avatar_url_as(static_format="png")  # Need to use format other than WebP for image to display on iOS. (I think this is a recent discord bug.)
            await self.archive_channel.send(embed=embeds.archive_header(interview.member.display_name, interview.member.id, avatar, messages[0].created_at))

            delta_between_timestamps = timedelta(minutes=self.TIME_BETWEEN_DISPLAYING_TIMESTAMPS)
            next_timestamp: datetime = messages[0].created_at + delta_between_timestamps

            for i, message in enumerate(messages):
                if i >= 2:
                    sanitized_content = message.clean_content

                    if sanitized_content not in self.IGNORED_MESSAGES:
                        if message.created_at >= next_timestamp:
                            next_timestamp = message.created_at + delta_between_timestamps
                            embed = discord.Embed(color=discord.Colour.light_grey().value, timestamp=message.created_at)
                            embed.set_footer(text=ZERO_WIDTH_CHAR)  # Hack to get timestamp only footer to display on mobile.

                            await self.archive_channel_webhook.send(content=sanitized_content, embed=embed, username=message.author.display_name,
                                                                    avatar_url=message.author.avatar_url)
                        else:
                            if sanitized_content is None or sanitized_content == "":
                                sanitized_content = "*Embed Only Message*"  # TODO: Make this fix better.

                            await self.archive_channel_webhook.send(sanitized_content, username=message.author.display_name, avatar_url=message.author.avatar_url)

                        await asyncio.sleep(0.75)

            self.archiving_in_progress = False

        except Exception as e:  # Yes this is broad, but in this case it's fine since we just clean up then reraise the error.
            # *SOMETHING* bad just happened... Abandon archiving the channel since we can't...
            # but set archiving_in_progress flag back to false so the bot is not stuck in an indeterminate state.
            self.archiving_in_progress = False
            await interview.channel.send(TRIANGLE_EMOJI + "ERROR! Could not archive channel. Please archive, then delete this channel manually. Additionally, please report this error to the bot owner.")
            raise e

    # def dump_json(self) -> str:
    #     interviews_data = []
    #     for interview in self.interviews:
    #         interviews_data.append(interview.dump_dict())
    #     data = {"interviews": interviews_data}
    #     return json.dumps(data, indent=4)

    async def save_to_db(self):
        self.LOG.info("Interviews: save_to_db()")
        self.LOG.info(f"Saving {len(self.interviews)} interviews")
        for interview in self.interviews:
            await interview.save_to_db()


    # async def load_json(self, json_data: str):
    #     data = json.loads(json_data)
    #     self.LOG.info(f"Expecting to load {len(data['interviews'])} interviews from backup file.")
    #     for interview_data in data["interviews"]:
    #         interview_obj = Interview(self.client, self, None, None)
    #         interview_obj = await interview_obj.load_json(interview_data)
    #         if interview_obj is not None:
    #             self.LOG.info("loaded interview")
    #             self.interviews.append(interview_obj)
    #             self.LOG.info("added interview to interviews")
    #
    #     if len(data['interviews']) != len(self.interviews):
    #         self.LOG.warning(f"Could not load all interviews!!! Expected: {len(data['interviews'])}, Got: {len(self.interviews)}")
    #         self.LOG.warning(f"Interview Dump File:\n{data['interviews']}\n")
    #         self.LOG.warning("Loaded Interviews:")
    #         for loaded_interview in self.interviews:
    #             self.LOG.warning(loaded_interview)
    #     elif len(data['interviews']) == 0:
    #         self.LOG.info(f"No interviews in backup file. raw loaded string:\n {data}")
    #     self.LOG.info("Finished loading interviews")
    #     return self


    async def load_db(self, db_data: List[Dict]):
        self.LOG.info(f"Expecting to load {len(db_data)} interviews from database.")
        for interview_data in db_data:
            interview_obj = Interview(self.bot, self, None, None)
            interview_obj = await interview_obj.load_db(interview_data)
            if interview_obj is not None:
                self.LOG.info("loaded interview")
                # Make sure that the interview is not already loaded
                if interview_obj not in self.interviews:
                    self.interviews.append(interview_obj)
                    self.LOG.info("added interview to interviews")
                else:
                    self.LOG.info(f"Avoiding loading duplicate interview belonging to {interview_obj.member.display_name}.")

        if len(db_data) != len(self.interviews):
            self.LOG.warning(
                f"Could not load all interviews!!! Expected: {len(db_data)}, Got: {len(self.interviews)}")
            self.LOG.warning(f"Interview Dump DB:\n{db_data}\n")
            self.LOG.warning("Loaded Interviews:")
            for loaded_interview in self.interviews:
                self.LOG.warning(loaded_interview)
        elif len(db_data) == 0:
            self.LOG.info(f"No interviews in DB. raw loaded string:\n {db_data}")
        self.LOG.info("Finished loading interviews")
        return self

