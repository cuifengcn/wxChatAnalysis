import flet as ft
from typing import Optional

from api.wechat import WeChatAPI
from ui.analysis_page import AnalysisPage
from ui.start_page import StartPage


class HomePage(ft.Tabs):
    def __init__(self):
        super().__init__()
        self.wechat_api = WeChatAPI()
        self.expand = 1
        self.selected_index = 0
        self.animation_duration = 300
        self.start_tab = StartPage(
            self.wechat_api, change_index_callback=self.change_index
        )
        self.analysis_tab = AnalysisPage(
            self.wechat_api, change_index_callback=self.change_index
        )
        self.tabs = [
            self.start_tab,
            self.analysis_tab,
        ]

    def did_mount(self):
        import atexit

        def goodbye():
            self.wechat_api.close_wcf()

        # 注册函数
        atexit.register(goodbye)

    async def change_index(self, index: int):
        self.start_tab.visible = index == 0
        await self.start_tab.update_async()
        self.analysis_tab.visible = index == 1
        await self.analysis_tab.update_async()

        self.selected_index = index
        await self.update_async()
        if index == 1:
            await self.analysis_tab.init()
