import asyncio
import json
import logging
from collections import Counter

import httpx
import jieba
import datetime as dt
import flet as ft
import pandas as pd
import traceback
from asyncio import Task
from dataclasses import dataclass, field
from typing import List

from wcferry import Wcf

from api.plot import *
from api.stop_words import stop_words
from ui.utils import extract_chinese, get_time_interval, ai_url


class WeChatAPI:
    def __init__(self):
        self.wcf: Wcf | None = None
        self.my_id: str | None = None
        self.user_id: str | None = None
        self.friends_list: list | None = None
        self.db_files: list | None = None
        self.message_cache = {}

    def init_wcf(self):
        try:
            if self.wcf is None:
                self.wcf = Wcf(debug=False, block=True)
        except Exception as e:
            logging.warning(f"init_wcf error {e}")
            return "连接微信失败"

    def close_wcf(self):
        if self.wcf is not None:
            self.wcf.cleanup()

    def get_my_id(self):
        if self.wcf is None:
            return "未连接微信"
        try:
            self.my_id = self.wcf.get_self_wxid()
            return None
        except Exception as e:
            logging.warning(f"get_my_id error {e}")
            return "获取用户id失败"

    def get_friends_list(self):
        if self.wcf is None:
            return "未连接微信"
        try:
            # {'wxid': 'wxid_t01111c11', 'code': 'SpanishSahara_', 'remark': '', 'name': '🦋', 'country': 'CN',
            # 'province': 'Jiangsu', 'city': 'Nanjing', 'gender': ''}
            self.friends_list = self.wcf.get_friends()
            self.friends_list.sort(key=lambda v: v["name"])
        except Exception as e:
            logging.warning(f"get_friends_list error {e}")
            return "获取好友列表失败"

    def get_db_files(self):
        if self.wcf is None:
            return "未连接微信"
        try:
            tmp = []
            # ['ChatMsg.db', 'Emotion.db', 'FunctionMsg.db', 'MSG0.db', 'MSG1.db', 'MSG2.db', 'Media.db',
            # 'MediaMSG0.db', 'MediaMSG1.db', 'MediaMSG2.db', 'MicroMsg.db', 'Misc.db']
            for name in self.wcf.get_dbs():
                if name.startswith("MSG"):
                    tmp.append(name)
            self.db_files = tmp
            self.db_files.sort(key=lambda v: int(v.split(".")[0][3:]))
        except Exception as e:
            logging.warning(f"get_db_files error {e}")
            return "获取数据库文件失败"

    def clear_message_cache(self):
        self.message_cache.clear()

    def get_chat_messages(self, user_id: str, offset=0, limit=100, desc=False):
        # 获取聊天记录
        # 聊天记录在 self.db_files 这几个数据库中，需要逐个，第一个查询完了，再接着第二个
        try:
            if user_id not in self.message_cache:
                self.message_cache[user_id] = CacheMessages(
                    self, user_id, self.db_files
                )
            return self.message_cache[user_id].get_messages(offset, limit, desc)
        except Exception as e:
            logging.error(f"get_chat_messages err {e}")
            return []


