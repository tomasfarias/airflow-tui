import sys
from typing import Optional

from rich.align import Align
from rich.console import Console, ConsoleOptions, RenderableType, RenderResult
from rich.panel import Panel
from rich.style import StyleType
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.tree import Tree
from textual.app import App
from textual.reactive import Reactive
from textual.views import GridView
from textual.widgets import Button, ButtonPressed, Footer, Header, ScrollView

from airflow.models import DAG, DagBag, DagRun
from airflow.models.dagcode import DagCode


class DagButton(Button):
    mouse_over = Reactive(False)

    def __init__(self, dag: DAG, style: StyleType = "on red") -> None:
        self.dag = dag
        super().__init__(dag.dag_id, name=dag.dag_id, style=style)

    def render(self) -> RenderableType:
        return Align.left(
            self.dag.dag_id,
            vertical="middle",
            style="white on red" if self.mouse_over else "black on white",
        )

    def on_enter(self) -> None:
        self.mouse_over = True

    def on_leave(self) -> None:
        self.mouse_over = False


class DagActiveButton(DagButton):
    def render(self) -> RenderableType:
        if self.dag.get_is_active():
            label = Text("Active")
            label.stylize("bold black on green")
        else:
            label = Text("Paused")
            label.stylize("bold black on red")

        return Panel(label)


class DagGridView(GridView):
    async def on_mount(self) -> None:
        """Event when widget is first mounted (added to a parent view)."""
        dagbag = DagBag()

        # Make all the buttons
        self.dag_buttons = {
            dag_id: DagButton(dag) for dag_id, dag in dagbag.dags.items()
        }
        self.active_buttons = {
            dag_id: DagActiveButton(dag) for dag_id, dag in dagbag.dags.items()
        }

        # Set basic grid settings
        self.grid.set_align("center", "center")

        # Create rows / columns / areas
        self.grid.add_column("active")
        self.grid.add_column("dag")
        self.grid.add_column("owner")
        self.grid.add_column("runs")
        self.grid.add_column("schedule")
        self.grid.add_row("row", repeat=len(self.dag_buttons))

        # Place out widgets in to the layout
        rows = []
        for dag_id, dag in dagbag.dags.items():
            rows.append(self.active_buttons[dag_id])
            rows.append(self.dag_buttons[dag_id])
            rows.append(Button(dag.owner))
            rows.append(Button(""))
            rows.append(
                Button(
                    str(dag.schedule_interval)
                    if dag.schedule_interval is not None
                    else "None"
                )
            )

        self.grid.place(*rows)


class Tab(Button):
    active = Reactive(False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._size = 3

    def render(self) -> RenderableType:
        return Align.center(
            self.label,
            vertical="middle",
            style="white on red" if self.active else "black on white",
        )


class DagTabbedView(GridView):
    def __init__(self, tabs: list[str], *args, **kwargs):
        self.tabs = tabs
        self.current_dag = None
        super().__init__(*args, **kwargs)

    async def on_mount(self) -> None:
        """Event when widget is first mounted (added to a parent view)."""
        dagbag = DagBag()

        # Create rows / columns / areas
        for tab in self.tabs:
            self.grid.add_column(tab)

        self.grid.add_row("tabs", size=3)
        self.grid.add_row("content", size=99)

        areas = {tab: f"{tab},tabs" for tab in self.tabs}
        areas["content"] = f"{self.tabs[0]}-start|{self.tabs[-1]}-end,content"
        self.grid.add_areas(**areas)

        self.tab_widgets = {tab: Tab(tab) for tab in self.tabs}

        self.content = ScrollView()
        self.tab_widgets["content"] = self.content

        self.grid.place(**self.tab_widgets)

    async def press_tab(self, tab_name: str):
        await self.handle_tab_pressed(self.tab_widgets[tab_name])

    async def handle_button_pressed(self, message: ButtonPressed) -> None:
        assert isinstance(message.sender, Button)
        button = message.sender
        await self.handle_tab_pressed(button)

    async def handle_tab_pressed(self, tab: Tab):
        if tab.name not in self.tabs:
            return

        for name, widget in self.tab_widgets.items():
            if name == tab.name:
                widget.active = True
            else:
                widget.active = False
        self.layout.require_update()

        if tab.name == "code":
            content = Syntax.from_path(self.current_dag.fileloc)
        elif tab.name == "tree":
            root = Tree(self.current_dag.dag_id)

            tree_dict = {}
            for task in self.current_dag.topological_sort():
                if len(task.upstream_task_ids) == 0:
                    tree_dict[task.task_id] = root.add(task.task_id)
                else:
                    for upstream_task in task.upstream_task_ids:
                        tree_dict[task.task_id] = tree_dict[upstream_task].add(
                            task.task_id
                        )

            content = root
        elif tab.name == "graph":
            content = ""

        await self.content.update(content)


class AirflowTUI(App):
    async def on_load(self) -> None:
        await self.bind("q", "quit", "Quit")
        await self.bind("b", "back", "Back")

    async def on_mount(self) -> None:
        await self.view.dock(Header(), edge="top")
        await self.view.dock(Footer(), edge="bottom")

        self.grid_view = DagGridView()
        await self.view.dock(self.grid_view, name="dag_grid")

        self.tabbed_view = DagTabbedView(["tree", "graph", "code"])
        await self.view.dock(self.tabbed_view, name="dag_tabbed")

    async def action_back(self) -> None:
        await self.view.action_toggle("dag_grid")

    async def handle_button_pressed(self, message: ButtonPressed) -> None:
        """A message sent by the button widget"""

        assert isinstance(message.sender, Button)
        button = message.sender

        if isinstance(button, DagActiveButton):
            pass
        elif getattr(button, "dag", None) is not None:
            self.tabbed_view.current_dag = button.dag
            await self.tabbed_view.press_tab("code")
            await self.view.action_toggle("dag_grid")


def main():
    AirflowTUI.run(title="Airflow TUI", log="airflow_tui.log")


if __name__ == "__main__":
    sys.exit(main())
