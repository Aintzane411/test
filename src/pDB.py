import aiosqlite
import logging
import time
import functools

import asyncpg

from datetime import datetime
from typing import TYPE_CHECKING, Optional, List, Dict
from dataclasses import dataclass, field

import discord


log = logging.getLogger("PNBot.pDB")


def db_deco(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        try:
            response = await func(*args, **kwargs)
            end_time = time.perf_counter()
            if len(args) > 1:
                log.info("DB Query {} from {} in {:.3f} ms.".format(func.__name__, args[1], (end_time - start_time) * 1000))
            else:
                log.info("DB Query {} in {:.3f} ms.".format(func.__name__, (end_time - start_time) * 1000))
            return response
        # except Exception:
        except asyncpg.exceptions.PostgresError:
            log.exception("Error attempting database query: {} for server: {}".format(func.__name__, args[1]))
    return wrapper


async def create_db_pool(uri: str) -> asyncpg.pool.Pool:

    # FIXME: Error Handling

    pool: asyncpg.pool.Pool = await asyncpg.create_pool(uri)

    return pool

# ---------- Interview Methods ---------- #

# --- Inserts --- #

# region Join Interview DB Functions

@db_deco
async def add_new_interview(pool: asyncpg.pool.Pool, sid: int, member_id: int, username: str, channel_id: int,
                                  question_number: int = 0, interview_finished: bool = False, paused: bool = False,
                                  interview_type: str = 'unknown', read_rules: bool = False, join_ts: datetime = None,
                                  interview_type_msg_id = None):

    async with pool.acquire() as conn:
        conn: asyncpg.connection.Connection
        # Convert ts to str
        if join_ts is None:
            join_ts = datetime.utcnow()

        ts = join_ts.timestamp()
        await conn.execute(
            "INSERT INTO interviews(guild_id, member_id, user_name, channel_id, question_number, interview_finished, paused, interview_type, read_rules, join_ts, interview_type_msg_id) VALUES($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)",
            sid, member_id, username, channel_id, question_number, interview_finished, paused, interview_type, read_rules, ts, interview_type_msg_id)


# --- Updates --- #
@db_deco
async def update_interview_all_mutable(pool: asyncpg.pool.Pool, cid: int, mid: int, question_number: int, interview_finished: bool, paused: bool, interview_type: str, read_rules: bool, interview_type_msg_id: Optional[int]):
    async with pool.acquire() as conn:
        conn: asyncpg.connection.Connection
        await conn.execute(
            "UPDATE interviews SET question_number = $1, interview_finished = $2, paused = $3, interview_type = $4, read_rules = $5 WHERE channel_id = $6 AND member_id = $7 AND interview_type_msg_id = $8",
            question_number, interview_finished, paused, interview_type, read_rules, cid, mid, interview_type_msg_id)


@db_deco
async def update_interview_question_number(pool: asyncpg.pool.Pool, cid: int, mid: int, question_number: int):
    async with pool.acquire() as conn:
        conn: asyncpg.connection.Connection
        await conn.execute(
            "UPDATE interviews SET question_number = $1 WHERE channel_id = $2 AND member_id = $3",
             question_number, cid, mid)


@db_deco
async def update_interview_finished(pool: asyncpg.pool.Pool, cid: int, mid: int, interview_finished: bool):
    async with pool.acquire() as conn:
        conn: asyncpg.connection.Connection
        await conn.execute(
            "UPDATE interviews SET interview_finished = $1 WHERE channel_id = $2 AND member_id = $3",
            interview_finished, cid, mid)


@db_deco
async def update_interview_paused(pool: asyncpg.pool.Pool, cid: int, mid: int, paused: bool):
    async with pool.acquire() as conn:
        conn: asyncpg.connection.Connection
        await conn.execute(
            "UPDATE interviews SET paused = $1 WHERE channel_id = $2 AND member_id = $3",
            paused, cid, mid)


@db_deco
async def update_interview_type(pool: asyncpg.pool.Pool, cid: int, mid: int, interview_type: str):
    async with pool.acquire() as conn:
        conn: asyncpg.connection.Connection
        await conn.execute(
            "UPDATE interviews SET interview_type = $1 WHERE channel_id = $2 AND member_id = $3",
            interview_type, cid, mid)


@db_deco
async def update_interview_read_rules(pool: asyncpg.pool.Pool, cid: int, mid: int, read_rules: bool):
    async with pool.acquire() as conn:
        conn: asyncpg.connection.Connection
        await conn.execute(
            "UPDATE interviews SET read_rules = $1 WHERE channel_id = $2 AND member_id = $3",
            read_rules, cid, mid)


@db_deco
async def update_interview_type_msg_id(pool: asyncpg.pool.Pool, cid: int, mid: int, interview_type_msg_id: int):
    async with pool.acquire() as conn:
        conn: asyncpg.connection.Connection
        await conn.execute(
            "UPDATE interviews SET interview_type_msg_id = $1 WHERE channel_id = $2 AND member_id = $3",
            interview_type_msg_id, cid, mid)



# --- Selects --- #
interview_row_map = ('guild_id', 'member_id', 'user_name', 'channel_id', 'question_number', 'interview_finished',
                     'paused', 'interview_type', 'read_rules', 'join_ts', 'interview_type_msg_id')


def row_to_interview_dict(row: aiosqlite.Row) -> Dict:
    interview_dict = {
        interview_row_map[0]:   row[0],         # Guild ID
        interview_row_map[1]:   row[1],         # Member_id
        interview_row_map[2]:   row[2],         # user_name
        interview_row_map[3]:   row[3],         # channel_id
        interview_row_map[4]:   row[4],         # quest_num
        interview_row_map[5]:   bool(row[5]),   # int_fin
        interview_row_map[6]:   bool(row[6]),   # Paused
        interview_row_map[7]:   row[7],         # interview_type
        interview_row_map[8]:   bool(row[8]),   # read_rules
        interview_row_map[9]:   datetime.fromtimestamp(row[9]),  # join_ts
        interview_row_map[10]:  row[10]         # interview_type_msg_id
    }
    return interview_dict


@dataclass
class InterviewData:
    guild_id: int
    member_id: int
    user_name: str
    channel_id: int
    question_number: int
    interview_finished: bool
    paused: bool
    interview_type: str
    read_rules: bool
    join_ts: int
    interview_type_msg_id: Optional[int]

    def joined_at(self) -> Optional[datetime]:
        """Get the time (if any) that user joined."""
        if self.join_ts is None:
            return None
        ts = datetime.fromtimestamp(self.join_ts)
        return ts



# @db_deco
# async def get_interview_by_member(pool: asyncpg.pool.Pool, member_id: int):
#     async with pool.acquire() as conn:
#         conn: asyncpg.connection.Connection
#         cursor = await conn.execute(" SELECT * from interviews WHERE member_id = ?", (member_id,))
#         row = await cursor.fetchone()
#         # interview_dict = dict(zip(interview_row_map, row))
#
#         return row_to_interview_dict(row)
#
#
# @db_deco
# async def get_all_interview_for_guild(pool: asyncpg.pool.Pool, sid: int):
#     async with pool.acquire() as conn:
#         conn: asyncpg.connection.Connection
#         cursor = await conn.execute(" SELECT * from interviews WHERE guild_id = ?", (sid,))
#         raw_rows = await cursor.fetchall()
#         # rows = [dict(zip(interview_row_map, row)) for row in raw_rows]
#         rows = []
#         for row in raw_rows:
#             rows.append(row_to_interview_dict(row))
#         return rows


@db_deco
async def get_all_interviews(pool: asyncpg.pool.Pool) -> List[Dict]:  #  -> List[InterviewData]:
    async with pool.acquire() as conn:
        conn: asyncpg.connection.Connection
        raw_rows = await conn.fetch("SELECT * from interviews")
        # rows = [dict(zip(interview_row_map, row)) for row in raw_rows]
        rows = []
        for row in raw_rows:
            rows.append(row_to_interview_dict(row))
        return rows


# --- Deletes --- #
@db_deco
async def delete_interview(pool: asyncpg.pool.Pool, cid: int, mid: int):
    async with pool.acquire() as conn:
        conn: asyncpg.connection.Connection
        await conn.execute(
            "DELETE FROM interviews WHERE channel_id = $1 AND member_id = $2",
            cid, mid)

# endregion


# region Guild Settings DB Functions

# @db_deco
# async def do_guild_settings_exist(pool: asyncpg.pool.Pool, sid: int) -> bool:
#     async with pool.acquire() as conn:
#         conn: asyncpg.connection.Connection
#         return (await conn.fetchval("SELECT COUNT(*) FROM guild_settings WHERE guild_id = ?", sid) > 0)
#
# @dataclass
# class GuildSettings:
#     """Data Storage for Guild Settings"""
#     guild_id: int
#     raid_level: int
#     welcome_back_react_msg_id: Optional[int]


@db_deco
async def upsert_raid_level(pool: asyncpg.pool.Pool, sid: int, raid_level: int):
    async with pool.acquire() as conn:
        conn: asyncpg.connection.Connection

        await conn.execute("""
                            INSERT INTO guild_settings(guild_id, raid_level) VALUES($1, $2)
                            ON CONFLICT(guild_id)
                            DO UPDATE SET raid_level = EXCLUDED.raid_level
                            """, sid, raid_level)


@db_deco
async def get_raid_level(pool: asyncpg.pool.Pool, sid: int) -> int:
    async with pool.acquire() as conn:
        conn: asyncpg.connection.Connection
        row = await conn.fetchrow(" SELECT * from guild_settings WHERE guild_id = $1", sid)
        # interview_dict = dict(zip(interview_row_map, row))

        if row is not None:
            return row[1]
        else:
            return 0

#
#
# @db_deco
# async def upsert_welcome_back_react_msg_id(pool: asyncpg.pool.Pool, guild_id: int, message_id: Optional[int]):
#     async with pool.acquire() as conn:
#         conn: asyncpg.connection.Connection
#
#         await conn.execute("""
#                             INSERT INTO guild_settings(guild_id, welcome_back_react_msg_id) VALUES($1, $2)
#                             ON CONFLICT(guild_id)
#                             DO UPDATE SET welcome_back_react_msg_id = EXCLUDED.welcome_back_react_msg_id
#                             """, guild_id, message_id)
#
#
# @db_deco
# async def get_guild_settings(pool: asyncpg.pool.Pool, guild_id: int) -> Optional[GuildSettings]:
#     async with pool.acquire() as conn:
#         conn: asyncpg.connection.Connection
#         row = await conn.fetchrow(" SELECT * from guild_settings WHERE guild_id = $1", guild_id)
#         return GuildSettings(**row) if row is not None else None
#

# endregion

# region Role DB Functions

@dataclass
class AllowedRole:
    """Data Storage for Allowed Role"""
    role_id: int
    guild_id: int
    cat_id: int
    description: Optional[str]
    emoji: Optional[int]

    # async def remove(self, pool: asyncpg.pool.Pool, role_id: int):
    #     await delete_role(pool, self.guild_id, role_id)
    async def remove(self, pool: asyncpg.pool.Pool):
        await delete_role(pool, self.guild_id, self.role_id)


@dataclass
class RoleCategory:
    cat_id: int
    guild_id: int
    cat_name: str
    cat_position: int
    description: Optional[str]
    pool: Optional[asyncpg.pool.Pool]
    roles: Optional[List[AllowedRole]] = None


    @property
    def bq_description(self) -> Optional[str]:
        """Reformats the description to be discord formatted as a multi-line block quote"""
        if self.description is None:
            return None

        split_cat_desc = self.description.splitlines()

        cat_desc = ""
        for line in split_cat_desc:
            cat_desc += f"> {line}\n"
        return cat_desc

    async def get_roles(self) -> List[AllowedRole]:
        if self.roles is None:
            self.roles = await get_roles_in_cat(self.pool, self.cat_id)

        return self.roles

    async def add_new_role(self, role_id: int, role_desc=""):
        await upsert_role(self.pool, self.guild_id, role_id, self.cat_id, role_desc)


    async def _rename(self, name: str):
        """Do not call this unless you are sure the name is unique."""
        await rename_role_cat(self.pool, self.cat_id, name)
        self.cat_name = name


    async def redescribe(self, description: str):
        await change_description_role_cat(self.pool, self.cat_id, description)
        self.description = description

    async def _move(self, new_position: int):
        """Do not call this unless you are aware of the positions of all categories. """
        await move_role_cat(self.pool, self.cat_id, new_position)
        self.cat_position = new_position


    async def delete(self):
        await delete_role_cat(self.pool, self.guild_id, self.cat_id)
        self.cat_id = self.guild_id = self.cat_name = self.pool = self.roles = None


    async def role_in(self, other_role: 'discord.Role'):
        await self.get_roles()

        for allowed_role in self.roles:
            if allowed_role.role_id == other_role.id:
                return True

        return False


@dataclass
class RoleCategories:
    cats: List[RoleCategory]
    guild_id: int
    pool: Optional[asyncpg.pool.Pool]

    @staticmethod
    def _sort_func(cat: RoleCategory):
        return cat.cat_position, cat.cat_id

    def sort(self):
        self.cats.sort(key=self._sort_func)

    def max_position(self) -> int:
        if len(self.cats) == 0:
            return 0

        self.sort()
        return self.cats[-1].cat_position


    async def add_new_cat(self, cat_name: str, cat_desc: str):
        if self.get_cat_by_name(cat_name) is not None:
            raise ValueError("A Category By That Name Already Exists")
        else:
            _max = self.max_position()
            await add_role_cat(self.pool, self.guild_id, cat_name, cat_desc, _max+1)
            # TODO: Update self.cats to include new addition.


    async def rename_cat(self, cat: RoleCategory, new_name: str):
        if self.get_cat_by_name(new_name) is not None:
            raise ValueError("A Category By That Name Already Exists")
        else:
            await cat._rename(new_name)


    async def role_in(self, other_role: 'discord.Role'):
        for cat in self.cats:
            await cat.get_roles()

            for allowed_role in cat.roles:
                if allowed_role.role_id == other_role.id:
                    return True

            return False

    def get_cat(self, cat_id: int) -> Optional[RoleCategory]:
        return discord.utils.get(self.cats, cat_id=cat_id)

    def get_cat_by_name(self, cat_name: str) -> Optional[RoleCategory]:
        return discord.utils.find(lambda x: x.cat_name.lower().strip() == cat_name.lower().strip(), self.cats)

    async def swap_position(self, first_cat_id: int, second_cat_id: int):
        if first_cat_id == second_cat_id:
            raise ValueError("Categories must be unique to swap their position!")

        first_cat = self.get_cat(first_cat_id)
        sec_cat = self.get_cat(second_cat_id)

        f_p = first_cat.cat_position
        s_p = sec_cat.cat_position

        if f_p != s_p:
            await sec_cat._move(f_p)
            await first_cat._move(s_p)
        else:
            # Somehow they are the same. Fall back by moving one of them to the end of the list.
            await sec_cat._move(self.max_position()+1)

        self.sort()

@db_deco
async def get_role_cats(pool: asyncpg.pool.Pool, gid: int) -> RoleCategories:  # List[RoleCategory]:
    async with pool.acquire() as conn:
        conn: asyncpg.connection.Connection
        raw_rows = await conn.fetch("SELECT * from role_categories WHERE guild_id = $1", gid)

        cats = RoleCategories(cats=[RoleCategory(**row, pool=pool) for row in raw_rows], guild_id=gid, pool=pool)
        cats.sort()
        return cats


# @db_deco
# async def get_role_category(pool: asyncpg.pool.Pool, gid: int, cat_id) -> RoleCategory:  # List[RoleCategory]:
#     async with pool.acquire() as conn:
#         conn: asyncpg.connection.Connection
#         raw_rows = await conn.fetch("SELECT * from role_categories WHERE guild_id = $1", gid)
#
#         cats = RoleCategories(cats=[RoleCategory(**row, pool=pool) for row in raw_rows], guild_id=gid, pool=pool)
#         cats.sort()
#         return cats


@db_deco
async def get_roles_in_cat(pool: asyncpg.pool.Pool, cat_id: int) -> List[AllowedRole]:
    async with pool.acquire() as conn:
        conn: asyncpg.connection.Connection
        raw_rows = await conn.fetch("SELECT * from allowed_roles where cat_id = $1", cat_id)

        return [AllowedRole(**row) for row in raw_rows]


@db_deco
async def get_roles_in_guild(pool: asyncpg.pool.Pool, gid: int) -> List[AllowedRole]:
    async with pool.acquire() as conn:
        conn: asyncpg.connection.Connection
        raw_rows = await conn.fetch("SELECT * from allowed_roles where guild_id = $1", gid)

        return [AllowedRole(**row) for row in raw_rows]


@db_deco
async def upsert_role(pool: asyncpg.pool.Pool, gid: int, role_id: int, cat_id: int, desc: Optional[str]):
    async with pool.acquire() as conn:
        conn: asyncpg.connection.Connection

        await conn.execute("""
                            INSERT INTO allowed_roles(role_id, guild_id, cat_id, description) VALUES($1, $2, $3, $4)
                            ON CONFLICT(role_id)
                            DO UPDATE SET cat_id = EXCLUDED.cat_id, description = EXCLUDED.description
                            """, role_id, gid, cat_id, desc)


@db_deco
async def move_role(pool: asyncpg.pool.Pool, gid: int, role_id: int, new_cat_id: int):
    async with pool.acquire() as conn:
        conn: asyncpg.connection.Connection
        await conn.execute(
            "UPDATE allowed_roles SET cat_id = $1 WHERE role_id = $2 AND guild_id = $3",
             new_cat_id, role_id, gid)


@db_deco
async def delete_role(pool: asyncpg.pool.Pool, gid: int, role_id: int):
    async with pool.acquire() as conn:
        conn: asyncpg.connection.Connection
        await conn.execute(
            "DELETE FROM allowed_roles WHERE role_id = $1 AND guild_id = $2",
            role_id, gid)


@db_deco
async def add_role_cat(pool: asyncpg.pool.Pool, gid: int, name: str, description: str, position: int):
    async with pool.acquire() as conn:
        conn: asyncpg.connection.Connection

        await conn.execute("""
                            INSERT INTO role_categories(guild_id, cat_name, description, cat_position) VALUES($1, $2, $3, $4)
                            """, gid, name, description, position)


@db_deco
async def rename_role_cat(pool: asyncpg.pool.Pool, cat_id: int, cat_name: str):
    async with pool.acquire() as conn:
        conn: asyncpg.connection.Connection

        await conn.execute("""
                           UPDATE role_categories SET cat_name = $1 WHERE cat_id = $2
                            """, cat_name, cat_id)


@db_deco
async def change_description_role_cat(pool: asyncpg.pool.Pool, cat_id: int, description: str):
    async with pool.acquire() as conn:
        conn: asyncpg.connection.Connection

        await conn.execute("""
                           UPDATE role_categories SET description = $1 WHERE cat_id = $2
                            """, description, cat_id)


@db_deco
async def move_role_cat(pool: asyncpg.pool.Pool, cat_id: int, cat_pos: int):
    async with pool.acquire() as conn:
        conn: asyncpg.connection.Connection

        await conn.execute("""
                           UPDATE role_categories SET cat_position = $1 WHERE cat_id = $2
                            """, cat_pos, cat_id)


@db_deco
async def delete_role_cat(pool: asyncpg.pool.Pool, gid: int, cat_id: int):
    async with pool.acquire() as conn:
        conn: asyncpg.connection.Connection
        await conn.execute(
            "DELETE FROM role_categories WHERE cat_id = $1",
             cat_id)

# endregion

# region Cached Messages DB Functions
# ----- Cached Messages DB Functions ----- #

@dataclass
class CachedMessage:
    message_id: int
    guild_id: int
    user_id: int
    ts: datetime
    content: str
    system_pkid: Optional[str]
    member_pkid: Optional[str]
    pk_system_account_id: Optional[int]


@db_deco
async def cache_message(pool, sid: int, message_id: int, author_id: int, content: str, timestamp: datetime):
    if timestamp is None:
        log.info("FDSF")
    msg_ts = timestamp.timestamp()
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO messages(guild_id, message_id, user_id, content, ts) VALUES($1, $2, $3, $4, $5)", sid, message_id, author_id, content, msg_ts)


@db_deco
async def cache_pk_message(pool, sid: int, message_id: int, author_id: int, content: str, timestamp: datetime, system_pkid:str, member_pkid:str):
    """Only use for history population. Timestamp must be in UTC"""
    msg_ts = timestamp.timestamp()
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO messages(guild_id, message_id, user_id, content, ts, system_pkid, member_pkid) VALUES($1, $2, $3, $4, $5, $6, $7)", sid, message_id, author_id, content, msg_ts, system_pkid, member_pkid)


@db_deco
async def get_cached_message(pool, sid: int, message_id: int) -> Optional[CachedMessage]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM messages WHERE message_id = $1", message_id)
        return CachedMessage(**row) if row is not None else None


@db_deco
async def get_cached_messages_after_timestamp(pool, timestamp: datetime, sid: int, user_id: int) -> List[CachedMessage]:
    """ Timestamp must be in UTC"""
    async with pool.acquire() as conn:
        # now = datetime.now()
        # offset = timedelta(hours=hours)
        # before = now - offset
        before = timestamp.timestamp()
        raw_rows = await conn.fetch(" SELECT * from messages where ts > $1 and guild_id = $2 AND user_id = $3", before, sid, user_id)
        messages = [CachedMessage(**row) for row in raw_rows]
        return messages


@db_deco
async def get_all_cached_messages_after_timestamp(pool, timestamp: datetime, sid: int) -> List[CachedMessage]:
    """ Timestamp must be in UTC"""
    async with pool.acquire() as conn:
        # now = datetime.now()
        # offset = timedelta(hours=hours)
        # before = now - offset
        before = timestamp.timestamp()
        raw_rows = await conn.fetch(" SELECT * from messages where ts > $1 and guild_id = $2", before, sid)
        messages = [CachedMessage(**row) for row in raw_rows]
        return messages


@db_deco
async def update_cached_message_pk_details(pool, sid: int, message_id: int, system_pkid: str, member_pkid: str,
                                           pk_system_account_id: int):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE messages SET system_pkid = $1, member_pkid = $2, user_id = $3 WHERE message_id = $4",
                           system_pkid, member_pkid, pk_system_account_id, message_id)


