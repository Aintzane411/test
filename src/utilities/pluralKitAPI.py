"""
Functions for interfacing with the Plural Kit API.
API Endpoint functions include:
    get_pk_system_from_userid -> /a/
    get_pk_message -> /msg/

Part of the Gabby Gums Discord Logger.
"""

import logging
from typing import TYPE_CHECKING, Optional, Dict, List, Union, Tuple, NamedTuple

import aiohttp

log = logging.getLogger(__name__)


class PKAPIUnavailable(Exception):
    pass


class CouldNotConnectToPKAPI(PKAPIUnavailable):
    pass


class PkApi503Error(PKAPIUnavailable):
    """PK API Temporarily Unavailable."""
    pass


class PK502BadGatewayError(PKAPIUnavailable):
    """502 (Bad Gateway)"""
    pass


class PK500PKServerError(PKAPIUnavailable):
    """500 (Internal Server Error)"""
    pass


class UnknownPKError(Exception):
    pass


async def get_pk_system_from_userid(user_id: int) -> Optional[Dict]:
    """Gets a PK system from the PluralKit API using a Discord UserID"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f'https://api.pluralkit.me/v1/a/{user_id}') as r:
                if r.status == 200:  # We received a valid response from the PK API.
                    logging.debug(f"User has an associated PK Account linked to their Discord Account.")

                    # Convert the JSON response to a dict
                    pk_response = await r.json()
                    logging.debug(f"Got system: {pk_response}")

                    return pk_response
                elif r.status == 404:
                    # No PK Account found.
                    log.debug("No PK Account found.")
                    return None

                elif r.status == 500:
                    raise PK500PKServerError("Could not reach the Plural Kit API due to a Plural Kit Server Error.")

                elif r.status == 502:
                    raise PK502BadGatewayError("Could not reach the Plural Kit API due to a Gateway Error.")

                elif r.status == 503:
                    raise PkApi503Error("Could not reach the Plural Kit API as it is Temporarily Unavailable.")
                else:
                    raise UnknownPKError(f"Could not reach the Plural Kit API due to the following error: {r.status} ({r.reason}) for /a/")

    except aiohttp.ClientError as e:
        raise CouldNotConnectToPKAPI  # Really not strictly necessary, but it makes the code a bit nicer I think.


async def get_pk_message(message_id: int) -> Optional[Dict]:
    """Attempts to retrieve details on a proxied/pre-proxied message"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://api.pluralkit.me/v1/msg/{}'.format(message_id)) as r:
                if r.status == 200:  # We received a valid response from the PK API. The message is probably a pre-proxied message.
                    logging.debug(f"Message {message_id} is still on the PK api.")
                    # Convert the JSON response to a dict, Cache the details of the proxied message, and then bail.
                    pk_response = await r.json()
                    return pk_response
                elif r.status == 404:
                    # msg was not a proxied message
                    return None

                elif r.status == 500:
                    raise PK500PKServerError("Could not reach the Plural Kit API due to a Plural Kit Server Error.")

                elif r.status == 502:
                    raise PK502BadGatewayError("Could not reach the Plural Kit API due to a Gateway Error.")

                elif r.status == 503:
                    raise PkApi503Error("Could not reach the Plural Kit API as it is Temporarily Unavailable.")
                else:
                    raise UnknownPKError(f"Could not reach the Plural Kit API due to the following error: {r.status} ({r.reason}) for /msg/")

    except aiohttp.ClientError as e:
        raise CouldNotConnectToPKAPI



