import time

import flet as ft
import matplotlib.pyplot as plt
import pandas as pd
import datetime as dt
from wordcloud import WordCloud


def plot_day_bar(df: pd.DataFrame):
    my_daily_count = df[df["is_sender"] == 1].resample("D").count()
    my_daily_count = my_daily_count[my_daily_count["content"] != 0]
    user_daily_count = df[df["is_sender"] == 0].resample("D").count()
    user_daily_count = user_daily_count[user_daily_count["content"] != 0]

    concat_dict = {}
    for index, row in my_daily_count.iterrows():
        index = index.timestamp()
        concat_dict[index] = [index, row["content"], 0]

    for index, row in user_daily_count.iterrows():
        index = index.timestamp()
        if index in concat_dict:
            concat_dict[index][2] = row["content"]
        else:
            concat_dict[index] = [index, 0, row["content"]]

    concat_list = list(concat_dict.values())
    concat_list.sort(key=lambda v: v[0])

    bar_groups = []
    labels = []

    bar_width = 12
    if len(concat_list) > 20:
        bar_width = 10
    if len(concat_list) > 40:
        bar_width = 8
    if len(concat_list) > 60:
        bar_width = 6
    if len(concat_list) > 80:
        bar_width = 4
    for index in range(len(concat_list)):
        t = dt.datetime.fromtimestamp(concat_list[index][0]).strftime("%Y-%m-%d")
        labels.append(
            ft.ChartAxisLabel(
                value=index,
                label=ft.Container(
                    ft.Text(
                        t[2:],
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    padding=2,
                ),
            )
        )

        bar_groups.append(
            ft.BarChartGroup(
                x=index,
                bar_rods=[
                    ft.BarChartRod(
                        rod_stack_items=[
                            ft.BarChartRodStackItem(
                                from_y=0,
                                to_y=concat_list[index][1],
                                color=ft.colors.GREEN,
                            ),
                            ft.BarChartRodStackItem(
                                from_y=concat_list[index][1],
                                to_y=concat_list[index][1] + concat_list[index][2],
                                color=ft.colors.BLUE,
                            ),
                        ],
                        from_y=0,
                        to_y=concat_list[index][1] + concat_list[index][2],
                        width=bar_width,
                        # color=ft.colors.GREEN,
                        tooltip=f"{t}\n我的消息：{concat_list[index][1]}条\n你的消息：{concat_list[index][2]}条",
                        tooltip_style=ft.TextStyle(color=ft.colors.WHITE),
                        border_radius=bar_width / 2,
                    ),
                ],
            )
        )

    chart = ft.BarChart(
        bar_groups=bar_groups,
        border=ft.border.all(1, ft.colors.GREY_400),
        # left_axis=ft.ChartAxis(labels_size=12, title=ft.Text("消息数"), title_size=12),
        # bottom_axis=ft.ChartAxis(
        #     labels=labels,
        #     labels_size=12,
        # ),
        horizontal_grid_lines=ft.ChartGridLines(
            color=ft.colors.GREY_300, width=1, dash_pattern=[3, 3]
        ),
        tooltip_bgcolor=ft.colors.BLACK87,
        interactive=True,
        groups_space=bar_width / 2,
        # expand=True,
    )

    return chart


def plot_hour_bar(df: pd.DataFrame):
    df = df.copy()
    df["hour"] = df["datetime"].dt.hour
    my_hour_count: pd.Series = (
        df[df["is_sender"] == 1].groupby("hour")["content"].count()
    )
    user_hour_count: pd.Series = (
        df[df["is_sender"] == 0].groupby("hour")["content"].count()
    )

    concat_dict = {}
    for i in range(24):
        concat_dict[i] = [i, 0, 0]

    for index, row in my_hour_count.items():
        concat_dict[index] = [index, row, 0]

    for index, row in user_hour_count.items():
        concat_dict[index][2] = row

    concat_list = list(concat_dict.values())
    concat_list.sort(key=lambda v: v[0])

    bar_groups = []
    labels = []

    bar_width = 12
    if len(concat_list) > 20:
        bar_width = 10
    if len(concat_list) > 40:
        bar_width = 8
    if len(concat_list) > 60:
        bar_width = 6
    if len(concat_list) > 80:
        bar_width = 4
    for index in range(len(concat_list)):
        t = f"{index}点-{index+1}点"
        labels.append(
            ft.ChartAxisLabel(
                value=index,
                label=ft.Container(
                    ft.Text(
                        t,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    padding=2,
                ),
            )
        )

        bar_groups.append(
            ft.BarChartGroup(
                x=index,
                bar_rods=[
                    ft.BarChartRod(
                        rod_stack_items=[
                            ft.BarChartRodStackItem(
                                from_y=0,
                                to_y=concat_list[index][1],
                                color=ft.colors.GREEN,
                            ),
                            ft.BarChartRodStackItem(
                                from_y=concat_list[index][1],
                                to_y=concat_list[index][1] + concat_list[index][2],
                                color=ft.colors.BLUE,
                            ),
                        ],
                        from_y=0,
                        to_y=concat_list[index][1] + concat_list[index][2],
                        width=bar_width,
                        # color=ft.colors.GREEN,
                        tooltip=f"{t}\n我的消息：{concat_list[index][1]}条\n你的消息：{concat_list[index][2]}条",
                        tooltip_style=ft.TextStyle(color=ft.colors.WHITE),
                        border_radius=bar_width / 2,
                    ),
                ],
            )
        )

    chart = ft.BarChart(
        bar_groups=bar_groups,
        border=ft.border.all(1, ft.colors.GREY_400),
        # left_axis=ft.ChartAxis(labels_size=12, title=ft.Text("消息数"), title_size=12),
        # bottom_axis=ft.ChartAxis(
        #     labels=labels,
        #     labels_size=12,
        # ),
        horizontal_grid_lines=ft.ChartGridLines(
            color=ft.colors.GREY_300, width=1, dash_pattern=[3, 3]
        ),
        tooltip_bgcolor=ft.colors.BLACK87,
        interactive=True,
        groups_space=bar_width / 2,
        # expand=True,
    )

    return chart


def plot_cloud(text_list):
    from main import MAIN_PATH

    wordcloud = WordCloud(
        font_path=MAIN_PATH.joinpath("assets", "fonts", "alipuhui.ttf"),
        background_color="white",  # 背景色为白色
        height=400,  # 高度设置为400
        width=800,  # 宽度设置为800
        scale=20,  # 长宽拉伸程度设置为20
        prefer_horizontal=0.9999,
    ).generate(" ".join(text_list))
    plt.figure(figsize=(8, 4))
    plt.imshow(wordcloud)
    plt.axis("off")
    """保存到本地"""
    if not MAIN_PATH.joinpath("tmp").exists():
        MAIN_PATH.joinpath("tmp").mkdir(parents=True, exist_ok=True)
    path = MAIN_PATH.joinpath("tmp").joinpath(f"{int(time.time())}.jpg")
    plt.savefig(path, dpi=600, bbox_inches="tight")
    return ft.Image(str(path))
