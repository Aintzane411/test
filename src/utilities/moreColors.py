"""
Provides convenience functions for the various custom colors used by PNBot.
Colors include:
    PN Orange
    GG Purple

Part of PNBot.
"""

from discord.colour import Colour


def pn_orange() -> Colour:
    """A convenience function that returns a :class:`Colour` with a value of 0xF6C57F."""
    # discord.Color.from_rgb(80, 135, 135))
    return Colour(0xF6C57F)


def pn_purple() -> Colour:
    """A convenience function that returns a :class:`Colour` with a value of 0x9932CC."""
    return Colour(0x9932CC)




