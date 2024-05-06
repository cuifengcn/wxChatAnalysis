import asyncio
from enum import Enum

import flet as ft

from api.wechat import WeChatAPI
from ui.utils import AD_NAME, AD_URL


class StartPage(ft.Tab):
    def __init__(self, wechat_api, change_index_callback):
        self.wechat_api = wechat_api
        self.change_index_callback = change_index_callback
        super().__init__()
        self.text = "首页"
        self.content = ft.Row(
            [
                ft.Container(GuideView(self.wechat_api), padding=10, expand=1),
                ft.VerticalDivider(),
                ft.Container(
                    DetectView(
                        self.wechat_api,
                        change_index_callback=self.change_index_callback,
                    ),
                    padding=10,
                    expand=1,
                ),
            ]
        )


class GuideView(ft.Column):
    def __init__(self, wechat_api):
        self.wechat_api = wechat_api
        super().__init__()
        self.expand = 1
        self.controls = [
            ft.Markdown(
                f"""# 使用教程
1. 安装 **[3.9.2.23](https://github.com/lich0821/WeChatFerry/releases/download/v39.0.14/WeChatSetup-3.9.2.23.exe)** 版本微信
2. 登录微信，在“设置”-“通用设置”中关闭“有更新时自动升级微信”
3. 点击【开始检测】，等待检测成功
4. (可选) 手机打开微信，进入“设置”-“聊天”-“聊天记录迁移与备份”，将聊天记录迁移至电脑微信
5. 点击【开始分析】，选择好友，点击【开始分析】，等待分析结果
6. (可选)填写[{AD_NAME}]({AD_URL})账号与密码，增加AI分析结果
                """,
                expand=1,
                selectable=True,
                auto_follow_links=True,
            ),
            ft.Markdown(
                f"""# 免责声明
1. 本工具仅供学习交流使用，请勿用于任何非法用途；
2. 用户自愿承担使用本工具产生的任何风险与责任；
3. 生成的内容不保证准确，仅供参考；
4. 本工具免费使用，请勿进行倒卖盈利。""",
                expand=1,
                selectable=True,
                auto_follow_links=True,
            ),
        ]


