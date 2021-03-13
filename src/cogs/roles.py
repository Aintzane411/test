"""
Cog containing various PNBot Role Management commands.
Commands include:

Part of PNBot.
"""

import logging

from math import ceil
from typing import TYPE_CHECKING, Optional, Dict, List, Union, Tuple

import discord
from discord.ext import commands
import eCommands

import pDB
from utilities.utils import send_embed, pn_embed, is_team_member, is_server_member, purge_deleted_roles
from utilities.roleParser import parse_csv_roles, BetterRoleConverter
from embeds import add_and_removed_roles_embed
# from utilities.paginator import FieldPages

from uiElements import StringReactPage, BoolPage

if TYPE_CHECKING:
    from PNDiscordBot import PNBot
    import asyncpg

# TODO: For ALL functions in this file: Make sure that we don't send too much text in embeds


log = logging.getLogger(__name__)

MAX_NUMBER_OF_CATS = 9

number_emotes = [
    "\N{DIGIT ZERO}\N{VARIATION SELECTOR-16}\N{COMBINING ENCLOSING KEYCAP}",
    "\N{DIGIT ONE}\N{VARIATION SELECTOR-16}\N{COMBINING ENCLOSING KEYCAP}",
    "\N{DIGIT TWO}\N{VARIATION SELECTOR-16}\N{COMBINING ENCLOSING KEYCAP}",
    "\N{DIGIT THREE}\N{VARIATION SELECTOR-16}\N{COMBINING ENCLOSING KEYCAP}",
    "\N{DIGIT FOUR}\N{VARIATION SELECTOR-16}\N{COMBINING ENCLOSING KEYCAP}",
    "\N{DIGIT FIVE}\N{VARIATION SELECTOR-16}\N{COMBINING ENCLOSING KEYCAP}",
    "\N{DIGIT SIX}\N{VARIATION SELECTOR-16}\N{COMBINING ENCLOSING KEYCAP}",
    "\N{DIGIT SEVEN}\N{VARIATION SELECTOR-16}\N{COMBINING ENCLOSING KEYCAP}",
    "\N{DIGIT EIGHT}\N{VARIATION SELECTOR-16}\N{COMBINING ENCLOSING KEYCAP}",
    "\N{DIGIT NINE}\N{VARIATION SELECTOR-16}\N{COMBINING ENCLOSING KEYCAP}",
    "\N{KEYCAP TEN}",
]

number_buttons = [(number_emotes[i], i) for i in range(len(number_emotes))]


class AdminAddAllowedRoles:
    navigation_buttons = [
        ("\N{Leftwards Black Arrow}", "left_button"),
        ("\N{Black Rightwards Arrow}", "right_button"),
    ]

    def __init__(self, cats: pDB.RoleCategories):

        self.role_cats = cats.cats
        self.ctx: Optional[commands.Context] = None
        # self.cat_names = [cat.cat_name for cat in role_cats]
        num_of_buttons = len(self.role_cats) if len(self.role_cats) <= len(number_emotes) else len(number_emotes)

        buttons = [(number_emotes[i], self.role_cats[i].cat_name) for i in range(num_of_buttons)]
        self.cat_names_w_buttons = []

        for i, cat in enumerate(self.role_cats):
            if i < len(number_emotes):
                self.cat_names_w_buttons.append(f"{number_emotes[i]}  {cat.cat_name}")
            else:
                self.cat_names_w_buttons.append(f"    {cat.cat_name}")

        cat_desc = "\n".join(self.cat_names_w_buttons)
        self.embed = pn_embed(title="Select A Role Category", desc=f"Click a react or send the name to select\n\n{cat_desc}")

        self.ui = StringReactPage(embed=self.embed, buttons=buttons, allowable_responses=self.cat_names_w_buttons, remove_msgs=False)

        self.selected_cat = ""

    async def run(self, ctx: commands.Context):
        self.ctx = ctx
        await self.prompt_for_category()

        # Clean up and remove the reactions
        await self.ui.finish()

    async def prompt_for_category(self, refreshed_embed=None):
        response = await self.ui.run(self.ctx, new_embed=refreshed_embed)

        if response is None:
            await self.ctx.send(embed=pn_embed(title="Add Role Canceled"))
            return

        self.selected_cat = response.content()

        log.info(f"Selected: {self.selected_cat}")

        # Clean up and remove the reactions from the `Category Prompt` before self.prompt_for_new_roles() creates a new UI
        await self.ui.finish()

        await self.prompt_for_new_roles()


    async def prompt_for_new_roles(self, refreshed_embed=None):
        cat: pDB.RoleCategory = discord.utils.find(lambda x: x.cat_name.lower().strip() == self.selected_cat.lower().strip(), self.role_cats)

        self.embed = pn_embed(title=f"Add Roles to *{cat.cat_name}*",
                              desc="You may send a single role, or multiple roles separated by a comma.")

        self.ui = StringReactPage(embed=self.embed, remove_msgs=False)

        response = await self.ui.run(self.ctx, new_embed=refreshed_embed)
        if response is None:
            await self.ctx.send(embed=pn_embed(title="Add Role Canceled"))
            return

        unparsed_roles = response.content()

        parsed_roles = await parse_csv_roles(self.ctx, unparsed_roles, parse_all=True)
        if parsed_roles is None:
            await self.ctx.send(embed=pn_embed(title="ERROR!!! Could not parse roles!"))
            return

        # Add the roles to the DB.
        for role in parsed_roles.good_roles:
            await cat.add_new_role(role.id)

        status_embed = add_and_removed_roles_embed(parsed_roles, disallowed_field_name="The following roles could not be added as they have *Moderator Level* permissions:")

        await self.ctx.send(embed=status_embed)
        return

    # async def prompt_for_role(self, ctx: commands.Context, refreshed_embed=None):
    #     cat: pDB.RoleCategory = discord.utils.find(lambda x: x.cat_name.lower() == self.selected_cat, self.role_cats)
    #     roles = await cat.get_roles()
    #
    #     response = await self.ui.run(ctx, new_embed=refreshed_embed)
    #
    #     if response is None:
    #         await ctx.send(embed=pn_embed(desc="Add Role Canceled"))
    #         return
    #
    #     self.selected_cat = response.content()
    #     log.info(f"Selected: {self.selected_cat}")

    # async def construct_category_selection_embed