class CacheMessages:
    def __init__(self, wechat_api, user_id, db_files):
        self.wechat_api: WeChatAPI = wechat_api
        self.user_id = user_id
        self.db_files = db_files
        self.db_lines = {}

    def get_messages(self, offset=0, limit=100, desc=False):
        if len(self.db_lines) == 0:
            for db_file in self.db_files:
                query = f"SELECT COUNT(*) FROM MSG WHERE StrTalker = '{self.user_id}';"
                res = self.wechat_api.wcf.query_sql(
                    db_file,
                    query,
                )
                if not res:
                    self.db_lines[db_file] = 0
                else:
                    self.db_lines[db_file] = res[0]["COUNT(*)"]
        result = []
        dbs = self.db_files
        if desc:
            dbs = dbs[::-1]
        for db_name in dbs:
            lines_num = self.db_lines[db_name]
            if lines_num == 0:
                # 此db为空
                continue
            if offset > lines_num:
                # 此db有数据，但是比offset小，减去offset，然后在下一个db获取
                offset -= lines_num
                continue
            query = f"SELECT * FROM MSG WHERE StrTalker = '{self.user_id}' ORDER BY CreateTime {'DESC' if desc else ''} LIMIT {offset}, {limit};"
            res = self.wechat_api.wcf.query_sql(
                db_name,
                query,
            )
            if res:
                result.extend(res)
                if len(res) == limit:
                    # 获取的数据够了，结束
                    break
                # 不够，需要从下一个db继续获取，下一个db直接从0获取就行了
                offset = 0
                limit = limit - len(res)
        return self.format_messages([MessageData.from_dict(i) for i in result])

    def format_messages(self, messages: list["MessageData"]):
        res = []
        for m in messages:
            content = m.StrContent.replace("\n", "").replace("\r\n", "").strip()
            if "<msg><img " in content or "<imgdatahash></imgdatahash>" in content:
                m.StrContent = "[图片]"
            elif "<msg><videomsg " in content or "cdnrawvideoaeskey" in content:
                m.StrContent = "[视频]"
            elif "voicemsg" in content:
                m.StrContent = f"[语音]{extract_chinese(content)}"
            elif "<VoIPBubbleMsg>" in content:
                m.StrContent = f"[语音通话]{extract_chinese(content)}"
            elif "<msg><emoji" in content:
                m.StrContent = f"[EMOJI]"
            elif "location x" in content:
                m.StrContent = f"[定位]{extract_chinese(content)}"
            elif "<revokemsg>" in content:
                m.StrContent = f"{extract_chinese(content)}"
            res.append(m)
        return res


@dataclass
class MessageData:
    localId: int | None
    TalkerId: int | None
    MsgSvrID: int | None
    Type: int | None
    SubType: int | None
    IsSender: int | None
    CreateTime: int | None
    Sequence: int | None
    StatusEx: int | None
    FlagEx: int | None
    Status: int | None
    MsgServerSeq: int | None
    MsgSequence: int | None
    StrTalker: str | None
    StrContent: str | None
    DisplayContent: str | None
    BytesExtra: bytes | None

    @staticmethod
    def from_dict(data):
        return MessageData(
            localId=data.get("localId"),
            TalkerId=data.get("TalkerId"),
            MsgSvrID=data.get("MsgSvrID"),
            Type=data.get("Type"),
            SubType=data.get("SubType"),
            IsSender=data.get("IsSender"),
            CreateTime=data.get("CreateTime"),
            Sequence=data.get("Sequence"),
            StatusEx=data.get("StatusEx"),
            FlagEx=data.get("FlagEx"),
            Status=data.get("Status"),
            MsgServerSeq=data.get("MsgServerSeq"),
            MsgSequence=data.get("MsgSequence"),
            StrTalker=data.get("StrTalker"),
            StrContent=data.get("StrContent"),
            DisplayContent=data.get("DisplayContent"),
            BytesExtra=data.get("BytesExtra"),
        )


