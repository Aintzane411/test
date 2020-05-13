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

@db_deco
async def add_new_interview(pool: asyncpg.pool.Pool, sid: int, member_id: int, username: str, channel_id: int,
                                  question_number: int = 0, interview_finished: bool = False, paused: bool = False,
                                  interview_type: str = 'unknown', read_rules: bool = False, join_ts: datetime = None):
    async with pool.acquire() as conn:
        conn: asyncpg.connection.Connection
        # Convert ts to str
        if join_ts is None:
            join_ts = datetime.utcnow()

        ts = join_ts.timestamp()
        await conn.execute(
            "INSERT INTO interviews(guild_id, member_id, user_name, channel_id, question_number, interview_finished, paused, interview_type, read_rules, join_ts) VALUES($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)",
            sid, member_id, username, channel_id, question_number, interview_finished, paused, interview_type, read_rules, ts)


# --- Updates --- #
@db_deco
async def update_interview_all_mutable(pool: asyncpg.pool.Pool, cid: int, mid: int, question_number: int, interview_finished: bool, paused: bool, interview_type: str, read_rules: bool):
    async with pool.acquire() as conn:
        conn: asyncpg.connection.Connection
        await conn.execute(
            "UPDATE interviews SET question_number = $1, interview_finished = $2, paused = $3, interview_type = $4, read_rules = $5 WHERE channel_id = $6 AND member_id = $7",
            question_number, interview_finished, paused, interview_type, read_rules, cid, mid)


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


# --- Selects --- #
interview_row_map = ('guild_id', 'member_id', 'user_name', 'channel_id', 'question_number', 'interview_finished',
                     'paused', 'interview_type', 'read_rules', 'join_ts')


def row_to_interview_dict(row: aiosqlite.Row) -> Dict:
    interview_dict = {
        interview_row_map[0]: row[0],   # Guild ID
        interview_row_map[1]: row[1],   # Member_id
        interview_row_map[2]: row[2],   # user_name
        interview_row_map[3]: row[3],   # channel_id
        interview_row_map[4]: row[4],   # quest_num
        interview_row_map[5]: bool(row[5]),   # int_fin
        interview_row_map[6]: bool(row[6]),   # Paused
        interview_row_map[7]: row[7],   # interview_type
        interview_row_map[8]: bool(row[8]),   # read_rules
        interview_row_map[9]: datetime.fromtimestamp(row[9])  # join_ts
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


# --- Guild Settings --- #
#
# @db_deco
# async def do_guild_settings_exist(pool: asyncpg.pool.Pool, sid: int) -> bool:
#     async with pool.acquire() as conn:
#         conn: asyncpg.connection.Connection
#         return (await conn.fetchval("SELECT COUNT(*) FROM guild_settings WHERE guild_id = ?", sid) > 0)


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


@dataclass
class AllowedRole:
    """Data Storage for Allowed Role"""
    role_id: int
    guild_id: int
    cat_id: int
    description: Optional[str]
    emoji: Optional[int]

    async def remove(self, pool: asyncpg.pool.Pool, role_id: int):
        await delete_role(pool, self.guild_id, role_id)


@dataclass
class RoleCategory:
    cat_id: int
    guild_id: int
    cat_name: str
    cat_position: int
    description: Optional[str]
    pool: Optional[asyncpg.pool.Pool]
    roles: Optional[List[AllowedRole]] = None


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


# ---------- Table Creation ---------- #
@db_deco
async def create_tables(pool: asyncpg.pool.Pool):
    async with pool.acquire() as conn:
        conn: asyncpg.connection.Connection
        # TODO: Move interview_type over to an int and use an enum?
        await conn.execute('''
                               CREATE TABLE if not exists interviews(
                               guild_id             BIGINT NOT NULL,
                               member_id            BIGINT NOT NULL,
                               user_name            TEXT NOT NULL,
                               channel_id           BIGINT NOT NULL,
                               question_number      INT DEFAULT 0,
                               interview_finished   BOOLEAN default FALSE,
                               paused               BOOLEAN default FALSE,
                               interview_type       TEXT default 'unknown',   
                               read_rules           BOOLEAN default FALSE,
                               join_ts              BIGINT NOT NULL,
                               PRIMARY KEY          (member_id, channel_id)
                              );
                        ''')

        await conn.execute('''
                               CREATE TABLE if not exists guild_settings(
                               guild_id                 BIGINT NOT NULL,
                               raid_level               INT DEFAULT 0,
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





