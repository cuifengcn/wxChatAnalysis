import flet as ft
from pathlib import Path
from ui.home_page import HomePage

MAIN_PATH = Path(__file__).parent.absolute()


async def main(page: ft.Page):
    page.title = "微信聊天对话统计"
    page.window_width = 1200
    page.window_height = 800
    page.padding = 0
    page.fonts = {"阿里普惠": "fonts/alipuhui.ttf"}
    page.theme = ft.Theme(font_family="阿里普惠", color_scheme=ft.ColorScheme())
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = ft.colors.GREY_200
    page.add(HomePage())


# Press the green button in the gutter to run the script.
if __name__ == "__main__":
    ft.app(target=main, assets_dir="assets")

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