class AdminRemoveAllowedRoles:
    navigation_buttons = [
        ("\N{Leftwards Black Arrow}", "left_button"),
        ("\N{Black Rightwards Arrow}", "right_button"),
    ]


    def __init__(self):

        self.ctx: Optional[commands.Context] = None
        self.ui = None

    async def run(self, ctx: commands.Context):
        self.ctx = ctx
        await self.prompt_for_roles_to_remove()

        # Clean up and remove the reactions
        await self.ui.finish()

    async def prompt_for_roles_to_remove(self):

        allowed_roles = await pDB.get_roles_in_guild(self.ctx.bot.db, self.ctx.guild.id)
        purged_roles = await purge_deleted_roles(self.ctx, allowed_roles)
        if len(purged_roles) > 0:
            purged_role_msg = f"\n\n(Note, {len(purged_roles)} roles that were previously deleted from discord have been purged.)"
        else:
            purged_role_msg = f""

        embed = pn_embed(title=f"Send Roles to Remove",
                         desc=f"You may send a single role, or multiple roles separated by a comma.{purged_role_msg}")

        self.ui = StringReactPage(embed=embed, remove_msgs=False)

        response = await self.ui.run(self.ctx)
        if response is None:
            await self.ctx.send(embed=pn_embed(title="Remove Roles Canceled"))
            return

        unparsed_roles = response.content()

        parsed_roles = await parse_csv_roles(self.ctx, unparsed_roles, parse_all=True, allow_privileged_roles=True)
        if parsed_roles is None:
            await self.ctx.send(embed=pn_embed(title="ERROR!!! Could not parse roles!"))
            return

        status_embed = pn_embed(
            title=f"{len(parsed_roles.good_roles)} out of {len(parsed_roles.good_roles) + len(parsed_roles.bad_roles)} roles removed:")

        # Remove the roles from the DB.
        for role in parsed_roles.good_roles:
            # cat: pDB.RoleCategory = discord.utils.find(lambda x: x.role_in(role), self.role_cats)
            await pDB.delete_role(self.ctx.bot.db, self.ctx.guild.id, role.id)

        if len(parsed_roles.good_roles) > 0:
            good_roles_msg = ", ".join([f"<@&{role.id}>" for role in parsed_roles.good_roles])
            status_embed.add_field(name="Successfully removed:", value=good_roles_msg, inline=False)

        if len(parsed_roles.bad_roles) > 0:
            bad_roles_msg = ", ".join([f"{role}" for role in parsed_roles.bad_roles])
            suggestion_strs = [f"<@&{role.best_match.id}>" for role in parsed_roles.bad_roles if
                               role.best_match is not None]
            suggestion_msg = f"\n\nDid you mean? {', '.join(set(suggestion_strs))}" if len(suggestion_strs) > 0 else ""

            status_embed.add_field(name="Could not find and remove the following (check spelling and capitalization):",
                                   value=f"{bad_roles_msg}{suggestion_msg}\n\N{ZERO WIDTH SPACE}", inline=False)

        await self.ctx.send(embed=status_embed)
        return


