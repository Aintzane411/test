"""
Extension that implements a custom Embed based help system.
Currently supports:
    General Help Page

Help System Convention: prefix[command_name|alias1|alias...] <req_arg> [opt_arg]

Part of the PNBot.
"""

import logging
import itertools

from typing import List, Optional, Union, Dict
import discord
from discord.ext import commands as dpy_cmds

log = logging.getLogger(__name__)

help_embed_color = 0xF6C57F
bot_name = "PNBot"
bot_description = "PNBot is a bot custom designed for Plural Nest to help assist with interviews, role assignment, and other tasks."
bot_github_link = "https://github.com/amadea-system/PNBot"


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


class EmbedHelp(dpy_cmds.DefaultHelpCommand):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.separate_aliases = kwargs.get('separate_aliases', False)


    async def send_embed(self, embed: discord.embeds):

        dest: discord.abc.Messageable = self.get_destination()
        await dest.send(embed=embed)


    def get_command_signature(self, command):
        """Retrieves the signature portion of the help page.

        Parameters
        ------------
        command: :class:`Command`
            The command to get the signature of.

        Returns
        --------
        :class:`str`
            The signature for the command.
        """

        parent = command.full_parent_name
        if len(command.aliases) > 0 and not self.separate_aliases:
            aliases = '|'.join(command.aliases)
            fmt = '[%s|%s]' % (command.name, aliases)
            if parent:
                fmt = parent + ' ' + fmt
            alias = fmt
        else:
            alias = command.name if not parent else parent + ' ' + command.name

        return '%s%s %s' % (self.clean_prefix, alias, command.signature)

    def get_command_embeded_description(self, command: dpy_cmds.Command) -> List[str]:
        """A utility function to format the embed description block of commands and groups.

        Parameters
        ------------
        command: :class:`Command`
            The command/group to format.
        """
        msg = []
        if command.description:
            msg.append(command.description)
            # msg.append("\n")
        elif command.brief:
            msg.append(command.brief)
            # msg.append("\n")

        signature = self.get_command_signature(command)
        msg.append(f"```{signature}```")

        if command.help:
            msg.append(command.help)

        return msg

    def get_formated_commands(self, commands, *, max_size=None) -> Optional[List[str]]:
        """
        Formats a list of commands with their command signature and short_doc while preserving a max width.
        """

        if not commands:
            return

        msg = []
        max_size = max_size or self.get_max_size(commands)

        get_width = discord.utils._string_width   # TODO: Stop using a protected member.
        for command in commands:
            name = command.name
            width = max_size - (get_width(name) - len(name))
            entry = '{0}`{1:<{width}}`\N{EM QUAD}{2}'.format(self.indent * ' ', command.name, command.short_doc,
                                                             width=width)
            msg.append(self.shorten_text(entry))

        return msg

    def add_examples(self, command: Union[dpy_cmds.Group, dpy_cmds.Command], embed: discord.Embed) -> discord.Embed:
        """Adds any examples the command/group may have as a field """

        if hasattr(command, 'examples') and len(command.examples) > 0:
            parent = command.full_parent_name
            alias = command.name if not parent else parent + ' ' + command.name

            command_signature = f"{self.clean_prefix}{alias}"
            example_msg = []
            for example in command.examples:
                example_msg.append(f"`{command_signature} {example}`")

            example_msg.append("\n")
            example_msg = "\n".join(example_msg)
            field_name = "Examples:" if len(command.examples) > 1 else "Example:"
            embed.add_field(name=field_name, value=example_msg, inline=False)

        return embed

    def add_command_aliases(self, command: Union[dpy_cmds.Group, dpy_cmds.Command], embed: discord.Embed) -> discord.Embed:
        """Adds any command aliases the command/group may have as a field """

        if len(command.aliases) > 0 and self.separate_aliases:
            aliases = ', '.join(command.aliases)
            alias = f"`{command.name}, {aliases}`"
            embed.add_field(name="Aliases:", value=alias, inline=False)

        return embed


    def _get_ending_note(self, group: Optional[dpy_cmds.Group] = None) -> str:
        """Returns help command's ending note. This is mainly useful to override for i18n purposes."""
        command_name = self.invoked_with
        if group and len(group.commands) > 0:
            return "Type {0}{1} command for more info on a command.\n" \
               "You can also type {0}{1} <Sub-Command> for more info on a sub-command.".format(self.clean_prefix, command_name)

        return "Type {0}{1} command for more info on a command.\n" \
               "You can also type {0}{1} category for more info on a category.".format(self.clean_prefix, command_name)


    async def is_user_allowed_help(self, cmd: Union[dpy_cmds.Group, dpy_cmds.Command]) -> bool:
        """
        Checks if the user is allowed to see help for the command.
         This is based on verify_checks and if the user is allowed to run the command.
        """
        if not self.verify_checks:
            return True   # if we do not need to verify the checks then we can just return True

        try:
            return await cmd.can_run(self.context)
        except dpy_cmds.CommandError:
            return False


    async def send_bot_help(self, mapping):
        ctx: dpy_cmds.Context = self.context
        bot: dpy_cmds.Bot = ctx.bot
        dest: discord.abc.Messageable = self.get_destination()

        # TODO: Move this to the error handler.
        if ctx.guild is not None:
            permissions: discord.Permissions = ctx.guild.me.permissions_in(dest)
            if not permissions.embed_links:
                await dest.send(f"Error! {bot_name} must have the `Embed Links` permission in this channel to continue. Please give {bot_name} the `Embed Links` permission and try again."
                                f"\nIf you need assistance, please talk to Amadea System")
                return

        embed = discord.Embed(title=f'{bot_name} Help', color=help_embed_color)

        embed.add_field(name=f"What is {bot_name} for?",
                        value=bot_description)

        embed.set_footer(text="Created by Luna, Hibiki, and Fluttershy aka Amadea System (Hibiki#8792) "
                              f"| Github: {bot_github_link}")

        no_category = '\u200b{0.no_category}:'.format(self)

        def get_category(command, *, no_category=no_category):
            if hasattr(command, 'category') and command.category is not None:
                return f"{command.category}:"

            cog = command.cog
            return cog.qualified_name + ':' if cog is not None else no_category


        filtered = await self.filter_commands(bot.commands, sort=True, key=get_category)
        to_iterate = itertools.groupby(filtered, key=get_category)

        # Now we can add the commands to the page.
        for category, commands in to_iterate:
            commands = sorted(commands, key=lambda c: c.name) if self.sort_commands else list(commands)

            field_values = self.get_formated_commands(commands)
            field_values = split_text(field_values, max_size=1000)
            for i, field_value in enumerate(field_values):
                name = category if i == 0 else "\N{Zero Width Space}"
                embed.add_field(name=name, value=f"{field_value}", inline=False)

        note = self.get_ending_note()
        if note:
            embed.add_field(name="\N{Zero Width Space}", value=note)

        await dest.send(embed=embed)


    async def send_command_help(self, command: dpy_cmds.Command):

        command_name = command.qualified_name
        embed = discord.Embed(title=f'{command_name}  -  {bot_name} Help', color=help_embed_color)

        if not await self.is_user_allowed_help(command):
            embed.description = f"You are not allowed to use the **{command_name}** command.\n"
        else:
            embed_descrip = self.get_command_embeded_description(command)

            embed.description = "\n".join(embed_descrip)

            embed = self.add_command_aliases(command, embed)
            embed = self.add_examples(command, embed)

        await self.send_embed(embed)


    async def send_group_help(self, group: dpy_cmds.Group):
        command_name = group.qualified_name
        embed = discord.Embed(title=f'{command_name}  -  {bot_name} Help', color=help_embed_color)

        if not await self.is_user_allowed_help(group):
            embed.description = f"You are not allowed to use the **{command_name}** command.\n"
        else:
            embed_desc = self.get_command_embeded_description(group)
            embed.description = "\n".join(embed_desc)
            filtered = await self.filter_commands(group.commands, sort=self.sort_commands)
            if len(filtered) > 0:
                field_value = self.get_formated_commands(filtered)  # , heading=self.commands_heading
                embed.add_field(name="Sub-Commands:", value="\n".join(field_value), inline=False)

            embed = self.add_command_aliases(group, embed)
            embed = self.add_examples(group, embed)

            note = self._get_ending_note(group)
            if note:
                embed.add_field(name="\N{Zero Width Space}", value=note, inline=False)

        await self.send_embed(embed)


def setup(bot):
    bot.help_command = EmbedHelp(width=100, indent=0, no_category="Everything Else", separate_aliases=True)
