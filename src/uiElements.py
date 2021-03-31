"""


"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional, Dict, List, Union, Tuple, NamedTuple, Callable, Any

import discord
from discord.ext import commands

if TYPE_CHECKING:
    from pDB import RoleCategory, AllowedRole


class DiscordPermissionsError(Exception):
    pass


class CannotAddReactions(DiscordPermissionsError):
    def __init__(self):
        super().__init__(f"Insufficient permissions to add reactions to user interface!\n"
                         f"Please have an admin add the **Add Reactions** and **Read Message History** permissions to this bot and make sure that the channel you are using commands in is configured to allow those permissions as well.")


class CannotEmbedLinks(DiscordPermissionsError):
    def __init__(self):
        super().__init__('Bot does not have embed links permission in this channel.')


class CannotSendMessages(DiscordPermissionsError):
    def __init__(self):
        super().__init__('Bot cannot send messages in this channel.')


class CannotAddExtenalReactions(DiscordPermissionsError):
    def __init__(self):
        super().__init__(f"Gabby Gums is missing the **Use External Emojis** Permission!\n"
                         f"Please have an admin add the **Use External Emojis** permissions to this bot and make sure that the channel you are using commands in is configured to allow External Emojis as well.")



async def do_nothing(*args, **kwargs):
    pass


@dataclass
class PageResponse:
    """Data Storage class for returning the user response (if any) and the UI Message(es) that the Page sent out."""
    response: Optional[Any]
    ui_message: Optional[discord.Message]
    # user_messages: List[discord.Message] = field(default_factory=[])

    def __str__(self):
        return str(self.content())

    def content(self):
        if isinstance(self.response, str):
            return self.response
        elif isinstance(self.response, discord.Message):
            return self.response.content
        else:
            return self.response

    def c(self):
        return self.content()


class Page:
    """
    An interactive form that can be interacted with in a variety of ways including Boolean reaction, string input, non-interactive response message, soon to be more.
    Calls a Callback with the channel and response data to enable further response and appropriate handling of the data.
    """
    LOG = logging.getLogger("PNBot.Page")

    def __init__(self, name: Optional[str] = None, body: Optional[str] = None,
                 callback: Callable = do_nothing, additional: str = None, embed: Optional[discord.Embed] = None, image = None,
                 previous_msg: Optional[Union[discord.Message, PageResponse]] = None, timeout: int = 120.0):
        """

        :param name: The header of a Text Message based Page. Ignored if embed is used.
        :param body: The body of a Text Message based Page. Ignored if embed is used.
        :param callback: The callback function that gets called to handle the user input.
        :param additional: The footer of a Text Message based Page. Ignored if embed is used.
        :param embed: The embed that is used for a Embed based Page.
        :param image: Includes an image?
        :param previous_msg: The last UI message sent. Used for edit in place? Can be either a discord msg Object, or a PageResponse Object
        :param timeout: How long, in seconds, till the UI times out from inactivity.
        """

        self.name = name
        self.body = body
        self.additional = additional

        self.embed = embed

        self.image = image
        self.timeout = timeout

        self.callback = callback
        self.prev = previous_msg.ui_message if isinstance(previous_msg, PageResponse) else previous_msg

        self.response = None
        self.page_message: Optional[discord.Message] = None
        self.user_message: Optional[discord.Message] = None

        self.running = False

        self._can_remove_reactions = False

    async def run(self, ctx: commands.Context, new_embed: Optional[discord.Embed] = None):
        pass

    def construct_std_page_msg(self) -> str:
        page_msg = ""
        if self.name is not None:
            page_msg += "**{}**\n".format(self.name)

        if self.body is not None:
            page_msg += "{}\n".format(self.body)

        if self.additional is not None:
            page_msg += "{}\n".format(self.additional)

        # self.page_message = page_message
        return page_msg

    @staticmethod
    async def cancel(ctx, self):
        await self.remove()
        await ctx.send("Canceled!")

    async def remove(self, user: bool = True, page: bool = True):
        pass

        # if self.previous is not None:
        #     await self.previous.remove(user, page)
        #
        # try:
        #     if user and self.user_message is not None:
        #         await self.user_message.delete(delay=1)
        # except Exception:
        #     pass
        #
        # try:
        #     if page and self.page_message is not None:
        #         await self.page_message.delete(delay=1)
        # except Exception:
        #     pass


class BoolPage(Page):

    def __init__(self, name: Optional[str] = None, body: Optional[str] = None,
                 callback: Callable = do_nothing, additional: str = None, embed: Optional[discord.Embed] = None, previous_msg: Optional[Union[discord.Message, PageResponse]] = None, timeout: int = 120.0):
        """
        Callback signature: page: reactMenu.Page, _client: commands.Bot, ctx: commands.Context, response: bool
        """
        self.ctx = None
        self.match = None
        self.canceled = False

        super().__init__(name=name, body=body, callback=callback, additional=additional, embed=embed, previous_msg=previous_msg, timeout=timeout)


    async def run(self, ctx: commands.Context, new_embed: Optional[discord.Embed] = None):
        """
        Callback signature: page: reactMenu.Page, _client: commands.Bot, ctx: commands.Context, response: bool
        """
        self.ctx = ctx
        channel: discord.TextChannel = ctx.channel
        author: discord.Member = ctx.author
        message: discord.Message = ctx.message

        if self.embed is None:
            self.page_message = await channel.send(self.construct_std_page_msg())
        else:
            self.page_message = await channel.send(self.construct_std_page_msg(), embed=self.embed)

        try:
            await self.page_message.add_reaction("✅")
            await self.page_message.add_reaction("❌")
        except discord.Forbidden as e:
            await ctx.send(
                f"CRITICAL ERROR!!! \n{ctx.guild.me.name} does not have the `Add Reactions` permissions!. Please have an Admin fix this issue and try again.")
            raise e


        def react_check(_reaction: discord.Reaction, _user):
            self.LOG.info("Checking Reaction: Reacted Message: {}, orig message: {}".format(_reaction.message.id,
                                                                                            self.page_message.id))

            return _user == ctx.author and (str(_reaction.emoji) == '✅' or str(_reaction.emoji) == '❌')


        try:
            reaction, react_user = await self.ctx.bot.wait_for('reaction_add', timeout=self.timeout, check=react_check)
            if str(reaction.emoji) == '✅':
                self.response = True
                # await self.remove()
                await self.page_message.clear_reactions()
                await self.callback(self, self.ctx.bot, ctx, True)
                return True
            elif str(reaction.emoji) == '❌':
                self.response = False
                # await self.remove()
                await self.page_message.clear_reactions()
                await self.callback(self, self.ctx.bot, ctx, False)
                return False

        except asyncio.TimeoutError:
            # await self.remove()
            await self.page_message.clear_reactions()
            return None


class StringReactPage(Page):
    # cancel_emoji = '🛑'

    def __init__(self, buttons: List[Tuple[Union[discord.PartialEmoji, str], Any]] = None, allowable_responses: Optional[List[str]] = None, allow_any_response: bool = False,
                 cancel_btn=True, edit_in_place=False, remove_msgs=True, cancel_emoji: Optional[str] = None, cancel_btn_loc: Optional[int] = None, **kwrgs):
        """
        Callback signature: ctx: commands.Context, page: reactMenu.Page

        name: Optional[str] = None, body: Optional[str] = None,
        callback: Callable = do_nothing, additional: str = None, embed: Optional[discord.Embed] = None,
        previous_msg: Optional[Union[discord.Message, PageResponse]] = None, timeout: int = 120.0

        :param name: The header of a Text Message based Page. Ignored if embed is used.         Optional[str]
        :param body: The body of a Text Message based Page. Ignored if embed is used.           Optional[str]
        :param callback: The callback function that gets called to handle the user input.       Callable
        :param additional: The footer of a Text Message based Page. Ignored if embed is used.   Optional[str]
        :param embed: The embed that is used for a Embed based Page.                            discord.Embed
        :param image: Includes an image?
        :param previous_msg: The last UI message sent. Used for edit in place? Can be either a discord msg Object, or a PageResponse Object
        :param timeout: How long, in seconds, till the UI times out from inactivity. Default 120s  int

        :param allowable_responses: Restrict the valid options the user can send the bot. Not case sensitive.
        :param cancel_btn: Should a cancel button be included in the UI element.
        :param edit_in_place: If true, the UI will edit the first embed when a new screen is sent. Otherwise a new embed will be sent every time.
        :param remove_msgs:
        :param cancel_emoji: Overrides the default cancel_btn emoji
        :param cancel_btn_loc: Specify where the cancel button will be located
        """
        self.ctx = None
        self.match = None
        self.cancel_btn = cancel_btn
        # self.allow_any_response = allow_any_response
        self.allowable_responses = allowable_responses or []
        self.clean_allowable_responses = [allowed_rsp.lower().strip() for allowed_rsp in self.allowable_responses]

        self.edit_in_place = edit_in_place
        self.canceled = False
        self.buttons = buttons or []
        self.sent_msg = []
        self._reaction_match = None
        self.remove_msgs = remove_msgs
        self.match_type = None
        self.cancel_emoji = cancel_emoji or "❌"

        if self.cancel_btn and cancel_btn_loc is None:
            self.buttons.append((self.cancel_emoji, None))

        elif self.cancel_btn and cancel_btn_loc is not None:
            self.buttons.insert(cancel_btn_loc, (self.cancel_emoji, None))

        super().__init__(**kwrgs)

    async def run(self, ctx: commands.Context, new_embed: Optional[discord.Embed] = None, send_new_msg=True):
        """
        Callback signature: page: reactMenu.Page

        :param new_embed: Replaces the currently stored embed with a new embed
        :param send_new_msg:
        """
        self.ctx = ctx
        channel: discord.TextChannel = ctx.channel
        author: discord.Member = ctx.author
        message: discord.Message = ctx.message

        if send_new_msg:
            await self.check_permissions()
            if new_embed is not None:
                self.embed = new_embed

            self.page_message = await self.send(self.construct_std_page_msg(), embed=self.embed, image=self.image)

            if not self.running or not self.edit_in_place:
                async def add_reactions():
                    for (reaction, _) in self.buttons:
                        try:
                            await self.page_message.add_reaction(reaction)
                        except discord.Forbidden:
                            raise CannotAddReactions()

                loop: asyncio.AbstractEventLoop = ctx.bot.loop
                task = loop.create_task(add_reactions())

        self.running = True

        while True:

            done, pending = await asyncio.wait([
                self.ctx.bot.wait_for('raw_reaction_add', timeout=self.timeout, check=self.react_check),
                self.ctx.bot.wait_for('message', timeout=self.timeout, check=self.msg_check)
            ], return_when=asyncio.FIRST_COMPLETED)

            try:
                stuff = done.pop().result()

            except asyncio.TimeoutError:
                # await ctx.send("Command timed out.")
                # await self.remove()
                if self.embed is None:
                    await ctx.send("Timed Out!")
                # await ctx.send("Done!")
                return None

            except Exception as e:
                self.LOG.exception(e)
            # if any of the tasks died for any reason,
            #  the exception will be replayed here.

            for future in pending:
                future.cancel()  # we don't need these anymore

            if self.canceled:
                # await self.remove()
                # await ctx.send("Done!")
                return None

            if self.match is not None and len(self.allowable_responses) > 0 and self.match_type != "react":
                # self.LOG.info(f"Got: {self.match}")
                if self.match.lower().strip() not in self.clean_allowable_responses:
                    content = self.match
                    if content.startswith(ctx.bot.command_prefix):
                        self.sent_msg.append(
                            await self.ctx.send(f"It appears that you used a command while a menu system is still running. Disregarding the input."))
                    else:
                        self.sent_msg.append(await self.ctx.send(f"`{content}` is not a valid choice. Please try again."))

                    # Force match and canceled to be None/False to loop around and let the user try again.
                    self.match = None
                    self.canceled = False

            if self.match is not None:
                if callable(self.match):
                    await self.match(self.ctx, self)

                # (self.edit_in_place or not self.remove_msgs)
                if not self.edit_in_place and self.remove_msgs:
                    await self.remove()
                else:
                    await self.reset_user_react()

                return PageResponse(response=self.match, ui_message=self.prev)


    async def reset_user_react(self):
        """Removes the reaction the user last made"""

        if discord.utils.find(lambda m: len(m) > 0 and m[0] == self._reaction_match, self.buttons) and self._can_remove_reactions:
            try:
                await self.page_message.remove_reaction(self._reaction_match, self.ctx.author)
            except (discord.Forbidden, discord.NotFound, discord.InvalidArgument, discord.HTTPException):
                pass

            self._reaction_match = None


    async def remove_bot_react(self, react):
        """Removes a reaction made by this bot"""
        try:
            await self.page_message.remove_reaction(react, self.ctx.bot.user)
        except (discord.Forbidden, discord.NotFound, discord.InvalidArgument, discord.HTTPException):
            pass


    def react_check(self, payload):
        """Uses raw_reaction_add"""
        if len(self.buttons) == 0:
            return False
        if payload.user_id != self.ctx.author.id:
            return False

        if payload.message_id != self.page_message.id:
            return False

        if self.cancel_emoji == str(payload.emoji):
            self.canceled = True
            self._reaction_match = str(payload.emoji)
            self.match_type = "react"
            return True

        to_check = str(payload.emoji)
        for (emoji, func) in self.buttons:
            if to_check == emoji:
                self.match = func
                self._reaction_match = emoji
                self.match_type = "react"
                return True

        return False

    def msg_check(self, _msg: discord.Message):
        """Uses on_message"""

        if _msg.author.id != self.ctx.author.id:
            return False

        if _msg.channel.id != self.page_message.channel.id:
            return False

        # if _msg.content.lower().strip() not in self.clean_allowable_responses:  # _msg.content.lower().strip() not in self.allowable_responses
        #     return False

        self.LOG.info(f"returning: true. content: {_msg.content}")
        self.match = _msg.content
        self.match_type = "string"
        return True


    async def check_permissions(self):
        if self.ctx is not None and self.ctx.guild is not None:
            permissions = self.ctx.channel.permissions_for(self.ctx.guild.me)
            self._verify_permissions(self.ctx, permissions)
        #
        # if self.prev is None and not self._can_remove_reactions:
        #     # Only send this warning message the first time the menu system is activated.
        #     await self.ctx.send(f"\N{WARNING SIGN}\ufe0f Gabby Gums is missing the `Manage Messages` permission!\n"
        #                         f"While you can continue without giving Gabby Gums this permission, you will experience a suboptimal menu system experience.")

    def _verify_permissions(self, ctx, permissions):
        if not permissions.send_messages:
            raise CannotSendMessages()

        if self.embed is not None and not permissions.embed_links:
            raise CannotEmbedLinks()

        self._can_remove_reactions = permissions.manage_messages

        if len(self.buttons) > 0:
            if not permissions.add_reactions:
                raise CannotAddReactions()
            if not permissions.read_message_history:
                raise CannotAddReactions()
            if not permissions.external_emojis:
                raise CannotAddExtenalReactions()

    async def update_buttons(self, new_buttons: List[Tuple[Union[discord.PartialEmoji, str], Any]]):

        old_buttons_set = set(self.buttons)
        new_buttons_set = set(new_buttons)
        buttons_to_remove = old_buttons_set.difference(new_buttons_set)
        buttons_to_add = new_buttons_set.difference(old_buttons_set)

        self.buttons = new_buttons or []

        if self.cancel_btn:  # and cancel_btn_loc is None:
            self.buttons.append((self.cancel_emoji, None))
            buttons_to_add.add((self.cancel_emoji, None))

        for react, _ in self.buttons:
            await self.remove_bot_react(react)
        if self.cancel_btn:
            await self.remove_bot_react(self.cancel_emoji)

        if self.edit_in_place:
            async def modify_reactions():
                # remove_reactions():
                try:
                    await self.page_message.clear_reactions()
                except (discord.Forbidden, discord.NotFound, discord.InvalidArgument, discord.HTTPException):
                    for (reaction, _) in buttons_to_remove:
                        await self.remove_bot_react(reaction)

                # add reactions
                for (reaction, _) in buttons_to_add:
                    try:
                        await self.page_message.add_reaction(reaction)
                    except discord.Forbidden:
                        raise CannotAddReactions()

            loop: asyncio.AbstractEventLoop = self.ctx.bot.loop
            task = loop.create_task(modify_reactions())


    async def send(self, content: Optional[str] = None, embed: Optional[discord.Embed] = None, image: Optional[discord.File] = None) -> discord.Message:

        if self.prev and self.edit_in_place:
            await self.prev.edit(content=content, embed=embed, file=image)
        else:
            self.prev = await self.ctx.send(content=content, embed=embed, file=image)
            self.sent_msg.append(self.prev)
        return self.prev


    async def remove(self, user: bool = True, page: bool = True):

        # if self.previous is not None:
        #     await self.previous.remove(user, page)
        if self.remove_msgs:

            try:
                if user and self.user_message is not None:
                    await self.user_message.delete(delay=1)
            except Exception:
                pass

            try:
                for msg in self.sent_msg:
                    if page and msg is not None:
                        await msg.delete(delay=1)

            except Exception:
                pass


    async def finish(self, last_embed: Optional[discord.Embed] = None):
        """Remove all reactions and edit the embed with a given finish embed"""

        if last_embed is not None:
            await self.send(embed=last_embed, image=self.image)

        if self._can_remove_reactions and (self.edit_in_place or not self.remove_msgs):
            try:
                await self.page_message.clear_reactions()
            except (discord.Forbidden, discord.NotFound, discord.InvalidArgument, discord.HTTPException):
                pass
        elif self.edit_in_place or not self.remove_msgs:
            # If we don't have permissions to remove ALL reactions, just remove the reactions we made.
            for react, _ in self.buttons:
                await self.remove_bot_react(react)
            if self.cancel_btn:
                await self.remove_bot_react(self.cancel_emoji)