class AddRemoveRolesToUser:
    navigation_buttons = [
        ("\N{Leftwards Black Arrow}", "left_button"),
        ("\N{Black Rightwards Arrow}", "right_button"),
        ("\N{Bar Chart}", "category_list")
    ]

    max_per_page = 9  # TODO: Make this configurable per guild.

    def __init__(self, cats: pDB.RoleCategories):
        self.role_cats = cats.cats

        # Page/subpage indexes
        self.page_index: int = 0
        self.max_page_index: int = len(self.role_cats) - 1

        self.sub_page_index: int = 0
        self.showing_categories = False

        # Buttons
        self.buttons = self.navigation_buttons[:]
        num_of_buttons = self.max_per_page if self.max_per_page <= len(number_emotes) else len(number_emotes)
        self.buttons.extend([(number_emotes[i+1], i) for i in range(num_of_buttons)])

        # Vars that get dealt with later
        self.embed = pn_embed()  # discord.Embed()
        self.ui: Optional[StringReactPage] = None
        self.ctx: Optional[commands.Context] = None

        self.conf_msg: Optional[discord.Message] = None
        self.current_roles_len = 0

        self.roles_added: List[int] = []
        self.roles_removed: List[int] = []


    async def run(self, ctx: commands.Context):
        """Initializes remaining variables and starts the command."""
        self.ctx = ctx

        if self.max_page_index < 0:
            await self.ctx.send(embed=pn_embed(title="No Roles Available To Add Or Remove", desc=f"There are currently no roles that have been configured as allowable to add or remove."))
            await self.ui.finish()
            return

        embed = await self.prepare_embed()
        self.ui = StringReactPage(embed=self.embed, buttons=self.buttons, remove_msgs=False, edit_in_place=True, cancel_emoji='🛑') #, cancel_btn_loc=len(self.navigation_buttons))

        await self.update_current_roles_len()  # Make sure that self.current_roles_len is initialized

        # Start the UI Loop
        await self.prompt_for_toggle_roles(embed)

        # Clean up and remove the reactions
        await self.ui.finish()


    @property
    def current_category(self) -> pDB.RoleCategory:
        """Get the current category with respect to the current page"""
        cat = self.role_cats[self.page_index]
        return cat


    async def max_sub_page_index(self) -> int:
        """Calculates and returns the maximum subpage-index based on the current page index"""
        await self.update_current_roles_len()

        value = ceil(self.current_roles_len/self.max_per_page) - 1
        if value < 0:
            value = 0
        return value


    async def update_current_roles_len(self):
        """Updates the variable reflecting the number of roles on the current page"""
        await self.all_current_roles()


    async def all_current_roles(self) -> List[pDB.AllowedRole]:
        """Get all the current roles with respect to only the current page. Also keeps self.current_roles_len updated"""
        roles = await self.current_category.get_roles()
        self.current_roles_len = len(roles)
        return roles


    async def current_roles(self) -> List[pDB.AllowedRole]:
        """Get the current roles *with* respect to the current page and sub-page"""
        start, end = self.get_slice_points()
        roles = await self.all_current_roles()

        if roles is not None:
            return roles[start:end]
        else:
            return []


    def get_slice_points(self):
        """Computes the start and end slice points for reducing roles down to sub-pages"""
        return self.sub_page_index * self.max_per_page, (self.sub_page_index * self.max_per_page) + self.max_per_page


    async def decrement_page(self):
        """Decrements the page count and the refreshes self.embed"""
        if not self.showing_categories:  # if we are on the cat listing, just return back to the page we are on.
            if self.page_index > 0 and self.sub_page_index == 0:
                self.page_index -= 1
                self.sub_page_index = await self.max_sub_page_index()

            elif self.sub_page_index > 0:
                self.sub_page_index -= 1

            else:
                self.page_index = self.max_page_index  # Wrap around

        await self.update_current_roles_len()

        self.showing_categories = False
        log.info(f"Dec indexes: idx: {self.page_index}, sub_idx: {self.sub_page_index} max_sub_idx: {await self.max_sub_page_index()}")
        await self.prepare_embed()


    async def increment_page(self):
        """Increments the page count and the refreshes self.embed"""
        if not self.showing_categories:  # if we are on the cat listing, just return back to the page we are on.
            if self.page_index < self.max_page_index and self.sub_page_index == await self.max_sub_page_index():
                self.page_index += 1
                self.sub_page_index = 0

            elif self.sub_page_index < await self.max_sub_page_index():
                self.sub_page_index += 1

            else:
                self.page_index = 0  # Wrap around

        await self.update_current_roles_len()

        self.showing_categories = False
        log.info(f"Inc indexes: idx: {self.page_index}, sub_idx: {self.sub_page_index} max_sub_idx: {await self.max_sub_page_index()}")
        await self.prepare_embed()


    async def jump_to_page(self, cat_idx: int):
        """Jump to the start of a specific page by idx"""
        self.sub_page_index = 0
        self.page_index = cat_idx
        self.showing_categories = False
        await self.prepare_embed()


    async def show_category_listing(self):
        """Shows a listing of categories and sets the appropriate flags to jump to a specific page by category."""
        self.showing_categories = True
        await self.prepare_category_listing_embed()

    async def prepare_category_listing_embed(self) -> discord.Embed:
        """Edits the command embed (self.embed) to show a list of the categories."""

        self.embed.clear_fields()
        self.embed.title = f"Jump to a Category"
        self.embed.description = f"*Click* on the associated react to jump to a category.\n" \
                                 f"*Click* on 🛑 to stop changing your roles.\n" \
                                 f"*Click* on \N{Bar Chart} to return to the category listing.\n" \
                                 f"*Click* on \N{Leftwards Black Arrow} / \N{Black Rightwards Arrow} to navigate through the pages.\n\n"

        cat_txt = []
        for i, cat in enumerate(self.role_cats):
            if i < self.max_per_page:  # TODO: Paginate Categories.

                cat_description = f"\n{cat.bq_description}" if cat.description is not None else ""
                cat_txt.append(f"{number_buttons[i+1][0]} __**{cat.cat_name}**__{cat_description}")

        cat_txt = "\n".join(cat_txt) if len(cat_txt) > 0 else "*No Categories*"
        cat_txt += f"\n\N{Zero Width Space}\n\N{Zero Width Space}"  # Make some extra space so tool tips don't block the roles
        self.embed.add_field(name="\N{Zero Width Space}", value=cat_txt, inline=False)

        return self.embed


    async def prepare_embed(self) -> discord.Embed:
        """Edits the command embed (self.embed) to reflect the the current page and sub-page"""
        black_circle = "\N{MEDIUM BLACK CIRCLE}"

        self.embed.clear_fields()
        self.embed.title = f"Select Roles to Add or Remove"
        max_sub_page_index = await self.max_sub_page_index()

        cat_page_num = f"*Showing Category {self.page_index+1} of {self.max_page_index+1}*"
        cat_subpage_num = f"  ({self.sub_page_index+1} / {max_sub_page_index + 1})" if max_sub_page_index > 0 else ""
        cat_desc = self.current_category.bq_description if self.current_category.description is not None else ""

        self.embed.description = f"*Click* on the associated react to add/remove roles.\n\n" \
                                 f"{cat_page_num}\n"\
                                 f"__**{self.current_category.cat_name}{cat_subpage_num}**__\n"\
                                 f"{cat_desc}\n"

        roles = await self.current_roles()  # self.role_cats[self.page_index].get_roles()

        role_txt = []
        for i, role in enumerate(roles):
            has_role = discord.utils.get(self.ctx.author.roles, id=role.role_id)
            has_role_indicator = " ✅ " if has_role is not None else f" {black_circle} "  # "❌"
            role_txt.append(f"{number_buttons[i+1][0]}{has_role_indicator}<@&{role.role_id}>")

        # role_txt = [f"{number_buttons[i][0]} <@&{role.role_id}>" for i, role in enumerate(roles)]
        role_txt = "\n".join(role_txt) if len(role_txt) > 0 else "*No Roles*"
        role_txt += f"\n\N{Zero Width Space}\n\N{Zero Width Space}"  # Make some extra space so tool tips don't block the roles
        self.embed.add_field(name="\N{Zero Width Space}", value=role_txt, inline=False)

        return self.embed


    async def prompt_for_toggle_roles(self, refreshed_embed=None):
        """The main command handler for the Toggle User Roles UI"""

        # discord.utils.find(lambda x: x.cat_name.lower().strip() == self.selected_cat.lower().strip(), self.role_cats)

        # self.embed = refreshed_embed or pn_embed(title=f"Select Roles to Add",
        #                                          desc="Click on the associated react to add roles.")

        await self.show_category_listing()
        while True:
            response = await self.ui.run(self.ctx, new_embed=self.embed)

            # Send out the conf embed right after the first time we send out the UI embed.
            if self.conf_msg is None:
                self.conf_msg = await self.ctx.send(embed=pn_embed(title="Changing Roles"))

            if response is None:
                if self.conf_msg is not None and len(self.conf_msg.embeds) > 0:
                    self.conf_msg.embeds[0].title = "Finished Changing Roles"
                await self.conf_msg.edit(embed=self.conf_msg.embeds[0])
                return

            roles = await self.current_roles()

            if response.content() == 'left_button':
                await self.decrement_page()

            elif response.content() == 'right_button':
                await self.increment_page()

            elif response.content() == "category_list":
                await self.show_category_listing()

            else:
                if self.showing_categories:
                    if response.content() in list(range(len(self.role_cats))):
                        await self.jump_to_page(response.content())
                else:
                    if response.content() in list(range(len(roles))):
                        await self.toggle_role(roles[response.content()].role_id)
                        await self.prepare_embed()

    async def add_role(self, member: discord.Member, role_id: int):
        await member.add_roles(discord.Object(id=role_id),
                               reason=f"Role added via PNBot at the command of {member.name}#{member.discriminator}.")

        self.roles_added.append(role_id)
        try:
            self.roles_removed.remove(role_id)
        except ValueError:
            pass

    async def remove_role(self, member: discord.Member, role_id: int):
        await member.remove_roles(discord.Object(id=role_id),
                                  reason=f"Role removed via PNBot at the command of {member.name}#{member.discriminator}.")
        self.roles_removed.append(role_id)
        try:
            self.roles_added.remove(role_id)
        except ValueError:
            pass

    async def toggle_role(self, role_id: int):
        """Adds a role tto the user and then sends/edits the confirmation message"""
        member: Union[discord.Member, discord.User] = self.ctx.author

        has_role = (discord.utils.get(member.roles, id=role_id) is not None)
        conf_key = "remove" if has_role else "adding"
        conf_txt = f"<@&{role_id}>"  # f"\nRemoving role: <@&{role_id}>" if has_role else f"\nAdding role: <@&{role_id}>"
        try:
            if has_role:
                await self.remove_role(member, role_id)
            else:
                await self.add_role(member, role_id)

        except discord.Forbidden:
            conf_txt = f"\nPermissions Error! Failed to remove role: <@&{role_id}>" if has_role else f"\nPermissions Error! Failed to add role: <@&{role_id}>"
            conf_key = "error"
        except discord.HTTPException:
            conf_txt = f"\nUnknown Discord Error! Failed to remove role: <@&{role_id}>" if has_role else f"\nUnknown Discord Error! Failed to add role: <@&{role_id}>"
            conf_key = "error"

        await self.update_conf_msg_fields(field_type=conf_key, field_value=conf_txt)

    async def update_conf_msg_fields(self, field_type: str, field_value: Optional[str] = None):  #, remove: Optional[str] = None, error: Optional[str] = None):
        """
        Adds/Updates the fields of the conf_msg embed.
        Valid arguments for `field_type`: adding, remove, error
        """
        field_names = {'adding': "Roles Added:", 'remove': "Roles Removed:", 'error': "Errors:"}
        if field_type not in field_names:
            raise ValueError("invalid field type")

        # Just in case the embed gets removed, abort trying to edit it.
        if len(self.conf_msg.embeds) == 0:
            return

        conf_embed = self.conf_msg.embeds[0]

        error_field_and_idx = discord.utils.find(lambda f: f[1].name == "Errors:", enumerate(conf_embed.fields))

        if field_type != 'error':
            conf_embed.clear_fields()
            if len(self.roles_added) > 0:
                add_value = ", ".join([f"<@&{role_id}>" for role_id in self.roles_added])
                conf_embed.add_field(name=field_names['adding'], value=add_value, inline=False)

            if len(self.roles_removed) > 0:
                del_value = ", ".join([f"<@&{role_id}>" for role_id in self.roles_removed])
                conf_embed.add_field(name=field_names['remove'], value=del_value, inline=False)

            if error_field_and_idx is not None:
                idx, error_field = error_field_and_idx
                conf_embed.add_field(name=error_field.name, value=error_field.value, inline=False)
        else:
            if error_field_and_idx is not None:
                idx, error_field = error_field_and_idx
                conf_embed.set_field_at(idx, name=error_field.name, value=f"{error_field.value}{field_value}", inline=False)
            else:
                conf_embed.insert_field_at(3, name=field_names['error'], value=field_value, inline=False)

        await self.conf_msg.edit(embed=conf_embed)