@db_deco
async def delete_cached_message(pool, sid: int, message_id: int):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM messages WHERE message_id = $1", message_id)


@db_deco
async def get_number_of_rows_in_messages(pool, table: str = "messages") -> int:  # Slow! But only used for g!top so okay.
    async with pool.acquire() as conn:
        num_of_rows = await conn.fetchval("SELECT COUNT(*) FROM messages")
        return num_of_rows

# endregion


# region Members DB Functions

@dataclass
class DBMember:
    user_id: int
    guild_id: int
    internal_user_id: int
    join_count: int
    inactive_L1_count: int
    inactive_L2_count: int
    post_count: int
    become_member: bool
    soft_banned: bool


@db_deco
async def upsert_new_member(pool: asyncpg.pool.Pool, guild_id: int, user_id: int, pn_user_id: int):
    async with pool.acquire() as conn:
        conn: asyncpg.connection.Connection

        await conn.execute("""
                            INSERT INTO members(user_id, guild_id, internal_user_id) VALUES($1, $2, $3)
                            ON CONFLICT(guild_id, user_id)
                            DO UPDATE 
                            SET join_count = join_count + 1
                            """, user_id, guild_id, pn_user_id)


@db_deco
async def get_member(pool, guild_id: int, user_id: int) -> Optional[DBMember]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM members WHERE guild_id = $1 and user_id = $2", guild_id, user_id)
        return DBMember(**row) if row is not None else None


