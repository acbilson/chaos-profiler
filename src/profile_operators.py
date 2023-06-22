import linecache
import tracemalloc
from dataclasses import dataclass
from tracemalloc import Snapshot, Statistic, StatisticDiff
from typing import Callable
from enum import Enum


class TraceKeyType(Enum):
    FILENAME = "filename"
    LINE_NUM = "lineno"
    TRACEBACK = "traceback"


@dataclass
class ProfileRunSettings:
    func: Callable
    func_file_names: list[str]
    run_count: int = 3
    key_type: TraceKeyType = TraceKeyType.LINE_NUM
    limit: int = 10
    exclusive_filter: bool = True


class StatisticRun:
    def __init__(self, position: int, statistic: Statistic) -> None:
        self.position = position + 1
        self.statistic = statistic

    def __str__(self) -> str:
        return (
            f"{self.file_trace}\n{self.line_trace}"
            if self.line_trace is not None
            else f"{self.file_trace}"
        )

    @property
    def file_trace(self) -> str:
        frame = self.statistic.traceback[0]
        return f"\t#{self.position}: {self.statistic.size / 1024}KiB -> {frame.filename}:{frame.lineno} (traces: {self.statistic.traceback.total_nframe})"

    @property
    def line_trace(self) -> str | None:
        frame = self.statistic.traceback[0]
        line = linecache.getline(frame.filename, frame.lineno).strip()
        return f"\t\t{line}" if line is not None else None


class StatisticDiffRun:
    def __init__(self, position: int, statistic: StatisticDiff) -> None:
        self.position = position + 1
        self.statistic = statistic

    def __str__(self) -> str:
        return (
            f"{self.file_trace}\n{self.line_trace}"
            if self.line_trace is not None
            else f"{self.file_trace}"
        )

    @property
    def file_trace(self) -> str:
        frame = self.statistic.traceback[0]
        return f"\t#{self.position}: {self.statistic.size_diff / 1024}KiB -> {frame.filename}:{frame.lineno} (traces: {self.statistic.traceback.total_nframe})"

    @property
    def line_trace(self) -> str | None:
        frame = self.statistic.traceback[0]
        line = linecache.getline(frame.filename, frame.lineno).strip()
        return f"\t\t{line}" if line is not None else None


class SnapshotRun:
    def __init__(
        self,
        iteration: int,
        snapshot: Snapshot,
        settings: ProfileRunSettings,
    ) -> None:
        self.iteration = iteration
        self.snapshot = snapshot
        self.settings = settings

    def __str__(self) -> str:
        title = (
            f"\n## Snapshot Run #{self.iteration}"
            if self.iteration != 0
            else "\n## Snapshot Before Run"
        )
        return "\n".join(
            [
                title,
                f"### Top {self.settings.limit} Memory Hogs:",
                "\n".join([str(stat) for stat in self.top_stats]),
                "\n### Summary:",
                f"\tTop Total Size: {self.top_stats_summary}",
                f"\tRemaining Total Size: {self.remaining_stats_summary}",
            ]
        )

    @property
    def __inclusive_filtered(self) -> Snapshot:
        return self.snapshot.filter_traces(
            (
                tracemalloc.Filter(False, tracemalloc.__file__),
                tracemalloc.Filter(False, "<frozen importlib._bootstrap>"),
                tracemalloc.Filter(False, "<unknown>"),
            )
        )

    @property
    def __exclusive_filtered(self) -> Snapshot:
        return self.snapshot.filter_traces(
            [
                tracemalloc.Filter(True, func_file_name)
                for func_file_name in self.settings.func_file_names
            ],
        )

    @property
    def filtered_snapshot(self) -> Snapshot:
        return (
            self.__exclusive_filtered
            if self.settings.exclusive_filter
            else self.__inclusive_filtered
        )

    @property
    def top_stats(self) -> list[StatisticRun]:
        return [
            StatisticRun(i, stat)
            for i, stat in enumerate(
                self.filtered_snapshot.statistics(self.settings.key_type.value)[
                    : self.settings.limit
                ]
            )
        ]

    @property
    def top_stats_summary(self) -> str:
        return self.__total_size_line(self.top_stats)

    @property
    def remaining_stats(self) -> list[StatisticRun]:
        return [
            StatisticRun(i, stat)
            for i, stat in enumerate(
                self.filtered_snapshot.statistics(self.settings.key_type.value)[
                    self.settings.limit :
                ]
            )
        ]

    @property
    def remaining_stats_summary(self) -> str:
        return self.__total_size_line(self.remaining_stats)

    def __total_size_line(self, stats: list[StatisticRun]) -> str:
        summary_line = ""
        if stats is not None and len(stats) > 0:
            total_size = sum(stat.statistic.size for stat in stats)
            summary_line = f"{total_size / 1024} KiB"
        return summary_line