class Analyzer:
    def __init__(self, wechat_api: WeChatAPI):
        self.wechat_api: WeChatAPI = wechat_api
        self.analysis_task: Task | None = None
        self.end_callback = None
        self.theme_color = ft.colors.BLUE

        self.my_info: UserInfo | None = None
        self.user_info: UserInfo | None = None
        self.start_message_info: StartMessageInfo | None = None
        self.count_rank_info: CountRankInfo | None = None

        self.most_late_message: MostLateMessageInfo | None = None
        self.filter_messages = []
        self.message_df: pd.DataFrame | None = None

    def start_analysis(self, user_id: str, end_callback):
        self.end_callback = end_callback
        self.analysis_task = asyncio.create_task(
            self.generate_analysis_task(user_id, end_callback)
        )

    async def get_ai_result(self, user_id, username, password):
        if not username or not password:
            return None
        try:
            messages = self.get_chat_messages(user_id)
            message_string = "\n".join([i.StrContent for i in messages])
            url = ai_url
            res = ""
            async with httpx.AsyncClient().stream(
                method="POST",
                url=url,
                json={
                    "username": username,
                    "password": password,
                    "content": message_string,
                },
                timeout=300,
            ) as response:
                async for chunk in response.aiter_lines():
                    if chunk.startswith("data:"):
                        data = json.loads(chunk[5:])
                        if "result" in data and data["result"]:
                            res += data["result"]
                    else:
                        return self.build_container(ft.Text(chunk, selectable=True))
            return self.build_container(ft.Text(res, selectable=True))
        except Exception as e:
            logging.warning(f"{e} {traceback.format_exc()}")
            return self.build_container(ft.Text(str(e), selectable=True))

    def get_chat_messages(self, user_id) -> List[MessageData]:
        # 移除无用的信息
        res: List[MessageData] = []
        all_messages: List[MessageData] = self.wechat_api.get_chat_messages(
            user_id, offset=0, limit=100000
        )
        for message in all_messages:
            if message.Type == 10000:
                # 打招呼、撤回等系统消息，忽略
                continue
            for w in ["[图片]", "[视频]", "[语音通话]", "[EMOJI]", "[定位]"]:
                if message.StrContent.startswith(w):
                    # 把这些忽略掉
                    continue
            res.append(message)
        return res

    async def generate_analysis_task(self, user_id: str, end_callback):
        try:
            my_id = self.wechat_api.my_id
            # {'wxid': 'wxid_xxx', 'code': '', 'remark': '', 'name': 'xxx', 'country': '',
            # 'province': '', 'city': '', 'gender': '女'}
            self.my_info = UserInfo.from_dict(
                self.wechat_api.wcf.get_info_by_wxid(my_id)
            )
            self.user_info = UserInfo.from_dict(
                self.wechat_api.wcf.get_info_by_wxid(user_id)
            )
            all_messages: List[MessageData] = self.get_chat_messages(user_id)
            for message in all_messages:
                self.build_start_message(message)
                self.build_most_late_message(message)
                self.build_filter_message(message)

            self.build_count_rank()
            self.message_df = pd.DataFrame.from_records(self.filter_messages)
            if "datetime" in self.message_df.columns:
                self.message_df.set_index("datetime", inplace=True, drop=False)
            await end_callback(self.build_view())
        except Exception as e:
            logging.error(f"generate_analysis_task error {e} {traceback.format_exc()}")
            await end_callback()

    def build_start_message(self, message: MessageData):
        if not hasattr(self, "build_start_message_finished"):
            setattr(self, "build_start_message_finished", False)
        finished = getattr(self, "build_start_message_finished")
        if finished:
            return

        if not self.start_message_info:
            self.start_message_info = StartMessageInfo(
                start_time=dt.datetime.fromtimestamp(message.CreateTime),
                from_my=message.IsSender == 1,
                content=message.StrContent,
            )
        elif self.start_message_info.resp_content is None:
            #  还没收到对方的回复
            if self.start_message_info.from_my and message.IsSender == 1:
                # 仍然是自己的消息
                if (
                    message.CreateTime - self.start_message_info.start_time.timestamp()
                ) < 600:
                    # 规定一个600秒的限制
                    self.start_message_info.content += " " + message.StrContent
            elif (not self.start_message_info.from_my) and message.IsSender == 0:
                # 仍然是对方发的
                if (
                    message.CreateTime - self.start_message_info.start_time.timestamp()
                ) < 600:
                    # 规定一个600秒的限制
                    self.start_message_info.content += " " + message.StrContent
            else:
                # 是对方发的了
                self.start_message_info.resp_content = message.StrContent
                self.start_message_info.interval = (
                    message.CreateTime - self.start_message_info.start_time.timestamp()
                )
                setattr(self, "build_start_message_finished", True)

    def build_most_late_message(self, message: MessageData):
        def get_interval():
            # 计算和凌晨4点差多少秒
            datetime = dt.datetime.fromtimestamp(message.CreateTime)
            if datetime.hour < 4:
                return 4 * 3600 - (
                    datetime.hour * 3600 + datetime.minute * 60 + datetime.second
                )
            else:
                return (
                    24 * 3600
                    - (datetime.hour * 3600 + datetime.minute * 60 + datetime.second)
                    + 4 * 3600
                )

        if (
            not self.most_late_message
            or get_interval() < self.most_late_message.interval
        ):
            self.most_late_message = MostLateMessageInfo(
                datetime=dt.datetime.fromtimestamp(message.CreateTime),
                interval=get_interval(),
                message=message,
            )

    def build_filter_message(self, message: MessageData):
        self.filter_messages.append(
            {
                "datetime": dt.datetime.fromtimestamp(message.CreateTime),
                "is_sender": message.IsSender == 1,
                "content": message.StrContent,
            }
        )

    def build_count_rank(self):
        # [{'localId': 1, 'TalkerId': 1, 'MsgSvrID': 2061517216873451111, 'Type': 1, 'SubType': 0, 'IsSender': 0,
        # 'CreateTime': 1676545342, 'Sequence': 1676545342000, 'StatusEx': 0, 'FlagEx': 16, 'Status': 2, 'MsgServerSeq': 1,
        # 'MsgSequence': 791091113, 'StrTalker': '111@chatroom', 'StrContent': '[胜利]', 'DisplayContent': '',
        # 'Reserved0': 0, 'Reserved1': 3, 'Reserved2': None, 'Reserved3': None, 'Reserved4': None, 'Reserved5': None,
        # 'Reserved6': None, 'CompressContent': None, 'BytesExtra': b'', 'BytesTrans': None}]
        counts = {}
        for db in self.wechat_api.db_files:
            res = self.wechat_api.wcf.query_sql(
                db, "SELECT StrTalker, COUNT(*) AS count FROM Msg GROUP BY StrTalker;"
            )
            for i in res:
                if i["StrTalker"].endswith("@chatroom"):
                    # 把群聊去掉
                    continue
                if i["StrTalker"] not in counts:
                    counts[i["StrTalker"]] = i["count"]
                else:
                    counts[i["StrTalker"]] += i["count"]
        if self.wechat_api.user_id not in counts:
            return
        counter = Counter(counts)
        message_num = counter.get(self.wechat_api.user_id)
        rank = [item[1] for item in counter.most_common()].index(message_num) + 1
        percent = message_num / counter.total()
        top_10 = []
        for item in counter.most_common(10):
            info = self.wechat_api.wcf.get_info_by_wxid(item[0])
            top_10.append(info["remark"] or info["name"])
        self.count_rank_info = CountRankInfo(
            count_rank=rank, percent=percent, top_10=top_10
        )

    def build_view(self):
        res = []
        message_df: pd.DataFrame = self.message_df
        if len(message_df) == 0:
            res.append(self.build_container(ft.Text("我们没有任何对话")))
            return res
        part1 = []
        # xxx与xxx
        part1.append(
            ft.Text(
                spans=[
                    ft.TextSpan(
                        text=f"{self.my_info.remark or self.my_info.name}",
                        style=ft.TextStyle(
                            weight=ft.FontWeight.BOLD,
                            size=20,
                            color=self.theme_color,
                        ),
                    ),
                    ft.TextSpan(
                        text=f"与",
                        style=ft.TextStyle(weight=ft.FontWeight.BOLD, size=20),
                    ),
                    ft.TextSpan(
                        text=f"{self.user_info.remark or self.user_info.name}",
                        style=ft.TextStyle(
                            weight=ft.FontWeight.BOLD,
                            size=20,
                            color=self.theme_color,
                        ),
                    ),
                ],
                selectable=True,
            )
        )
        # 2023年3月11日 是我们相识的第1天
        start_year = self.start_message_info.start_time.year
        start_month = self.start_message_info.start_time.month
        start_day = self.start_message_info.start_time.day
        part1.append(
            ft.Text(
                spans=[
                    ft.TextSpan(
                        text=f"{start_year}年{start_month}月{start_day}日 ",
                        style=ft.TextStyle(weight=ft.FontWeight.BOLD),
                    ),
                    ft.TextSpan(text=f"是我们相识的第"),
                    ft.TextSpan(
                        text=f" 1 ",
                        style=ft.TextStyle(size=20, color=self.theme_color),
                    ),
                    ft.TextSpan(text=f"天"),
                ],
                selectable=True,
            )
        )
        if self.start_message_info.from_my:
            # 我先说
            part1.append(
                ft.Text(
                    spans=[
                        ft.TextSpan(text=f"我对你说的第一句话："),
                        ft.TextSpan(
                            text=f"“{self.start_message_info.content}”",
                            style=ft.TextStyle(color=self.theme_color),
                        ),
                    ],
                    selectable=True,
                )
            )
            if self.start_message_info.resp_content:
                # 对方回复
                part1.append(
                    ft.Text(
                        spans=[
                            ft.TextSpan(text=f"你在"),
                            ft.TextSpan(
                                text=f" {get_time_interval(self.start_message_info.interval)} ",
                                style=ft.TextStyle(weight=ft.FontWeight.BOLD),
                            ),
                            ft.TextSpan(text=f"后回复我："),
                            ft.TextSpan(
                                text=f"“{self.start_message_info.resp_content}”",
                                style=ft.TextStyle(color=self.theme_color),
                            ),
                        ],
                        selectable=True,
                    )
                )
        else:
            # 对方先说
            part1.append(
                ft.Text(
                    spans=[
                        ft.TextSpan(text=f"你对我说的第一句话："),
                        ft.TextSpan(
                            text=f"“{self.start_message_info.content}”",
                            style=ft.TextStyle(color=self.theme_color),
                        ),
                    ],
                    selectable=True,
                )
            )
            if self.start_message_info.resp_content:
                # 我回复
                part1.append(
                    ft.Text(
                        spans=[
                            ft.TextSpan(text=f"我在"),
                            ft.TextSpan(
                                text=f" {get_time_interval(self.start_message_info.interval)} ",
                                style=ft.TextStyle(weight=ft.FontWeight.BOLD),
                            ),
                            ft.TextSpan(text=f"后回复你："),
                            ft.TextSpan(
                                text=f"“{self.start_message_info.resp_content}”",
                                style=ft.TextStyle(color=self.theme_color),
                            ),
                        ],
                        selectable=True,
                    )
                )
        res.append(self.build_container(ft.Column(part1, tight=True)))
        res.append(ft.Container(height=10))
        part2 = []
        # 今天是2024年4月27日 是我们相识的第412天
        now = dt.datetime.now()
        days_to_now = (now - message_df.iloc[0].datetime).days
        part2.append(
            ft.Text(
                spans=[
                    ft.TextSpan(
                        text=f"今天是{now.year}年{now.month}月{now.day}日 ",
                        style=ft.TextStyle(weight=ft.FontWeight.BOLD),
                    ),
                    ft.TextSpan(text=f"是我们相识的第"),
                    ft.TextSpan(
                        text=f" {days_to_now} ",
                        style=ft.TextStyle(size=20, color=self.theme_color),
                    ),
                    ft.TextSpan(text=f"天"),
                ],
                selectable=True,
            )
        )
        # 在认识的xx天里
        my_words_count = (
            message_df[message_df["is_sender"] == 1]["content"].str.len().sum()
        )
        user_words_count = (
            message_df[message_df["is_sender"] == 0]["content"].str.len().sum()
        )
        daily_count = message_df.resample("D").count()
        daily_count = daily_count[daily_count["content"] > 0]
        part2.append(
            ft.Text(
                spans=[
                    ft.TextSpan(text=f"在认识的{days_to_now}天里，我们共进行了"),
                    ft.TextSpan(
                        text=f"{len(daily_count)}天、{len(message_df)}次、{my_words_count + user_words_count}字 ",
                        style=ft.TextStyle(color=self.theme_color, size=20),
                    ),
                    ft.TextSpan(text=f"的对话"),
                ],
                selectable=True,
            )
        )
        part2.append(
            ft.Text(
                spans=[
                    ft.TextSpan(text=f"我对你说了"),
                    ft.TextSpan(
                        text=f" {len(message_df[message_df['is_sender'] == 1])} ",
                        style=ft.TextStyle(color=self.theme_color),
                    ),
                    ft.TextSpan(text=f"句话，共"),
                    ft.TextSpan(
                        text=f" {my_words_count} ",
                        style=ft.TextStyle(color=self.theme_color),
                    ),
                    ft.TextSpan(text=f"字；"),
                    ft.TextSpan(text=f"你对我说了"),
                    ft.TextSpan(
                        text=f" {len(message_df[message_df['is_sender'] == 0])} ",
                        style=ft.TextStyle(color=self.theme_color),
                    ),
                    ft.TextSpan(text=f"句话，共"),
                    ft.TextSpan(
                        text=f" {user_words_count} ",
                        style=ft.TextStyle(color=self.theme_color),
                    ),
                    ft.TextSpan(text=f"字。"),
                ],
                selectable=True,
            )
        )
        res.append(self.build_container(ft.Column(part2, tight=True)))
        res.append(ft.Container(height=10))
        res.append(
            self.build_container(
                ft.Text(
                    spans=[
                        ft.TextSpan(text=f"我们聊过最多的话题有"),
                        ft.TextSpan(
                            text=f"{' '.join(self.get_topics(self.get_contents(message_df), top_n=20))}",
                            style=ft.TextStyle(color=self.theme_color, size=20),
                        ),
                        ft.TextSpan(text=f"。"),
                    ],
                    selectable=True,
                )
            )
        )
        res.append(ft.Container(height=10))
        # 聊天最多的一天
        # my_daily_count = message_df[message_df["is_sender"] == 1].resample("D").count()
        # user_daily_count = (
        #     message_df[message_df["is_sender"] == 0].resample("D").count()
        # )
        total_daily_count = message_df.resample("D").count()
        total_max_count_day = total_daily_count[
            total_daily_count["content"] == total_daily_count["content"].max()
        ]
        if total_daily_count["content"].max() > 3 and len(total_max_count_day) > 0:
            # 一天说的话都不超过2条，没统计的必要了
            line = total_max_count_day.iloc[0]
            line_index: dt.datetime = total_max_count_day.index[0]
            lines = message_df[message_df.index.normalize() == line_index]
            res.append(
                self.build_container(
                    ft.Text(
                        spans=[
                            ft.TextSpan(
                                text=f"{line_index.year}年{line_index.month}月{line_index.day}日 ",
                                style=ft.TextStyle(color=self.theme_color, size=20),
                            ),
                            ft.TextSpan(text=f"我们聊天最多，共进行了"),
                            ft.TextSpan(
                                text=f"{line['content']}次",
                                style=ft.TextStyle(color=self.theme_color, size=20),
                            ),
                            ft.TextSpan(text=f"对话，"),
                            ft.TextSpan(text=f"这一天我们讨论了"),
                            ft.TextSpan(
                                text=f"{' '.join(self.get_topics(self.get_contents(lines)))}",
                                style=ft.TextStyle(color=self.theme_color),
                            ),
                            ft.TextSpan(text=f"这些话题"),
                        ],
                        selectable=True,
                    )
                )
            )

        # 聊天最晚的一天
        if self.most_late_message and self.most_late_message.datetime.hour < 4:
            # 0-4点之间
            datetime = self.most_late_message.datetime - dt.timedelta(days=1)
            res.append(
                self.build_container(
                    ft.Text(
                        spans=[
                            ft.TextSpan(
                                text=f"{datetime.year}年{datetime.month}月{datetime.day}日这一天，我们聊到了凌晨"
                            ),
                            ft.TextSpan(
                                text=f"{datetime.hour}点{datetime.minute}分",
                                style=ft.TextStyle(color=self.theme_color),
                            ),
                            ft.TextSpan(
                                text=f"，我们当时一定有特别想聊的事情！"
                                f"那天{'我' if self.most_late_message.message.IsSender == 1 else '你'}聊的最后一句话是："
                            ),
                            ft.TextSpan(
                                text=f"“{self.most_late_message.message.StrContent}”",
                                style=ft.TextStyle(color=self.theme_color),
                            ),
                        ],
                        selectable=True,
                    )
                )
            )

        res.append(ft.Container(height=10))
        res.append(ft.Text("每日消息统计图"))
        res.append(plot_day_bar(self.message_df))
        res.append(ft.Text("日时段消息统计图"))
        res.append(plot_hour_bar(self.message_df))
        res.append(ft.Text("词云图"))
        res.append(
            plot_cloud(
                self.get_topics(self.get_contents(df=self.message_df), top_n=100)
            )
        )
        # 好友排名
        if self.count_rank_info:
            res.append(
                self.build_container(
                    ft.Text(
                        spans=[
                            ft.TextSpan(text=f"我们的对话次数在所有好友中的排名第"),
                            ft.TextSpan(
                                text=f" {self.count_rank_info.count_rank} ",
                                style=ft.TextStyle(color=self.theme_color, size=20),
                            ),
                            ft.TextSpan(text=f"，占所有对话的"),
                            ft.TextSpan(
                                text=f" {round(self.count_rank_info.percent * 100, 2)}% ",
                                style=ft.TextStyle(color=self.theme_color, size=20),
                            ),
                        ],
                        selectable=True,
                    )
                )
            )
            res.append(
                self.build_container(
                    ft.Text(
                        spans=[
                            ft.TextSpan(text=f"和我聊天最多的10个人是"),
                            ft.TextSpan(
                                text=f" {' '.join(self.count_rank_info.top_10)} ",
                                style=ft.TextStyle(color=self.theme_color),
                            ),
                        ],
                        selectable=True,
                    )
                )
            )

        return res

    @staticmethod
    def build_container(child):
        return ft.Container(
            child,
            padding=ft.padding.symmetric(horizontal=16, vertical=6),
            border_radius=ft.border_radius.all(12),
            bgcolor=ft.colors.WHITE,
            width=350,
        )

    async def stop_analysis(self, e=None):
        if self.analysis_task:
            self.analysis_task.cancel()
            self.analysis_task = None
        if self.end_callback:
            await self.end_callback()
            self.end_callback = None

    def get_contents(self, df):
        combined_string = " ".join(df["content"])
        return combined_string

    def get_topics(self, content, top_n=10):
        words = jieba.cut(content)
        filtered_words = [word for word in words if word not in stop_words]
        word_counts = Counter(filtered_words)
        return [i[0] for i in word_counts.most_common(top_n) if i[1] > 2]


@dataclass()
class UserInfo:
    wxid: str
    code: str
    remark: str
    name: str
    country: str
    province: str
    city: str
    gender: str
    avatar: str

    @staticmethod
    def from_dict(data):
        return UserInfo(
            wxid=data.get("wxid"),
            code=data.get("code"),
            remark=data.get("remark"),
            name=data.get("name"),
            country=data.get("country"),
            province=data.get("province"),
            city=data.get("city"),
            gender=data.get("gender"),
            avatar=data.get("avatar"),
        )


@dataclass()
class StartMessageInfo:
    start_time: dt.datetime
    from_my: bool
    content: str
    resp_content: str | None = field(default=None)
    interval: int | None = field(default=None)


@dataclass()
class MostLateMessageInfo:
    # 我们和凌晨4点进行比较
    datetime: dt.datetime
    interval: int  # most_datetime和凌晨4点进行比较的秒数
    message: MessageData


@dataclass()
class CountRankInfo:
    count_rank: int
    percent: float
    top_10: List[str]