@db_deco
async def get_linked_members(pool, guild_id: int, pn_user_id: int) -> List[DBMember]:
    async with pool.acquire() as conn:
        raw_rows = await conn.fetch("SELECT * FROM members WHERE guild_id = $1 and internal_user_id = $2", guild_id, pn_user_id)
        members = [DBMember(**row) for row in raw_rows]
        return members


@db_deco
async def update_member(pool, guild_id: int, user_id: int, increment_L1_count: bool = False, increment_L2_count: bool = False,
                        increase_post_count: int = 0, set_membership: bool = False):
    async with pool.acquire() as conn:
        if increment_L1_count:
            await conn.execute(
                "UPDATE members SET inactive_l1_count = inactive_l1_count + 1 WHERE guild_id = $1 and user_id = $2",
                guild_id, user_id)

        if increment_L2_count:
            await conn.execute(
                "UPDATE members SET inactive_l2_count = inactive_l2_count + 1 WHERE guild_id = $1 and user_id = $2",
                guild_id, user_id)

        if increment_L1_count:
            await conn.execute(
                "UPDATE members SET inactive_l1_count = inactive_l1_count + 1 WHERE guild_id = $1 and user_id = $2",
                guild_id, user_id)

        if increase_post_count:
            await conn.execute(
                "UPDATE members SET post_count = post_count + $3 WHERE guild_id = $1 and user_id = $2",
                guild_id, user_id, increase_post_count)

        if set_membership:
            await conn.execute(
                "UPDATE members SET became_member = TRUE WHERE guild_id = $1 and user_id = $2",
                guild_id, user_id)


