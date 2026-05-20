from pathlib import Path

from zoteropdf2md.marker_runner import MarkerRunner, ProgressContext, RunResult


class _CapturingMarkerRunner(MarkerRunner):
    def __init__(self) -> None:
        super().__init__(marker_cmd="marker", marker_single_cmd="marker_single")
        self.commands: list[list[str]] = []

    def _run(self, command, env, log, progress=None):  # type: ignore[override]
        self.commands.append(command)
        assert progress is None or isinstance(progress, ProgressContext)
        return RunResult(command=command, exit_code=0)


def test_marker_runner_uses_300dpi_for_batch_and_single() -> None:
    runner = _CapturingMarkerRunner()

    runner.run_batch(
        input_dir=Path("in"),
        output_dir=Path("out"),
        skip_existing=False,
        disable_multiprocessing=False,
        output_format="html",
        env={},
        log=lambda _line: None,
    )
    runner.run_single(
        pdf_path=Path("in") / "paper.pdf",
        output_dir=Path("out"),
        output_format="html",
        env={},
        log=lambda _line: None,
    )

    for command in runner.commands:
        assert command[command.index("--lowres_image_dpi") + 1] == "300"
        assert command[command.index("--highres_image_dpi") + 1] == "300"
