'''

'''

from discord.ext import commands


class NotTeamMember(commands.CheckFailure):
    pass


class NotStaff(commands.CheckFailure):
    pass
