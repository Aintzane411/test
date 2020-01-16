"""
"""

from typing import Optional, Dict

import discord
from discord.ext import commands

from Interviews import Interviews


class PNBot(commands.Bot):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db: Optional[str] = None
        self.open_interviews: Optional[Interviews] = None
