"""

"""
from __future__ import annotations

from datetime import datetime, timedelta
import json
from typing import Optional, List, Dict
import asyncio
import logging

import discord
from discord.ext import commands

import embeds
from utils import get_channel, get_webhook, backup_interviews


ZERO_WIDTH_CHAR = " ‌‌‌ "
TRIANGLE_EMOJI = "⚠ "


class Interview:
    LOG = logging.getLogger("PNBot.Interview")

    # Interview Types #
    UNKNOWN = "unknown"  # Default starting type

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

    def __init__(self, discord_client: commands.Bot, interviews: Interviews, member: Optional[discord.Member], channel: Optional[discord.TextChannel]):

        # Set by init call
        self.client: commands.Bot = discord_client
        self.interviews: Interviews = interviews
        self.member: discord.Member = member
        self.channel: discord.TextChannel = channel

        # Persistent (Via JSON backup)
        self.member_id = self.member.id if self.member is not None else None
        self.channel_id = self.channel.id if self.channel is not None else None
        self.question_number: int = 0
        self.interview_finished: bool = False

        self.paused: bool = False
        self.started: bool = False  # Not needed unless we decide to care about automatically resuming listening for reacts after reboot.

        self.interview_type = self.UNKNOWN  # self.NEW_SYSTEM  # Default to new system because why not.
        self.rule_confirmations = []

        # Not Persistent
        self.waiting_for_msgs = False
        self.questions = self.interviews.settings['interview_questions']

    def __str__(self):

        if self.interview_finished:
            overall_status = "<@{}> has completed their interview in <#{}>.".format(self.member.id, self.channel.id)
        else:
            overall_status = "<@{}> has an ongoing interview in <#{}>.".format(self.member.id, self.channel.id)

        read_rules = "They have read the rules." if len(self.rule_confirmations) > 0 else "They have NOT read the rules."

        if self.interview_type == self.UNKNOWN:
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

    async def start(self, restarting=False):

        if restarting is False:
            await self.ready()

        if self.interview_type == self.NEW_SYSTEM:
            await self.start_new_interview()

        elif self.interview_type == self.NEW_QUESTIONING:
            await self.start_new_interview()

        elif self.interview_type == self.NEW_SINGLET:
            await self.start_new_interview()

        elif self.interview_type == self.NEW_TULPA:
            await self.start_new_interview()

        elif self.interview_type == self.EXISTING_USER:
            await self.start_existing_system_prompt()

        elif self.interview_type == self.OTHER:
            await self.start_other_prompt()

        elif self.interview_type == self.UNKNOWN:
            # We should never get here, default to contacting team member.
            await self.start_other_prompt()

    async def restart(self):
        self.question_number: int = 0
        self.interview_finished: bool = False
        self.interview_type = self.UNKNOWN
        self.waiting_for_msgs = False
        await self.start()

    async def start_new_interview(self):
        def check(m: discord.Message):
            return m.author.id == self.member.id and m.channel == self.channel and self.paused is False and m.content.strip().lower() != "{}pause".format(self.client.command_prefix)

        self.waiting_for_msgs = True
        while True:
            await self.send_next_question()
            msg = await self.client.wait_for('message', check=check)
            self.LOG.info(msg.content)
            if self.question_number >= len(self.questions[self.interview_type]):
                async with self.channel.typing():
                    await asyncio.sleep(1.5)
                    self.interview_finished = True
                    await self.channel.send(self.FINAL_INTERVIEW_MESSAGE)
                break

    async def start_existing_system_prompt(self):
        self.interview_finished = True
        await self.channel.send("Please have your account that is already present on {guild.name} vouch that this new account belongs to them in <#{}> and then ping staff.".format(self.interviews.settings['welcome_channel_id'], guild=self.channel.guild, user=self.member))

    async def start_other_prompt(self):
        self.interview_finished = True
        other_prompt_messgage = "{user.display_name} would you please tell us how we may help you and a <@&{team_role_id}> member will be with you as soon as possible. Thank you!".format(guild=self.channel.guild, user=self.member, team_role_id=self.interviews.settings['team_role_id'])
        await self.channel.send(other_prompt_messgage)

    async def ready(self):
        # Ready_msg has a 0width char in the beginning.
        # ready_msg = await self.channel.send(
        #     " ‌‌‌ \nIf your system is new to {guild.name}, please click ✅ when you are ready to start your interview. \nIf your system already has an account on {guild.name}, please click 👥.\n".format(guild=self.channel.guild, user=self.member))
        tulpa_emoji = "<:tupla:652995996468379677>"
        alt_account_emoji = "<:altAccount:652989510996721675>"
        new_user_interview_prompt = " ‌‌‌ \nIf you are **new to {guild.name}** or have been **gone for more than 30 days**  please click on the reaction that applies to you:\n\n" \
                                    "*Plural System:* 👥\n" \
                                    "*Questioning whether or not you are a system:* ❓\n" \
                                    "*Singlet (A person who is not plural):* 👤\n" \
                                    "*Looking to make a tulpa:* {tulpa}\n\n".format(guild=self.channel.guild, user=self.member, tulpa=tulpa_emoji)
        alt_account_prompt = "If you already have an account on {guild.name}, please click {emoji}.\n\n".format(guild=self.channel.guild, user=self.member, emoji=alt_account_emoji)
        other_prompt = "If you need to speak to {guild.name} staff, if you would prefer to take your interview over DM, or for anything else, please click ℹ️\n".format(
                guild=self.channel.guild, user=self.member)

        # ready_msg = await self.channel.send(
        #     " ‌‌‌ \nIf you are a system and you are new to {guild.name}, please click 👥 when you are ready to start your interview. \n"
        #     "If you already have an account on {guild.name}, please click 👥.\n".format(
        #         guild=self.channel.guild, user=self.member))
        embed = discord.Embed()
        embed.description = new_user_interview_prompt + alt_account_prompt + other_prompt
        # ready_msg = await self.channel.send(new_user_interview_prompt+alt_account_prompt+other_prompt)
        ready_msg = await self.channel.send(embed=embed)

        emojis = ["👥", "❓", "👤", "<:tupla:652995996468379677>", "<:altAccount:652989510996721675>", "ℹ️"]
        for emoji in emojis:
            await ready_msg.add_reaction(emoji)

        def check(_reaction, _user):
            return _user == self.member and str(_reaction.emoji) in emojis

        reaction, user = await self.client.wait_for('reaction_add', check=check)
        self.started = True
        if str(reaction.emoji) == "👥":
            self.interview_type = self.NEW_SYSTEM
        elif str(reaction.emoji) == "❓":
            self.interview_type = self.NEW_QUESTIONING
        elif str(reaction.emoji) == "👤":
            self.interview_type = self.NEW_SINGLET
        elif str(reaction.emoji) == "<:tupla:652995996468379677>":
            self.interview_type = self.NEW_TULPA
        elif str(reaction.emoji) == "<:altAccount:652989510996721675>":
            self.interview_type = self.EXISTING_USER
        elif str(reaction.emoji) == "ℹ️":
            self.interview_type = self.OTHER

        return

    async def send_next_question(self):
        try:
            if not self.paused:
                async with self.channel.typing():
                    await asyncio.sleep(1.1)
                    await self.channel.send(self.questions[self.interview_type][self.question_number])
                    self.question_number += 1
        except Exception as e:
            self.LOG.exception(e)

    async def pause(self):
        self.paused = True
        await self.channel.send("The interview has been paused. You may resume the interview with `{}resume`".format(self.client.command_prefix))

    async def resume(self):
        self.paused = False
        await self.channel.send("The interview has been resumed.")
        if self.question_number > 0:
            self.question_number -= 1
        if self.waiting_for_msgs:
            await self.send_next_question()
        else:
            await self.start(restarting=True)

    async def prompt_to_resume(self):
        if not self.interview_finished:
            await self.channel.send("Apologies for the interruption, Please type **{}resume** to continue your interview.".format(self.client.command_prefix))

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
        # raise NotImplementedError
        return json.dumps(self.dump_dict, indent=4)

    async def load_json(self, json_data: dict):
        # raise NotImplementedError

        # TODO: Add error handling.
        self.question_number = json_data["question_number"]
        self.interview_finished = json_data["interview_finished"]
        self.paused = json_data["paused"]
        self.interview_type = json_data['interview_type']
        self.rule_confirmations = json_data["rule_confirmations"]

        self.channel_id = json_data["channel_id"]

        self.channel = await get_channel(self.client, json_data["channel_id"])

        self.member_id = json_data["member_id"]

        if self.channel is not None:
            self.member = self.channel.guild.get_member(json_data["member_id"])
        else:
            self.LOG.warning(f"Could not find channel matching: {self.channel_id}!! Interview for {self.member_id} will not be loaded!!")

        if self.member is None and self.channel is not None:
            self.LOG.warning(
                f"Found channel matching {self.channel_id}({self.channel.name}), but could not find member matching: {self.member_id}!! Corresponding interview will not be loaded!!")

        if self.member is not None and self.channel is not None:
            await self.prompt_to_resume()
            return self
        else:
            return