class SnapshotDiffRun:
    def __init__(
        self,
        iterations: tuple[int, int],
        diff: list[StatisticDiff],
        limit=10,
    ) -> None:
        self.iterations = iterations
        self.diff = diff
        self.limit = limit

    def __str__(self) -> str:
        title = f"\n## Snapshot Comparison between #{self.iterations[0]} and #{self.iterations[1]}"
        return "\n".join(
            [
                title,
                f"### Top {self.limit} Memory Hogs:",
                "\n".join([str(stat) for stat in self.top_stats]),
                "\n### Summary:",
                f"\tTop Total Size: {self.top_stats_summary}",
                f"\tRemaining Total Size: {self.remaining_stats_summary}",
            ]
        )

    @property
    def top_stats(self) -> list[StatisticDiffRun]:
        return [
            StatisticDiffRun(i, stat) for i, stat in enumerate(self.diff[: self.limit])
        ]

    @property
    def top_stats_summary(self) -> str:
        return self.__total_size_line(self.top_stats)

    @property
    def remaining_stats(self) -> list[StatisticDiffRun]:
        return [
            StatisticDiffRun(i, stat) for i, stat in enumerate(self.diff[self.limit :])
        ]

    @property
    def remaining_stats_summary(self) -> str:
        return self.__total_size_line(self.remaining_stats)

    def __total_size_line(self, stats: list[StatisticDiffRun]) -> str:
        summary_line = ""
        if stats is not None and len(stats) > 0:
            total_size = sum(stat.statistic.size_diff for stat in stats)
            summary_line = f"{total_size / 1024} KiB"
        return summary_line


class ProfileRun:
    def __init__(
        self,
        snapshot_runs: list[SnapshotRun],
        func_file_names: list[str],
        func_name: str,
    ) -> None:
        self.snapshot_runs = snapshot_runs
        self.func_file_names = func_file_names
        self.func_name = func_name

    def __compare(self, first: SnapshotRun, second: SnapshotRun) -> SnapshotDiffRun:
        return SnapshotDiffRun(
            iterations=(first.iteration, second.iteration),
            diff=first.filtered_snapshot.compare_to(
                second.filtered_snapshot, first.settings.key_type.value
            ),
        )

    @property
    def comparisons(self) -> list[SnapshotDiffRun]:
        comparisons: list[SnapshotDiffRun] = []
        for i, _ in enumerate(self.snapshot_runs):
            if i != 0:
                comparisons.append(
                    self.__compare(self.snapshot_runs[i - 1], self.snapshot_runs[i])
                )
        return comparisons

    def __str__(self) -> str:
        settings = self.snapshot_runs[0].settings
        return "\n".join(
            [
                f"# Profile Run For {self.func_name}",
                "```",
                "SETTINGS\n",
                f"- Memory Limit: {settings.limit}",
                f"- Key Type: {settings.key_type.name}",
                f"- Exclusive Filter Set: {settings.exclusive_filter}",
                f"- File Filters Applied: {settings.func_file_names}"
                if settings.exclusive_filter
                else "",
                "```",
                "\n".join([str(snapshot_run) for snapshot_run in self.snapshot_runs]),
                f"# Profile Comparisons For {self.func_name}",
                "\n".join([str(snapshot_run) for snapshot_run in self.snapshot_runs]),
                f"\n# Profile Comparisons For {self.func_name}",
                "\n".join([str(comparison) for comparison in self.comparisons]),
            ]
        )


def profile_func(settings: ProfileRunSettings) -> ProfileRun:
    tracemalloc.start()
    initial_snapshot = SnapshotRun(0, tracemalloc.take_snapshot(), settings)
    snapshot_runs: list[SnapshotRun] = [initial_snapshot]

    for i in range(1, settings.run_count + 1):
        settings.func()
        snapshot_runs.append(SnapshotRun(i, tracemalloc.take_snapshot(), settings))

    tracemalloc.stop()
    return ProfileRun(snapshot_runs, settings.func_file_names, str(settings.func))
