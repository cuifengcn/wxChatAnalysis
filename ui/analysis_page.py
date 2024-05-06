import asyncio
import json
import datetime as dt
import flet as ft
from typing import List
from api.wechat import WeChatAPI, MessageData, Analyzer
from ui.utils import async_partial, AD_NAME, AD_URL


class AnalysisPage(ft.Tab):
    def __init__(self, wechat_api, change_index_callback):
        self.wechat_api = wechat_api
        self.change_index_callback = change_index_callback
        super().__init__()
        self.visible = False
        self.text = "分析"
        self.message_view = MessagesView(wechat_api)
        self.analysis_view = AnalysisView(
            self.wechat_api,
            self.change_index_callback,
            refresh_messages=self.message_view.refresh_messages,
        )
        self.content = ft.Row(
            [
                ft.Container(self.analysis_view, padding=10, expand=1),
                ft.VerticalDivider(),
                ft.Container(self.message_view, padding=10),
            ],
            expand=1,
        )

    async def init(self):
        await self.analysis_view.init_user_select()


class AnalysisView(ft.Column):
    def __init__(self, wechat_api, change_index_callback, refresh_messages):
        self.wechat_api: WeChatAPI = wechat_api
        self.change_index_callback = change_index_callback
        self.refresh_messages = refresh_messages
        self.analyzer: Analyzer | None = None
        super().__init__()
        self.expand = 3
        self.user_select = ft.Dropdown(
            label="选择用户",
            options=[],
            width=250,
            on_change=self.user_select_change,
            content_padding=6,
            dense=True,
            alignment=ft.alignment.center,
        )
        self.user_search_btn = ft.IconButton(
            ft.icons.SEARCH, on_click=self.show_search_dialog
        )
        self.ai_checkbox = ft.Checkbox(
            label="AI分析", value=False, on_change=self.ai_checkbox_change
        )
        self.analysis_result = ft.ListView(
            spacing=10,
            padding=10,
            expand=1,
            animate_opacity=1000,
            controls=[],
        )
        self.controls = [
            ft.Row(
                [
                    ft.IconButton(ft.icons.ARROW_BACK, on_click=self.back_to_0_action),
                    self.user_select,
                    self.user_search_btn,
                    self.ai_checkbox,
                    ft.Container(width=10),
                    ft.FilledButton("开始分析", on_click=self.start_analysis_action),
                ],
                spacing=10,
            ),
            self.analysis_result,
        ]
        self.ai_username = None
        self.ai_password = None

    async def init_user_select(self):
        # {'wxid': 'wxid_xxxxxxx', 'code': 'dsjauodhsai', 'remark': '', 'name': '一月', 'country': 'AT',
        # 'province': 'Burgenland', 'city': '', 'gender': '女'}
        self.user_select.options = [
            ft.dropdown.Option(
                key=json.dumps(user),
                text=f'{user["name"]}({user["code"] or user["wxid"]})',
            )
            for user in self.wechat_api.friends_list
        ]
        await self.user_select.update_async()

    async def ai_checkbox_change(self, e=None):
        async def close(e=None):
            self.page.close_dialog()
            if self.ai_username and self.ai_password:
                self.ai_checkbox.value = True
                await self.page.client_storage.set_async(
                    "ai_username", self.ai_username
                )
                await self.page.client_storage.set_async(
                    "ai_password", self.ai_password
                )
            else:
                self.ai_checkbox.value = False
            await self.ai_checkbox.update_async()

        self.ai_username = await self.page.client_storage.get_async("ai_username")
        self.ai_password = await self.page.client_storage.get_async("ai_password")

        self.page.show_dialog(
            ft.AlertDialog(
                modal=True,
                content=ft.Column(
                    tight=True,
                    controls=[
                        ft.Markdown(
                            "请输入[元助手](http://yuanzhushou.com)的用户名和密码",
                            auto_follow_links=True,
                        ),
                        ft.TextField(
                            label="用户名",
                            value=self.ai_username,
                            on_change=lambda e: setattr(
                                self, "ai_username", e.control.value.strip()
                            ),
                        ),
                        ft.TextField(
                            label="密码",
                            value=self.ai_password,
                            on_change=lambda e: setattr(
                                self, "ai_password", e.control.value.strip()
                            ),
                        ),
                        ft.FilledButton("确定", on_click=close),
                    ],
                ),
            )
        )

    async def show_search_dialog(self, e=None):
        async def search_callback(user, e=None):
            self.user_select.value = json.dumps(user)
            await self.user_select.update_async()
            self.page.close_dialog()
            await self.user_select_change()

        self.page.show_dialog(
            UserSearchDialog(self.wechat_api.friends_list, search_callback)
        )

    async def user_select_change(self, e=None):
        if not self.user_select.value:
            return
        user = json.loads(self.user_select.value)
        user_id = user["wxid"]
        await self.refresh_messages(user_id)

    async def back_to_0_action(self, e=None):
        await self.change_index_callback(0)

    async def start_analysis_action(self, e=None):
        if not self.user_select.value:
            return
        analyzer = Analyzer(self.wechat_api)
        user = json.loads(self.user_select.value)
        user_id = user["wxid"]
        self.page.show_dialog(
            ft.AlertDialog(
                content=ft.Column(
                    [
                        ft.ProgressRing(),
                        ft.Text("分析中..."),
                        ft.Text("仅支持文本消息，内容仅供参考"),
                        ft.Container(
                            ft.Markdown(
                                f"访问 [ **{AD_NAME}** ]({AD_URL})\n\nAI对话AI绘画随心用",
                                selectable=True,
                                auto_follow_links=True,
                            ),
                            padding=ft.padding.symmetric(horizontal=50, vertical=10),
                            border_radius=12,
                            bgcolor=ft.colors.GREEN_200,
                        ),
                        ft.ElevatedButton(
                            "取消",
                            on_click=analyzer.stop_analysis,
                            visible=False,
                        ),
                    ],
                    tight=True,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                modal=True,
                actions_padding=0,
            )
        )

        async def error_callback(message):
            await self.page.show_dialog(
                ft.AlertDialog(content=ft.Column([
                    ft.Text(message)
                ], tight=True))
            )

        async def end_callback(views=None):
            if views:
                # 成功才赋值
                self.analyzer = analyzer
                self.page.close_dialog()
                self.analysis_result.controls.clear()
                # 增加个递显效果
                for v in views:
                    self.analysis_result.controls.append(v)
                    await self.analysis_result.update_async()
                    await asyncio.sleep(0.1)
                if ai_result:
                    self.analysis_result.controls.append(ft.Text("AI总结"))
                    self.analysis_result.controls.append(ai_result)
                    await self.analysis_result.update_async()
            self.page.close_dialog()

        await asyncio.sleep(0.5)

        # 增加ai分析结果
        ai_result = await analyzer.get_ai_result(
            user_id,
            self.ai_username,
            self.ai_password,
        )
        analyzer.start_analysis(user_id, end_callback, error_callback=error_callback)


class MessagesView(ft.Column):
    def __init__(self, wechat_api):
        super().__init__()
        self.wechat_api: WeChatAPI = wechat_api
        self.user_id: str | None = None
        self.page_offset: int = 0
        self.page_limit: int = 100
        self.prev_page_btn = ft.IconButton(
            ft.icons.ARROW_BACK,
            on_click=self.prev_page_action,
            disabled=True,
        )
        self.next_page_btn = ft.IconButton(
            ft.icons.ARROW_FORWARD,
            on_click=self.next_page_action,
            disabled=True,
        )
        self.list = ft.ListView(controls=[], expand=1, width=400, spacing=10)
        self.controls = [
            ft.Row(
                [
                    self.prev_page_btn,
                    self.next_page_btn,
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                tight=True,
            ),
            self.list,
        ]

    async def refresh_messages(self, user_id):
        self.wechat_api.user_id = user_id
        self.user_id = user_id
        await self.disable_page_btns()
        messages = self.wechat_api.get_chat_messages(
            user_id, offset=0, limit=self.page_limit
        )
        await self.put_messages(messages)
        self.page_offset = len(messages)
        self.prev_page_btn.disabled = True
        self.next_page_btn.disabled = len(messages) != self.page_limit
        await self.prev_page_btn.update_async()
        await self.next_page_btn.update_async()

    async def disable_page_btns(self):
        self.prev_page_btn.disabled = True
        await self.prev_page_btn.update_async()
        self.next_page_btn.disabled = True
        await self.next_page_btn.update_async()

    async def prev_page_action(self, e=None):
        """
        异步操作，用于获取前一页的消息并更新显示。
        """
        # 如果没有用户ID，则不执行任何操作
        if not self.user_id:
            return
        # 禁用页面上的按钮
        await self.disable_page_btns()
        # 更新页面偏移量，以显示前一页的内容
        self.page_offset = max(
            0, self.page_offset - self.page_limit - len(self.list.controls)
        )
        # 根据页面偏移量是否为0，禁用“上一页”按钮
        self.prev_page_btn.disabled = self.page_offset == 0
        # 从微信API获取聊天消息
        messages = self.wechat_api.get_chat_messages(
            self.user_id, offset=self.page_offset, limit=self.page_limit
        )
        # 将获取到的消息显示在页面上
        await self.put_messages(messages)
        # 更新页面偏移量，为加载下一页做准备
        self.page_offset += len(messages)
        # 根据获取到的消息数量是否等于页面限制数量，禁用“下一页”按钮
        self.next_page_btn.disabled = len(messages) != self.page_limit
        # 更新“上一页”和“下一页”按钮的状态
        await self.prev_page_btn.update_async()
        await self.next_page_btn.update_async()

    async def next_page_action(self, e=None):
        """
        异步操作，用于获取并显示下一页的消息。
        """
        # 如果没有用户ID，则不执行任何操作
        if not self.user_id:
            return
        # 禁用页面上的按钮
        await self.disable_page_btns()
        # 从微信API获取聊天消息
        messages = self.wechat_api.get_chat_messages(
            self.user_id, offset=self.page_offset, limit=self.page_limit
        )
        # 将消息放入聊天窗口
        await self.put_messages(messages)
        # 启用上一页按钮
        self.prev_page_btn.disabled = False
        # 更新页偏移量，为下一次请求做准备
        self.page_offset += len(messages)
        # 根据获取的消息数量，决定是否禁用下一页按钮
        self.next_page_btn.disabled = len(messages) != self.page_limit
        # 更新按钮状态
        await self.prev_page_btn.update_async()
        await self.next_page_btn.update_async()

    async def put_messages(self, messages: List[MessageData]):
        self.list.controls = [
            ft.Container(
                ft.Column(
                    [
                        ft.Text(
                            message.StrContent,
                            size=12,
                            overflow=ft.TextOverflow.ELLIPSIS,
                            selectable=True,
                            color=ft.colors.GREEN if message.IsSender == 1 else None,
                        ),
                        ft.Text(
                            str(dt.datetime.fromtimestamp(message.CreateTime)), size=10
                        ),
                    ],
                    tight=True,
                ),
                padding=ft.padding.symmetric(horizontal=10, vertical=6),
                border_radius=12,
                bgcolor=ft.colors.GREY_200,
            )
            for message in messages
        ]
        await self.list.update_async()
        await asyncio.sleep(0.35)
        self.list.scroll_to(0)


class UserSearchDialog(ft.AlertDialog):
    def __init__(self, users, select_callback):
        super().__init__()
        self.users = users
        self.select_callback = select_callback
        self.search_field = ft.TextField(
            label="搜索用户",
            on_submit=self.search_user,
            width=200,
            dense=True,
            content_padding=6,
            autofocus=True,
        )
        self.users_list = ft.ListView(
            spacing=10,
            padding=10,
            item_extent=30,
            expand=1,
            controls=[],
        )
        self.content = ft.Column(
            [
                ft.Row(
                    [
                        self.search_field,
                        ft.IconButton(ft.icons.SEARCH, on_click=self.search_user),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                self.users_list,
            ],
            width=300,
        )
        asyncio.get_event_loop().create_task(self.init_load_users())

    async def init_load_users(self):
        self.users_list.controls = [
            ft.Container(
                ft.Text(f'{user["name"]}({user["code"] or user["wxid"]})'),
                on_click=async_partial(self.select_callback, user),
                border_radius=12,
                bgcolor=ft.colors.GREY_200,
                padding=6,
            )
            for user in self.users
        ]
        await self.users_list.update_async()

    async def search_user(self, e=None):
        tmp = []
        keyword = self.search_field.value
        for u in self.users:
            if keyword in " ".join(u.values()):
                tmp.append(u)
        self.users_list.controls = [
            ft.Container(
                ft.Text(f'{user["name"]}({user["code"] or user["wxid"]})'),
                on_click=async_partial(self.select_callback, user),
                border_radius=12,
                bgcolor=ft.colors.GREY_200,
                padding=6,
            )
            for user in tmp
        ]
        await self.users_list.update_async()