class Interviews:
    LOG = logging.getLogger("PNBot.Interviews")

    # -- Time Definitions -- #
    TIME_BETWEEN_DISPLAYING_TIMESTAMPS = 5  # In Minutes
    MINUTES_TO_WAIT_BEFORE_ARCHIVE = 5  # In Minutes

    # -- Message Defs -- #
    FINAL_ARCHIVE_NOTICE = "**Archiving Channel!**"

    IGNORED_MESSAGES = [FINAL_ARCHIVE_NOTICE] + Interview.IGNORED_MESSAGES

    def __init__(self, discord_client: commands.Bot, settings: Dict):
        self.settings = settings
        self.interviews: List[Interview] = []
        self.client: commands.Bot = discord_client
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

    def new_interview(self, member: discord.Member, channel: discord.TextChannel) -> Interview:
        interview = Interview(self.client, self, member, channel)
        self.interviews.append(interview)

        #TODO: Call backup interview here. Remove from on User join.
        return interview

    async def init_archive_and_log_channel(self):
        if self.archive_channel is None:
            self.LOG.info("Getting Archive Channel object")
            self.archive_channel = await get_channel(self.client, self.settings['archive_channel_id'])
            self.archive_channel_webhook = await get_webhook(self.client, self.archive_channel)
        if self.log_channel is None:
            self.LOG.info("Getting Log Channel object")
            self.log_channel = await get_channel(self.client, self.settings['log_channel_id'])

    async def close_interview(self, interview, archive=True, message=None):
        self.LOG.info("Closing interview for {}".format(interview.member.display_name))
        self.interviews.remove(interview)
        if archive:
            await self.archive_interview_webhooks(interview, message)
        await interview.channel.delete()
        backup_interviews(self)

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
                            await self.archive_channel_webhook.send(sanitized_content, username=message.author.display_name, avatar_url=message.author.avatar_url)

                        await asyncio.sleep(0.75)

            self.archiving_in_progress = False

        except Exception as e:  # Yes this is broad, but in this case it's fine since we just clean up then reraise the error.
            # *SOMETHING* bad just happened... Abandon archiving the channel since we can't...
            # but set archiving_in_progress flag back to false so the bot is not stuck in an indeterminate state.
            self.archiving_in_progress = False
            await interview.channel.send(TRIANGLE_EMOJI + "ERROR! Could not archive channel. Please archive, then delete this channel manually. Additionally, please report this error to the bot owner.")
            raise e

    def dump_json(self) -> str:
        interviews_data = []
        for interview in self.interviews:
            interviews_data.append(interview.dump_dict())
        data = {"interviews": interviews_data}
        return json.dumps(data, indent=4)

    async def load_json(self, json_data: str):
        data = json.loads(json_data)
        self.LOG.info(f"Expecting to load {len(data['interviews'])} interviews from backup file.")
        for interview_data in data["interviews"]:
            interview_obj = Interview(self.client, self, None, None)
            interview_obj = await interview_obj.load_json(interview_data)
            if interview_obj is not None:
                self.LOG.info("loaded interview")
                self.interviews.append(interview_obj)
                self.LOG.info("added interview to interviews")

        if len(data['interviews']) != len(self.interviews):
            self.LOG.warning(f"Could not load all interviews!!! Expected: {len(data['interviews'])}, Got: {len(self.interviews)}")
            self.LOG.warning(f"Interview Dump File:\n{data['interviews']}\n")
            self.LOG.warning("Loaded Interviews:")
            for loaded_interview in self.interviews:
                self.LOG.warning(loaded_interview)
        elif len(data['interviews']) == 0:
            self.LOG.info(f"No interviews in backup file. raw loaded string:\n {data}")
        self.LOG.info("Finished loading interviews")
        return self

