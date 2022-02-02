import sys

from rich.table import Table
from textual.app import App
from textual.widgets import ScrollView

from airflow.models import DagBag


class AirflowTUI(App):
    async def on_load(self) -> None:
        await self.bind("q", "quit")

    async def on_mount(self) -> None:
        self.body = body = ScrollView(auto_width=True)

        dagbag = DagBag()

        async def add_dags():
            table = Table(title="DAGs")

            table.add_column("DAG")

            for dag in dagbag.dags:
                table.add_row(*[dag])

            await body.update(table)

        await self.call_later(add_dags)


def main():
    AirflowTUI.run(title="Airflow TUI")


if __name__ == "__main__":
    sys.exit(main())