class AdminChangeCatDescription:
    navigation_buttons = [
        ("\N{Leftwards Black Arrow}", "left_button"),
        ("\N{Black Rightwards Arrow}", "right_button"),
    ]

    def __init__(self, cats: pDB.RoleCategories):

        self.role_cats = cats.cats
        self.ctx: Optional[commands.Context] = None
        # self.cat_names = [cat.cat_name for cat in role_cats]
        num_of_buttons = len(self.role_cats) if len(self.role_cats) <= len(number_emotes) else len(number_emotes)

        buttons = [(number_emotes[i], self.role_cats[i].cat_name) for i in range(num_of_buttons)]
        self.cat_names_w_buttons = []

        for i, cat in enumerate(self.role_cats):
            if i < len(number_emotes):
                self.cat_names_w_buttons.append(f"{number_emotes[i]}  **{cat.cat_name}**\n*Description:*\n{cat.description}")
            else:
                self.cat_names_w_buttons.append(f"    **{cat.cat_name}**\n*Description:*\n{cat.description}")

        cat_desc = "\n".join(self.cat_names_w_buttons)
        self.embed = pn_embed(title="Select A Role Category",
                              desc=f"Click a react or send the name to select\n\n{cat_desc}")

        self.ui = StringReactPage(embed=self.embed, buttons=buttons, allowable_responses=[cat.cat_name for cat in self.role_cats],
                                  remove_msgs=False)

        self.selected_cat = ""

    async def run(self, ctx: commands.Context):
        self.ctx = ctx
        await self.prompt_for_category()
        await self.ui.finish()  # Clean up and remove reactions

    async def prompt_for_category(self):
        response = await self.ui.run(self.ctx)

        if response is None:
            await self.ctx.send(embed=pn_embed(title="Change Category Description Canceled"))
            return

        self.selected_cat = response.content()

        log.info(f"Selected: {self.selected_cat}")

        # Clean up and remove the reactions from the `Category Prompt` before self.prompt_for_new_description() creates a new UI
        await self.ui.finish()
        await self.prompt_for_new_description()


    async def prompt_for_new_description(self):
        cat: pDB.RoleCategory = discord.utils.find(lambda x: x.cat_name.lower().strip() == self.selected_cat.lower().strip(), self.role_cats)

        self.embed = pn_embed(title=f"Change description of *{cat.cat_name}*",
                              desc="Please send the new description now.")

        self.ui = StringReactPage(embed=self.embed, remove_msgs=False)

        response = await self.ui.run(self.ctx)
        if response is None:
            await self.ctx.send(embed=pn_embed(title="Change Category Description Canceled"))
            return

        new_description = response.content()

        status_embed = pn_embed(title=f"Description Changed:", desc=new_description)

        # Commit changes to the DB.
        await cat.redescribe(new_description)

        await self.ctx.send(embed=status_embed)
        return