class DetectView(ft.Column):
    def __init__(self, wechat_api, change_index_callback):
        self.wechat_api: WeChatAPI = wechat_api
        self.change_index_callback = change_index_callback
        super().__init__()
        self.expand = 1
        # 连接微信
        self.wechat_connect_entity = DetectEntity("微信连接状态", "未知", value_editable=False)
        # 获取账号id
        self.wechat_userid_entity = DetectEntity("账号id", "未知", value_editable=False)
        # 获取好友列表
        self.wechat_friends_list_entity = DetectEntity(
            "好友列表", "未知", value_editable=False
        )
        # 获取数据库文件
        self.wechat_db_files_entity = DetectEntity("数据库文件", "未知", value_editable=False)
        self.start_detect_btn = ft.FilledButton(
            "开始检测", on_click=self.start_detect_action
        )
        self.detect_succeed = False
        self.start_analysis_btn = ft.FilledButton(
            "开始分析",
            disabled=not self.detect_succeed,
            on_click=self.start_analysis_action,
        )
        self.controls = [
            ft.Text("环境检测", size=20),
            self.build_container(self.wechat_connect_entity),
            self.build_container(self.wechat_userid_entity),
            self.build_container(self.wechat_friends_list_entity),
            self.build_container(self.wechat_db_files_entity),
            ft.Container(expand=1),
            ft.Row([self.start_detect_btn], alignment=ft.MainAxisAlignment.CENTER),
            ft.Row([self.start_analysis_btn], alignment=ft.MainAxisAlignment.CENTER),
        ]

    @staticmethod
    def build_container(child):
        return ft.Container(
            child,
            padding=ft.padding.symmetric(horizontal=16, vertical=6),
            border_radius=ft.border_radius.all(12),
            bgcolor=ft.colors.WHITE,
            width=350,
        )

    async def start_detect_action(self, e):
        # self.wechat_api.init_wcf()
        # print(self.wechat_api.wcf.get_self_wxid())
        # print(self.wechat_api.wcf.get_dbs())
        # print(self.wechat_api.wcf.get_tables('MSG0.db'))
        # print(self.wechat_api.wcf.query_sql('MSG0.db', 'SELECT * FROM MSG LIMIT 10'))
        async def start():
            self.start_detect_btn.text = "检测中"
            self.start_detect_btn.disabled = True
            await self.start_detect_btn.update_async()
            self.start_analysis_btn.disabled = True
            await self.start_analysis_btn.update_async()

        async def end(succeed=False):
            self.start_detect_btn.text = "开始检测"
            self.start_detect_btn.disabled = False
            await self.start_detect_btn.update_async()
            self.start_analysis_btn.disabled = not succeed
            await self.start_analysis_btn.update_async()

        await start()
        # 1. 连接微信
        await self.wechat_connect_entity.update_status(DetectEntityStatus.processing)
        await asyncio.sleep(0.5)
        res = self.wechat_api.init_wcf()
        if res:
            # 返回错误
            await self.wechat_connect_entity.update_status(DetectEntityStatus.error)
            await self.wechat_connect_entity.set_value(res)
            await end()
            return
        else:
            await self.wechat_connect_entity.update_status(DetectEntityStatus.ok)
            await self.wechat_connect_entity.set_value("已连接")
        # 2. 获取my id
        await self.wechat_userid_entity.update_status(DetectEntityStatus.processing)
        res = self.wechat_api.get_my_id()
        if res:
            # 返回错误
            await self.wechat_userid_entity.update_status(DetectEntityStatus.error)
            await self.wechat_userid_entity.set_value(res)
            await end()
            return
        else:
            await self.wechat_userid_entity.update_status(DetectEntityStatus.ok)
            await self.wechat_userid_entity.set_value(self.wechat_api.my_id)
        # 3. 获取好友列表
        res = self.wechat_api.get_friends_list()
        if res:
            # 返回错误
            await self.wechat_friends_list_entity.update_status(
                DetectEntityStatus.error
            )
            await self.wechat_friends_list_entity.set_value(res)
            await end()
            return
        else:
            await self.wechat_friends_list_entity.update_status(DetectEntityStatus.ok)
            await self.wechat_friends_list_entity.set_value(
                f"{len(self.wechat_api.friends_list)}名好友"
            )

        # 4. 数据库文件
        res = self.wechat_api.get_db_files()
        if res:
            # 返回错误
            await self.wechat_db_files_entity.update_status(DetectEntityStatus.error)
            await self.wechat_db_files_entity.set_value(res)
            await end()
            return
        else:
            await self.wechat_db_files_entity.update_status(DetectEntityStatus.ok)
            await self.wechat_db_files_entity.set_value(
                f"{len(self.wechat_api.db_files)}个数据库文件"
            )

        await end(succeed=True)
        self.wechat_api.clear_message_cache()
        self.page.show_dialog(
            ft.AlertDialog(
                content=ft.Column(
                    [
                        ft.Text("检测完成，去选择好友，开始分析吧"),
                        ft.FilledButton(
                            "Let's go!", on_click=self.start_analysis_action
                        ),
                    ],
                    tight=True,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                actions_padding=0,
            )
        )

    async def start_analysis_action(self, e=None):
        self.page.close_dialog()
        await asyncio.sleep(0.2)
        await self.change_index_callback(1)


class DetectEntityStatus(Enum):
    unknown = "未检测"
    ok = "成功"
    processing = "检测中"
    error = "失败"


class DetectEntity(ft.Row):
    def __init__(
            self,
            title: str | None,
            value: str | None,
            value_editable: bool = False,
            value_hint: str | None = None,
            status: DetectEntityStatus = DetectEntityStatus.unknown,
    ):
        super().__init__()
        self.width = 300
        self.alignment = ft.MainAxisAlignment.SPACE_BETWEEN
        self.value_field = ft.TextField(
            value=value,
            hint_text=value_hint,
            dense=True,
            width=150,
            content_padding=6,
            disabled=not value_editable,
        )
        self.status_text = self.build_status_text(status)
        self.controls = [
            ft.Text(title, size=16, width=100) if title else ft.Container(),
            self.value_field,
            self.status_text,
        ]

    async def update_status(self, new_status: DetectEntityStatus):
        match new_status:
            case DetectEntityStatus.unknown:
                self.status_text.value = new_status.value
            case DetectEntityStatus.ok:
                self.status_text.value = new_status.value
                self.status_text.color = ft.colors.GREEN
            case DetectEntityStatus.processing:
                self.status_text.value = new_status.value
                self.status_text.color = ft.colors.BLUE
            case DetectEntityStatus.error:
                self.status_text.value = new_status.value
                self.status_text.color = ft.colors.RED
        await self.status_text.update_async()

    def get_value(self):
        return self.value_field.value

    async def set_value(self, new_value):
        self.value_field.value = new_value
        await self.value_field.update_async()

    @staticmethod
    def build_status_text(status: DetectEntityStatus):
        width = 50
        size = 16
        match status:
            case DetectEntityStatus.unknown:
                return ft.Text(status.value, size=size, width=width)
            case DetectEntityStatus.ok:
                return ft.Text(
                    status.value, size=size, color=ft.colors.GREEN, width=width
                )
            case DetectEntityStatus.processing:
                return ft.Text(
                    status.value, size=size, color=ft.colors.BLUE, width=width
                )
            case DetectEntityStatus.error:
                return ft.Text(
                    status.value, size=size, color=ft.colors.RED, width=width
                )