@db_deco
async def update_member_softban(pool, guild_id: int, user_id: int, ban: bool):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE members SET soft_banned = $3 WHERE guild_id = $1 and user_id = $2",
            guild_id, user_id, ban)


# endregion


# region Inactivity History DB Functions

@dataclass
class InactivityEvent:
    id: int
    user_id: int
    guild_id: int
    current_level: int
    previous_level: int
    reason: str
    ts: int

    @property
    def timestamp(self):
        return datetime.utcfromtimestamp(self.ts)


    @property
    def current_lvl_str(self):
        return self.lvl_to_str(self.current_level)


    @property
    def previous_lvl_str(self):
        return self.lvl_to_str(self.previous_level)


    def lvl_to_str(self, lvl: int) -> str:
        if lvl == 0:
            return "Active"
        if lvl == 1:
            return "Inactive - Level 1"
        if lvl == 2:
            return "Inactive - Level 2"
        return "Unknown"

@db_deco
async def add_inactivity_event(pool: asyncpg.pool.Pool, guild_id: int, user_id: int, current_level: int, previous_level: int,
                               reason: Optional[str] = None, event_ts: Optional[datetime] = None):
    if event_ts is None:
        event_ts = datetime.utcnow()
    ts = event_ts.timestamp()

    if reason is None:
        reason = "No Reason Given"

    async with pool.acquire() as conn:
        await conn.execute("""INSERT INTO 
                              inactivity_history(user_id, guild_id, current_level, previous_level, reason, ts) VALUES($1, $2, $3, $4, $5, $6)
                           """, user_id, guild_id, current_level, previous_level, reason, ts)

