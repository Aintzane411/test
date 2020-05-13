"""

"""

import re
import logging

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional, Dict, List, Union, Tuple

import discord
from discord.ext import tasks, commands
from discord import utils

from fuzzywuzzy import fuzz
from fuzzywuzzy import process

if TYPE_CHECKING:
    from pDB import RoleCategory, AllowedRole

log = logging.getLogger(__name__)


class BetterRoleConverter(commands.IDConverter):
    """Converts to a :class:`~discord.Role`.

    All lookups are via the local guild. If in a DM context, then the lookup
    is done by the global cache.

    The lookup strategy is as follows (in order):

    1. Lookup by ID.
    2. Lookup by mention or escaped mention.
    3. Lookup by name (Including with an @ in front of it)
    """
    # mention_pattern = re.compile()
    async def convert(self, ctx, argument):
        guild = ctx.guild
        if not guild:
            raise commands.errors.NoPrivateMessage()

        match = self._get_id_match(argument) or re.match(r'\\{0,2}<@&([0-9]+)>$', argument)
        if match:
            result = guild.get_role(int(match.group(1)))
        else:
            result = discord.utils.get(guild._roles.values(), name=argument.replace("@", ""))

        if result is None:
            raise commands.errors.BadArgument('Role "{}" not found.'.format(argument))
        return result


@dataclass()
class BadRole:
    role: str
    best_match: Optional[discord.Role]
    score: Optional[int]

    def __str__(self):
        # if self.best_match is not None:
        #     string = f"{self.role} [Maybe {self.best_match[0]} ({self.best_match[1]})]"
        # else:
        string = f"{self.role}"
        return string


@dataclass()
class ParsedRoles:
    good_roles: List[discord.Role]
    disallowed_roles: List[discord.Role]
    bad_roles: List[BadRole]


# class AllowableRoles:
#     categories: List[RoleCategory]
#     # guild_id: int
#     # roles: Optional[List['discord.Role']]
#     # row_map = ['role_id', 'guild_id']
#
#     def __init__(self, categories: List[RoleCategory]):
#         self.categories = categories
#
#     async def is_allowed(self, other_role: discord.Role):
#         for cat in self.categories:
#             if await cat.role_in(other_role):
#                 return True
#         return False


    # def allowed_intersection(self, other_roles: List['discord.Role']):
    #     """ returns list of allowed discord role objects """
    #     good_roles = []
    #     for other_role in other_roles:  # Loop through all the other roles.
    #         for allowed_role_id in self.role_ids:
    #             if allowed_role_id == other_role.id:
    #                 good_roles.append(other_role)
    #                 break
    #
    #     return good_roles
    #
    # def disallowed_intersection(self, other_roles: List['discord.Role']):
    #     """ returns list of disallowed discord role objects """
    #     bad_roles = []
    #     for other_role in other_roles:  # Loop through all the other roles.
    #         allowed = False
    #         for allowed_role_id in self.role_ids:
    #             if allowed_role_id == other_role.id:
    #                 allowed = True
    #                 break
    #
    #         if not allowed:
    #             bad_roles.append(other_role)
    #
    #     return bad_roles


async def is_allowed(categories: List['RoleCategory'], other_role: discord.Role):
    for cat in categories:
        if await cat.role_in(other_role):
            return True
    return False


csv_regex_pattern = re.compile("(.+?)(?:,|$)")


async def parse_csv_roles(ctx: commands.Context, role_text: str, allowed_roles: Optional[List['RoleCategory']] = None, allow_all: bool = False) -> Optional[ParsedRoles]:
    """ Parse a message containing CSV Roles.

        If allowed_roles is passed, we will attempt to FuzzyMatch any non-matched results with a role on the allowed roles list
        If allow_all is True, we will attempt to FuzzyMatch any non-matched results against every role in the guild (Good for Admin purposes.)
        Returns Named Tuple with Good roles and bad roles.
        Returns None if it can't parse.

    """

    if len(role_text) == 0:
        return None

    # Make sure that the string ends in a comma for proper regex detection
    if role_text[-1] != ",":
        role_text += ","

    # Pull out the roles from the CSV
    raw_roles = csv_regex_pattern.findall(role_text)

    # If we couldn't pull anything, return None.
    if len(raw_roles) == 0:
        return None

    log.info(raw_roles)

    # Loop through all the role strings trying to get discord.Role objects.
    # If we are able to get a discord.Role object, we can assume it's a valid role. and if we can't, it probably isn't
    good_roles = []
    bad_roles = []
    disallowed_roles = []

    guild_roles: List[discord.Role] = ctx.guild.roles[1:]  # Get all the roles from the guild EXCEPT @everyone.
    for raw_role in raw_roles:
        raw_role = raw_role.strip()  # Remove any leading/trailing whitespace
        try:
            # add identifiable roles to the good list
            # Todo: Try to match up Snowflake like raw roles to the roles in self.allowable_roles and bypass the RoleConverter on success.
            potential_role: discord.Role = await BetterRoleConverter().convert(ctx, raw_role)  # Try to match the text to an actual role.
            if allowed_roles is None or await is_allowed(allowed_roles, potential_role):
                # Add the role to the good list IF it's on the allowed list, or if there is no allowed list.

                is_mod_role = (potential_role.permissions.manage_messages or potential_role.permissions.administrator)
                if not is_mod_role:
                    good_roles.append(potential_role)
                else:
                    disallowed_roles.append(potential_role)  # Don't allow the bot to add roles with mod permissions!

            else:
                # If we get here, it's because the role exists but is not allowed to be used by users.
                disallowed_roles.append(potential_role)

        except commands.errors.BadArgument:  # This error indicates that the RoleConverter() failed to identify the role.
            # Role could not be found. Try to use fuzzyWuzzy string matching to try to identify the role despite typos.
            match = process.extractOne(raw_role, guild_roles, score_cutoff=0)

            # If we can't match, match will be None. Assign accordingly.
            best_match = match[0] if match else None
            score = match[1] if match else None

            # Check to see if the type is role and if we will allow all roles / the role is on the allowed list.
            if isinstance(best_match, discord.Role) and (allow_all or (allowed_roles is not None and await is_allowed(allowed_roles, best_match))):
                bad_role = BadRole(role=raw_role, best_match=best_match, score=score)  # Add the suggestion since it IS an allowed role.
            else:
                bad_role = BadRole(role=raw_role, best_match=None, score=None)  # Don't recommend roles that Users can't set.

            bad_roles.append(bad_role)

    parsed_roles = ParsedRoles(good_roles=good_roles, bad_roles=bad_roles, disallowed_roles=disallowed_roles)
    return parsed_roles