# class AdminMoveCat:
#     navigation_buttons = [
#         ("\N{Leftwards Black Arrow}", "left_button"),
#         ("\N{Black Rightwards Arrow}", "right_button"),
#     ]
#
#     def __init__(self, cats: pDB.RoleCategories):
#
#         self.role_cats = cats.cats
#         self.categories = cats
#
#         self.ctx: Optional[commands.Context] = None
#
#         self.cat_names = []
#         for i, cat in enumerate(self.role_cats):
#             self.cat_names.append(f"**{cat.cat_name}**")
#
#         cat_desc = "\n".join(self.cat_names)
#         self.embed = pn_embed(title="Select Categories To Swap Positions",
#                               desc=f"send the name to select\n\n{cat_desc}")
#
#         self.ui = StringReactPage(embed=self.embed, buttons=buttons, allowable_responses=self.cat_names_w_buttons,
#                                   remove_msgs=False)
#
#         self.selected_cat = ""
#
#     async def run(self, ctx: commands.Context):
#         self.ctx = ctx
#         await self.prompt_for_category()
#
#     async def prompt_for_category(self):
#         response = await self.ui.run(self.ctx)
#
#         if response is None:
#             await self.ctx.send(embed=pn_embed(title="Change Category Description Canceled"))
#             return
#
#         self.selected_cat = response.content()
#
#         log.info(f"Selected: {self.selected_cat}")
#         await self.prompt_for_new_description()
#
#
#     async def prompt_for_new_description(self):
#         cat: pDB.RoleCategory = discord.utils.find(lambda x: x.cat_name.lower().strip() == self.selected_cat.lower().strip(), self.role_cats)
#
#         self.embed = pn_embed(title=f"Change description of *{cat.cat_name}*",
#                               desc="Please send the new description now.")
#
#         self.ui = StringReactPage(embed=self.embed, remove_msgs=False)
#
#         response = await self.ui.run(self.ctx)
#         if response is None:
#             await self.ctx.send(embed=pn_embed(title="Change Category Description Canceled"))
#             return
#
#         new_description = response.content()
#
#         status_embed = pn_embed(title=f"Description Changed:", desc=new_description)
#
#         # Commit changes to the DB.
#         await cat.redescribe(new_description)
#
#         await self.ctx.send(embed=status_embed)
#         return