@db_deco
async def get_inactivity_events(pool, guild_id: int, user_id: int) -> List[InactivityEvent]:
    async with pool.acquire() as conn:
        raw_rows = await conn.fetch("SELECT * FROM inactivity_history WHERE guild_id = $1 and user_id = $2", guild_id, user_id)
        events = [InactivityEvent(**row) for row in raw_rows]
        return events


# @db_deco
# async def get_most_recent_inactivity_event(pool, guild_id: int, user_id: int) -> Optional[InactivityEvent]:
#     async with pool.acquire() as conn:
#
#         row = await conn.fetchrow("SELECT * FROM inactivity_history WHERE guild_id = $1 and user_id = $2", guild_id, user_id)
#         return InactivityEvent(**row) if row is not None else None




# endregion


# region Current Inactive Members Functions

@dataclass
class InactiveMember:
    user_id: int
    guild_id: int
    inactivity_level: int
    ts: int

    @property
    def timestamp(self):
        return datetime.utcfromtimestamp(self.ts)



@db_deco
async def upsert_inactive_user(pool: asyncpg.pool.Pool, guild_id: int, user_id: int, inactivity_level: int,
                               event_ts: Optional[datetime] = None):
    if event_ts is None:
        event_ts = datetime.utcnow()
    ts = event_ts.timestamp()

    async with pool.acquire() as conn:
        await conn.execute("""
                            INSERT INTO current_inactive_members(user_id, guild_id, inactivity_level, ts) VALUES($1, $2, $3, $4)
                            ON CONFLICT(guild_id, user_id)
                            DO UPDATE 
                            SET inactivity_level = EXCLUDED.inactivity_level, ts = EXCLUDED.ts
                            """, user_id, guild_id, inactivity_level, ts)


@db_deco
async def get_inactive_user(pool, guild_id: int, user_id: int) -> Optional[InactiveMember]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM current_inactive_members WHERE guild_id = $1 and user_id = $2", guild_id, user_id)
        return InactiveMember(**row) if row is not None else None


@db_deco
async def remove_inactive_user(pool, guild_id: int, user_id: int):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM current_inactive_members WHERE guild_id = $1 AND user_id = $2", guild_id, user_id)

# endregion


# region Temp Removed Member Roles Functions

@dataclass
class RoleRemovedFromUser:
    user_id: int
    guild_id: int
    role_id: int

    @property
    def id(self):
        return self.role_id

    def __hash__(self):
        return hash(self.id)


@db_deco
async def add_role_tmp_removed_from_user(pool: asyncpg.pool.Pool, guild_id: int, user_id: int, role_id: int):

    async with pool.acquire() as conn:
        await conn.execute("""INSERT INTO
                              temp_removed_member_roles(user_id, guild_id, role_id) VALUES($1, $2, $3)
                           """, user_id, guild_id, role_id)
        # await conn.execute("""
        #                     INSERT INTO temp_removed_member_roles(user_id, guild_id, role_id) VALUES($1, $2, $3)
        #                     ON CONFLICT(guild_id, user_id, role_id)
        #                     DO NOTHING
        #                     """, user_id, guild_id, role_id)


@db_deco
async def get_roles_tmp_removed_from_user(pool, guild_id: int, user_id: int) -> List[RoleRemovedFromUser]:
    async with pool.acquire() as conn:
        raw_rows = await conn.fetch("SELECT * FROM temp_removed_member_roles WHERE guild_id = $1 and user_id = $2",
                                    guild_id, user_id)

        roles = [RoleRemovedFromUser(**row) for row in raw_rows]
        return roles


@db_deco
async def delete_role_tmp_removed_from_all_user(pool, guild_id: int, role_id: int):
    """
    This function removes a role from all entries in the temp_removed_member_roles Table.
    It is to be used when a role is deleted from the guild.
    """
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM temp_removed_member_roles WHERE guild_id = $1 AND role_id = $2", guild_id, role_id)


@db_deco
async def delete_inactive_member_removed_roles(pool, guild_id: int, user_id: int):
    """
    This function removes all role from a specific user in the temp_removed_member_roles Table.
    It is to be used when a member leaves or when giving the roles back.
    """
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM temp_removed_member_roles WHERE guild_id = $1 AND user_id = $2", guild_id, user_id)


# endregion


# region Join Log Functions