class Roles(commands.Cog):

    def __init__(self, bot: 'PNBot'):
        self.bot = bot
        self.pool: asyncpg.pool.Pool = bot.db



# region Admin and Team Level Commands
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    @eCommands.command(name="add_cat", brief="Add a new role category",
                       description="Lets you add a new category for holding roles. "
                                   "Quotes are not needed for this command.",
                       examples=["Awesome Colors!"],
                       category="Role Management")
    async def add_category(self, ctx: commands.Context, *, cat_name: Optional[str] = None):
        if cat_name is None:
            await ctx.send_help(self.add_category)
            return

        existing_cats = await pDB.get_role_cats(self.pool, ctx.guild.id)

        if len(existing_cats.cats) >= MAX_NUMBER_OF_CATS:
            await send_embed(ctx, title="Can not add new category.",
                             desc="You have reached already the maximum number of categories and con not add another.\n"
                                  "Consider renaming or deleting an existing category")
            return

        embed = pn_embed(desc=f"Please enter a description for the new category {cat_name}\n"
                              f"Enter `none` for no description.")

        ui = StringReactPage(embed=embed, allow_any_response=True, remove_msgs=False)
        response = await ui.run(ctx)

        if response is None:
            embed = pn_embed(desc=f"Canceled adding {cat_name}")
            await ctx.send(embed=embed)
            await ui.finish()
            return

        if response.content().lower().strip() == 'none':
            cat_desc = None
            cat_desc_msg = "no description."
        else:
            cat_desc = response.content()
            cat_desc_msg = f"the description:\n\n{cat_desc}"

        await existing_cats.add_new_cat(cat_name, cat_desc)
        await send_embed(ctx, desc=f"**{cat_name}** has been added with {cat_desc_msg}")
        await ui.finish()


    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    @eCommands.command(name="delete_cat", brief="Deletes a role category",
                       description="Lets you delete an existing category for holding roles. "
                                   "Quotes are not needed for this command.",
                       examples=["Awesome Colors!"],
                       category="Role Management")
    async def delete_category(self, ctx: commands.Context, *, category_name: Optional[str] = None):
        if category_name is None:
            await ctx.send_help(self.delete_category)
            return

        existing_cats = await pDB.get_role_cats(self.pool, ctx.guild.id)

        category = existing_cats.get_cat_by_name(category_name)
        if category is None:
            raise ValueError(f"Could not find a category named {category_name}")
        roles = await category.get_roles()
        embed = pn_embed(title="Are You Sure?",
                         desc=f"**{category.cat_name}** contains **{len(roles)}** roles that will have to be readded to PNBot to be user settable if this category is deleted!\n"
                              f"Are you sure you want to delete the category **{category.cat_name}**?")

        ui = BoolPage(embed=embed)
        response = await ui.run(ctx)

        if response is not True:
            embed = pn_embed(desc=f"Canceled deletion of {category.cat_name}")
            await ctx.send(embed=embed)
            return

        category_name = category.cat_name
        await category.delete()
        await send_embed(ctx, desc=f"**{category_name}** has been deleted!")


    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    @eCommands.command(name="swap_cats", brief="Swaps the position of two categories (Use quotes).",
                       description="Lets you reorder the categories by swapping the position of any two categories. "
                                   "Quotes are required for any category who's name has spaces in it.",
                       examples=['Pronouns "Awesome Colors!"'],
                       category="Role Management")
    async def swap_category(self, ctx: commands.Context, first_category: Optional[str] = None, second_category: Optional[str] = None):
        if first_category is None or second_category is None:
            await ctx.send_help(self.swap_category)
            return

        existing_cats = await pDB.get_role_cats(self.pool, ctx.guild.id)

        cat_one = existing_cats.get_cat_by_name(first_category)
        if cat_one is None:
            raise ValueError(f"Could not find a category named {first_category}")

        cat_two = existing_cats.get_cat_by_name(second_category)
        if cat_two is None:
            raise ValueError(f"Could not find a category named {second_category}")

        await existing_cats.swap_position(cat_one.cat_id, cat_two.cat_id)

        msg = "" #f"The categories are now positioned in the following order:\n\n"
        for cat in existing_cats.cats:
            msg += f"{cat.cat_name}\n"

        await send_embed(ctx, title="New Category Positions", desc=msg)


    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    @eCommands.command(name="set_cat_desc", brief="Change the description of a role category",
                       description="This command allows you to add/change/remove the description of a role category.\n"
                                   "This command is interactive and no arguments are required",
                       examples=[""],
                       category="Role Management")
    async def redescribe_category(self, ctx: commands.Context):

        cats = await pDB.get_role_cats(self.pool, ctx.guild.id)
        ui = AdminChangeCatDescription(cats)
        await ui.run(ctx)


    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    @eCommands.command(name="allow_role_manual", aliases=["allow_role_m", "allow_roles_m"],
                       brief="Non-interactive command for allowing new user settable roles.",
                       description="A non-interactive version of the `allow_role` command.\n"
                                   "Allows you to add a new role for users to set.\n"
                                   "Quotes are required for the role if it has spaces in it. Quotes are not required for the category name.",
                       examples=['"Radical Red" Awesome Colors!', 'Pink Awesome Colors!'],
                       category="Role Management")
    async def allow_role_man(self, ctx: commands.Context, role: Optional[str] = None, *, cat_name: Optional[str] = None):
        if role is None or cat_name is None:
            await ctx.send_help(self.allow_role_man)
            return

        role: discord.Role = await BetterRoleConverter().convert(ctx, role)

        categories = await pDB.get_role_cats(self.pool, ctx.guild.id)

        cat = categories.get_cat_by_name(cat_name)  # discord.utils.find(lambda x: x.lower() == cat_name.lower(), cats.cats)
        if cat is None:
            await send_embed(ctx, desc=f"Could not find category: {cat_name}")
            return

        await cat.add_new_role(role.id, "")
        await send_embed(ctx, desc=f"Added <@&{role.id}> to {cat_name}")


    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    @eCommands.command(name="allow_role", aliases=["allow_roles"], brief="Adds a new user settable role.",
                       description="Allows you to add a new role for users to set.\n"
                                   "This command is interactive and no arguments are required",
                       examples=[""],
                       category="Role Management")
    async def allow_role(self, ctx: commands.Context):

        cats = await pDB.get_role_cats(self.pool, ctx.guild.id)
        ui = AdminAddAllowedRoles(cats)
        await ui.run(ctx)


    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    @eCommands.command(name="disallow_role", aliases=["disallow_roles"], brief="Disallows a role from being user settable.",
                       description="Allows you to disallow a role for users to set.\n"
                                   "This command is interactive and no arguments are required",
                       examples=[""],
                       category="Role Management")
    async def disallow_role(self, ctx: commands.Context):

        # cats = await pDB.get_role_cats(self.pool, ctx.guild.id)
        ui = AdminRemoveAllowedRoles()
        await ui.run(ctx)


    @is_team_member()
    @commands.guild_only()
    @eCommands.command(name="list_cats", brief="Lists all the defined categories.",
                       description="Shows all the categories setup on this server.",
                       examples=[""],
                       category="Role Management")
    async def show_cats(self, ctx: commands.Context):
        cats = await pDB.get_role_cats(self.pool, ctx.guild.id)
        cats = cats.cats
        if len(cats) == 0:
            msg = f"{ctx.guild.name} has no categories yet!"
        else:
            msg = f"{ctx.guild.name} has the following categories:\n\n"

            for cat in cats:
                cat_roles = await cat.get_roles()
                # split_cat_desc = cat.description.splitlines() if cat.description is not None else []

                # cat_desc = ""
                # for line in split_cat_desc:
                #     cat_desc += f"> {line}\n"
                # cat_desc += "\n"
                cat_desc = cat.bq_description if cat.description is not None else "\n"

                # cat_desc = f"> {cat.description}\n\n" if cat.description is not None else "\n"
                role_number = f"({len(cat_roles)} Roles)" if len(cat_roles) != 1 else f"({len(cat_roles)} Role)"
                msg += f"**{cat.cat_name}** `{role_number}`\n{cat_desc}"

        await send_embed(ctx, desc=msg)
# endregion


# region Member Level Commands
    @staticmethod
    async def full_role_list_embed(ctx: commands.Context, categories: pDB.RoleCategories) -> discord.Embed:
        """
        Constructs and returns an embed containing the full listing of (filled) categories and roles for a guild,
         marked with the roles the user who requested the embed has.
        """
        member: discord.Member = ctx.author

        if len(categories.cats) == 0:
            embed = pn_embed(desc=f"{ctx.guild.name} has no user settable roles!")
        else:

            embed = pn_embed(desc=f"{ctx.guild.name} has the following roles:\n")
            for cat in categories.cats:

                roles = await cat.get_roles()

                if len(roles) == 0:
                    continue  # Skip Categories that have not yet been set up.

                field_msg = ""  # if len(roles) > 0 else "*No Roles Have Been Added To This Category Yet*\n"
                for role in roles:
                    has_role = discord.utils.get(member.roles, id=role.role_id)
                    # has_role_indicator = " ✅" if has_role is not None else ""  # "❌"
                    # field_msg += f"> <@&{role.role_id}>{has_role_indicator}\n"
                    has_role_indicator = "✅" if has_role is not None else "\N{MEDIUM BLACK CIRCLE}"  # "❌"
                    field_msg += f"{has_role_indicator} <@&{role.role_id}>\n"

                embed.add_field(name=f"__{cat.cat_name}__", value=field_msg, inline=True)

        return embed


    @is_server_member()
    @commands.guild_only()
    @eCommands.command(name="list", aliases=["selfrole"], brief="Show all user settable roles",
                       description="Shows a list of every role that is available to you in this server.",
                       examples=[""])
    async def show_roles(self, ctx: commands.Context):

        cats = await pDB.get_role_cats(self.pool, ctx.guild.id)
        role_list_embed = await self.full_role_list_embed(ctx, cats)
        await ctx.send(embed=role_list_embed)


    @is_server_member()
    @commands.guild_only()
    @eCommands.command(name="role", aliases=["roles", "set_role", "set_roles"],
                       brief="The primary command for adding/removing roles.",
                       description="An interactive command that lets you add and remove roles from your account.",
                       examples=[""]
                      )
    async def add_roles_to_users(self, ctx: commands.Context):
        """
        __**How To Use**__

        **General Info**
        There is no need to wait for all the reactions to be added before making your selections.

        You may stop the command at any time by clicking on the 🛑 reaction or by simply letting the command timeout after 2 minutes of inactivity.
        This will end the command and save your settings.

        **Category Selection**
        When first run, you will be shown a list of categories. Select a category by *clicking* on the associated number reaction. This will take you to that categories `Select Roles` page.
        You may return to the category list at any time by *clicking* on \N{Bar Chart}.
        
        **Adding and Removing Roles**
        When on a `Select Roles` page, you may move through the pages with the \N{Leftwards Black Arrow} and \N{Black Rightwards Arrow} reactions.
        Roles may be added or removed by *clicking* on the associated number reaction.
        Roles that you currently have will have a ✅ next to them. 
        """

        cats = await pDB.get_role_cats(self.pool, ctx.guild.id)
        ui = AddRemoveRolesToUser(cats)
        await ui.run(ctx)


    @is_server_member()
    @commands.guild_only()
    @eCommands.command(name="add_roles", aliases=["add_role", "iam"],
                       brief="Text based command for adding roles.",
                       description="A text based command that lets you add one or many roles from your account with a single command.",
                       examples=["Light Blue", "She/Her, Pink, Voice, Pats Welcome"]
                       )
    async def add_role_via_text(self, ctx: commands.Context, *, roles: Optional[str] = None):
        """
        This command can accept either a single role, or many roles at once.
        When adding multiple roles at the same time, each role must be separated by a comma like this:
            `pb;add_roles She/Her, Pink, Voice, Pats Welcome`

        Quotation marks are not needed for this command.
        """

        if roles is None:
            await ctx.send_help(self.add_role_via_text)
            return

        member: discord.Member = ctx.author
        cats = await pDB.get_role_cats(self.pool, ctx.guild.id)

        parsed_roles = await parse_csv_roles(ctx, roles, cats.cats)

        if parsed_roles is None:
            await ctx.send(embed=pn_embed(title="ERROR!!! Could not parse roles!"))
            return

        if len(parsed_roles.good_roles) > 0:
            # Add the roles to the User.
            await member.add_roles(*parsed_roles.good_roles, reason=f"Role added via PNBot at the command of {member.name}#{member.discriminator}.")

        status_embed = add_and_removed_roles_embed(parsed_roles)
        await ctx.send(embed=status_embed)
        return


    @is_server_member()
    @commands.guild_only()
    @eCommands.command(name='remove_roles', aliases=['remove_role', "iamn", "iamnot"],
                       brief="Text based command for removing roles.",
                       description="A text based command that lets you remove one or many roles from your account with a single command.",
                       examples=["Light Blue", "She/Her, Pink, Voice, Pats Welcome"]
                       )
    async def remove_role_via_text(self, ctx: commands.Context, *, roles: Optional[str] = None):
        """
        This command can accept either a single role, or many roles at once.
        When removing multiple roles at the same time, each role must be separated by a comma like this:
            `pb;remove_roles She/Her, Pink, Voice, Pats Welcome`

        Quotation marks are not needed for this command.
        """

        if roles is None:
            await ctx.send_help(self.remove_role_via_text)
            return

        member: discord.Member = ctx.author
        cats = await pDB.get_role_cats(self.pool, ctx.guild.id)

        parsed_roles = await parse_csv_roles(ctx, roles, cats.cats)

        if parsed_roles is None:
            await ctx.send(embed=pn_embed(title="ERROR!!! Could not parse roles!"))
            return

        if len(parsed_roles.good_roles) > 0:
            # Remove the roles from the User.
            await member.remove_roles(*parsed_roles.good_roles, reason=f"Role removed via PNBot at the command of {member.name}#{member.discriminator}.")

        status_embed = add_and_removed_roles_embed(parsed_roles, remove_roles_msg=True)
        await ctx.send(embed=status_embed)
        return
# endregion


def setup(bot):
    bot.add_cog(Roles(bot))