@dataclass
class JoinLogEvent:
    id: int
    user_id: int
    guild_id: int
    ts: int

    inviter_id: int
    invite_id: str
    invite_name: Optional[str]

    @property
    def timestamp(self):
        return datetime.utcfromtimestamp(self.ts)


@db_deco
async def add_join_event(pool: asyncpg.pool.Pool, guild_id: int, user_id: int, event_ts: Optional[datetime] = None):

    if event_ts is None:
        event_ts = datetime.utcnow()
    ts = event_ts.timestamp()

    async with pool.acquire() as conn:
        await conn.execute("""INSERT INTO 
                              join_log(user_id, guild_id, ts) VALUES($1, $2, $3)
                           """, user_id, guild_id, ts)


@db_deco
async def update_join_event(pool: asyncpg.pool.Pool, guild_id: int, user_id: int, inviter_id: int, invite_id: str,
                         invite_name: Optional[str] = None):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE join_log SET inviter_id = $1, invite_id = $2, invite_name = $3 WHERE guild_id = $4 AND user_id = $5",
             inviter_id, invite_id, invite_name, guild_id, user_id)

@db_deco
async def get_join_events(pool, guild_id: int, user_id: int) -> List[JoinLogEvent]:
    async with pool.acquire() as conn:
        raw_rows = await conn.fetch("SELECT * FROM join_log WHERE guild_id = $1 and user_id = $2",
                                    guild_id, user_id)

        join_logs = [JoinLogEvent(**row) for row in raw_rows]
        return join_logs

# endregion

# region React Roles Functions

# @dataclass
# class ReactRolePost:
#     guild_id: int
#     message_id: int
#     role_id: int
#     emoji_id: str

# endregion
# ---------- Table Creation ---------- #
@db_deco
async def create_tables(pool: asyncpg.pool.Pool):
    async with pool.acquire() as conn:
        conn: asyncpg.connection.Connection
        # TODO: Move interview_type over to an int and use an enum?

        # ALTER TABLE interviews ADD COLUMN interview_type_msg_id BIGINT DEFAULT NULL;
        await conn.execute('''
                               CREATE TABLE if not exists interviews(
                               guild_id                 BIGINT NOT NULL,
                               member_id                BIGINT NOT NULL,
                               user_name                TEXT NOT NULL,
                               channel_id               BIGINT NOT NULL,
                               question_number          INT DEFAULT 0,
                               interview_finished       BOOLEAN default FALSE,
                               paused                   BOOLEAN default FALSE,
                               interview_type           TEXT default 'unknown',   
                               read_rules               BOOLEAN default FALSE,
                               join_ts                  BIGINT NOT NULL,
                               interview_type_msg_id    BIGINT DEFAULT NULL,
                               PRIMARY KEY              (member_id, channel_id)
                              );
                        ''')

        # ALTER TABLE guild_settings ADD COLUMN welcome_back_react_msg_id BIGINT DEFAULT NULL;
        await conn.execute('''
                               CREATE TABLE if not exists guild_settings(
                               guild_id                         BIGINT NOT NULL,
                               raid_level                       INT DEFAULT 0,
                               --welcome_back_react_msg_id        BIGINT DEFAULT NULL,
                               PRIMARY KEY              (guild_id)
                              );
                        ''')

        await conn.execute('''
                               CREATE TABLE if not exists role_categories(
                               cat_id                   SERIAL PRIMARY KEY,
                               guild_id                 BIGINT NOT NULL,
                               cat_name                 TEXT default 'Other',
                               description              TEXT DEFAULT NULL,
                               cat_position             INT NOT NULL
                              );
                        ''')

        await conn.execute('''
                               CREATE TABLE if not exists allowed_roles(
                               role_id                  BIGINT PRIMARY KEY,
                               guild_id                 BIGINT NOT NULL,
                               cat_id                   BIGINT NOT NULL REFERENCES role_categories(cat_id) ON DELETE CASCADE,
                               description              TEXT DEFAULT NULL,
                               emoji                    BIGINT DEFAULT NULL
                              );
                        ''')


        """ -- Added 3/6/2021 -- """
        await conn.execute('''
                           CREATE TABLE if not exists messages(
                               message_id           BIGINT PRIMARY KEY,
                               guild_id             BIGINT NOT NULL,
                               user_id              BIGINT NOT NULL,  --Could be a webhook id for PK messages?
                               ts                   BIGINT NOT NULL,  --TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                               content              TEXT DEFAULT NULL,
                               system_pkid          TEXT DEFAULT NULL,
                               member_pkid          TEXT DEFAULT NULL,
                               pk_system_account_id BIGINT DEFAULT NULL  --Discord ID associated with the PK System that sent the message.
                           )
                       ''')


        """ -- Added 3/13/2021 -- """

        """
        This table tracks details on each user who visits PN. 
        """
        await conn.execute('''
                           CREATE TABLE if not exists members(
                                user_id              BIGINT NOT NULL,       -- Discord User ID
                                guild_id             BIGINT NOT NULL,       -- Discord Guild ID
                                internal_user_id     BIGINT NOT NULL,       -- Internally Generated ID to link together alt accounts
                                join_count           INT DEFAULT 1,         -- How many times has the user joined the server
                                inactive_L1_count    INT DEFAULT 0,         -- How many times has the user went Inactive - Level One
                                inactive_L2_count    INT DEFAULT 0,         -- How many times has the user went Inactive - Level Two
                                post_count           INT DEFAULT 0,         -- Users Total post count
                                became_member        BOOL DEFAULT FALSE,    -- Has this user ever been given membership
                                soft_banned          BOOL DEFAULT FALSE,    -- Is the user `Soft Banned`
                                PRIMARY KEY          (user_id, guild_id)
                           )
                       ''')


        """
        This table tracks details on each *instance* of a join event @ PN 
        """
        await conn.execute('''
                              CREATE TABLE if not exists join_log(
                                  id                   SERIAL PRIMARY KEY,
                                  user_id              BIGINT NOT NULL,    -- Discord User ID
                                  guild_id             BIGINT NOT NULL,    -- Discord Guild ID
                                  ts                   BIGINT NOT NULL,    -- Timestamp of when the user joined
                                  
                                  inviter_id           BIGINT DEFAULT NULL,    -- Discord User ID of the person who created the invite (Most Recent)
                                  invite_id            TEXT DEFAULT NULL,      -- The Discord Invite Code / URL (Most Recent)
                                  invite_name          TEXT DEFAULT NULL   -- GG Name for the invite (Most Recent)
                              )
                          ''')

        """
        This table tracks each *instance* that a member was deemed to be Inactive or became active again.
        """
        await conn.execute('''
                           CREATE TABLE if not exists inactivity_history(
                                id                   SERIAL PRIMARY KEY,
                                user_id              BIGINT NOT NULL,       -- Discord User ID
                                guild_id             BIGINT NOT NULL,       -- Discord Guild ID
                                current_level        INT NOT NULL,          -- The inactivity level the user is now at. 0: Active, 1: Inactive - One, 2: Inactive - Two
                                previous_level       INT NOT NULL,          -- The inactivity level the user was previously at.  -1: None, 0: Active, 1: Inactive - One, 2: Inactive - Two
                                reason               TEXT NOT NULL,         -- Why the user was marked active or inactive.
                                ts                   BIGINT NOT NULL        -- Timestamp of when the user was marked as inactive or active.
                            )
                        ''')

        """
        This table tracks the users that are CURRENTLY marked Inactive, aka we have been given either the "Inactive Member - Level 1" or "Inactive Member - Level 2" roles to.
        """
        await conn.execute('''
                           CREATE TABLE if not exists current_inactive_members(
                               user_id              BIGINT NOT NULL,    -- Discord User ID
                               guild_id             BIGINT NOT NULL,    -- Discord Guild ID
                               inactivity_level     INT NOT NULL,       -- 1 or 2. Corresponds to which 'Inactivity Level' they are currently at.
                               ts                   BIGINT NOT NULL,    -- Timestamp of when the user was marked as inactive
                               PRIMARY KEY          (user_id, guild_id)
                           )
                       ''')


        """
        The temp_removed_member_roles table keeps track of the roles PNBot removed from a user when giving a inactive role or moving a user to #cooldown,
         so that it can give those roles back when it subsequently removes the inactive role or removes them from #cooldown.

        Be sure to remove all entries belonging to a **USER** when said user leaves the server. The entry will not be DELETE CASCADED as we are keeping member info indefinitely.

        Be sure to remove all entries belonging to a **ROLE** when said role is deleted. We can not use the "allowed_roles" Table as we will be dealing with roles that can not be on that table (Such as the NSFW role).
        """
        await conn.execute('''
                           CREATE TABLE if not exists temp_removed_member_roles(
                               user_id              BIGINT NOT NULL,    -- Discord User ID
                               guild_id             BIGINT NOT NULL,    -- Discord Guild ID
                               role_id              BIGINT NOT NULL,    -- Discord Role ID
                               PRIMARY KEY          (user_id, role_id)
                           )
                       ''')

        #
        # await conn.execute('''
        #                       CREATE TABLE if not exists react_role_post(
        #                           message_id           BIGINT NOT NULL,    -- Discord User ID
        #                           guild_id             BIGINT NOT NULL,    -- Discord Guild ID
        #                           role_id              BIGINT NOT NULL,
        #                           emoji_id             TEXT NOT NULL,
        #                           PRIMARY KEY          (message_id, guild_id, role_id, emoji_id)
        #                       )
        #                   ''')

        # await conn.execute('''
        #                        CREATE TABLE if not exists member_activity(
        #                        member_id                BIGINT NOT NULL,
        #                        guild_id                 BIGINT NOT NULL,
        #                        ts                       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        #                        PRIMARY KEY              (member_id, guild_id)
        #                       );
        #                 ''')

        # await conn.execute('''
        #                        CREATE TABLE if not exists user_profiles(
        #                        member_id                BIGINT NOT NULL,
        #                        guild_id                 BIGINT NOT NULL,
        #                        profile_name             TEXT NOT NULL,
        #                        profile_id               SERIAL UNIQUE,
        #                        PRIMARY KEY          (member_id, guild_id, profile_name)
        #                       );
        #                 ''')
        #
        # await conn.execute('''
        #                        CREATE TABLE if not exists role_profiles(
        #                        profile_id               BIGINT NOT NULL REFERENCES user_profiles(profile_id) ON DELETE CASCADE,
        #                        role_id                  BIGINT NOT NULL REFERENCES allowed_roles(role_id) ON DELETE CASCADE,
        #                        PRIMARY KEY              (profile_id, role_id)
        #                       );
        #                 ''')





