import os
import subprocess
import time
from pathlib import Path
from time import sleep
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import copier
import pytest
from bec_lib.utils.plugin_manager import main
from bec_lib.utils.plugin_manager._util import _goto_dir
from typer.testing import CliRunner

from bec_widgets.utils.bec_plugin_manager.create.widget import _commit_added_widget, _widget_exists

PLUGIN_REPO = "https://github.com/bec-project/plugin_copier_template.git"

REPLACEMENT_UI_CONTENTS = """<?xml version="1.0" encoding="UTF-8"?>
<ui version="4.0">
 <class>testWidget6</class>
 <widget class="QWidget" name="testWidget6">
  <property name="geometry">
   <rect>
    <x>0</x>
    <y>0</y>
    <width>539</width>
    <height>287</height>
   </rect>
  </property>
  <widget class="Waveform" name="waveform">
   <property name="geometry">
    <rect>
     <x>30</x>
     <y>0</y>
     <width>361</width>
     <height>125</height>
    </rect>
   </property>
  </widget>
 </widget>
 <customwidgets>
  <customwidget>
   <class>Waveform</class>
   <extends>QWidget</extends>
   <header>waveform</header>
  </customwidget>
 </customwidgets>
 <resources/>
 <connections/>
</ui>
"""


@pytest.fixture
def runner():
    return CliRunner()


def test_app_has_widget_commands(runner: CliRunner):
    result = runner.invoke(main._app, ["create", "--help"])
    assert "widget" in result.output


def test_create_widget_takes_name(runner: CliRunner):
    result = runner.invoke(main._app, ["create", "widget"])
    assert "Missing argument 'NAME'." in result.output


@patch("bec_widgets.utils.bec_plugin_manager.create.widget.logger")
@patch("bec_widgets.utils.bec_plugin_manager.create.widget.make_commit")
@patch("bec_widgets.utils.bec_plugin_manager.create.widget.git_stage_files")
def test_make_commit(stage: MagicMock, commit: MagicMock, logger: MagicMock):
    repo = Path("test_path")
    _commit_added_widget(repo, "test")
    assert stage.call_count == 2
    stage.assert_has_calls(
        [
            call(repo, [".copier-answers.yml"]),
            call(repo / repo.name / "bec_widgets" / "widgets" / "test", []),
        ]
    )
    commit.assert_called_with(repo, "plugin-manager added new widget: test")
    logger.info.assert_called_with("Committing new widget test")


def test_widget_exists_function():
    assert not _widget_exists([], "test_widget")
    assert _widget_exists([{"name": "test_widget", "use_ui": True}], "test_widget")


def test_editor_cb(runner):
    result = runner.invoke(main._app, ["create", "widget", "test", "--no-use-ui", "--open-editor"])
    assert result.exit_code == 2
    assert "Invalid value" in result.output
    assert "Can only open" in result.output


class TestAddWidgetVariants:
    @pytest.fixture(scope="class", autouse=True)
    def setup_env(self, tmp_path_factory: pytest.TempPathFactory):
        TestAddWidgetVariants._tmp_plugin_dir = tmp_path_factory.mktemp("test_plugin")

    @pytest.fixture(scope="function", autouse=True)
    def cleanup_repo(self):
        yield
        subprocess.run(["git", "reset", "--hard"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    @pytest.fixture(scope="class")
    def git_repo(self):
        project = TestAddWidgetVariants._tmp_plugin_dir / "test_plugin"
        with _goto_dir(TestAddWidgetVariants._tmp_plugin_dir):
            subprocess.run(["git", "clone", PLUGIN_REPO])
        os.makedirs(project)
        with _goto_dir(project):
            subprocess.run(["git", "init", "-b", "main"])
            subprocess.run(["git", "config", "user.email", "test"])
            subprocess.run(["git", "config", "user.name", "test"])
            copier.run_copy(
                str(TestAddWidgetVariants._tmp_plugin_dir / "plugin_copier_template"),
                str(project),
                defaults=True,
                data={
                    "project_name": "test_plugin",
                    "widget_plugins_input": [{"name": "test_widget", "use_ui": True}],
                },
                unsafe=True,
            )
            yield project

    @patch("bec_widgets.utils.bec_plugin_manager.create.widget.plugin_repo_path")
    def test_add_widget_with_ui(self, plugin_repo_path, runner: CliRunner, git_repo: Path):
        plugin_repo_path.return_value = str(git_repo)
        result = runner.invoke(
            main._app, ["create", "widget", "test_widget_2", "--use-ui", "--no-open-editor"]
        )
        assert result.exit_code == 0, result.output
        widget_dir = git_repo / "test_plugin" / "bec_widgets" / "widgets" / "test_widget_2"
        assert os.path.isdir(widget_dir)
        assert os.path.isfile(widget_dir / "test_widget_2.py")
        assert os.path.isfile(widget_dir / "test_widget_2.ui")
        assert os.path.isfile(widget_dir / "test_widget_2_ui.py")

    @patch("bec_widgets.utils.bec_plugin_manager.create.widget.plugin_repo_path")
    def test_add_widget_without_ui(self, plugin_repo_path, runner: CliRunner, git_repo: Path):
        plugin_repo_path.return_value = str(git_repo)
        result = runner.invoke(
            main._app, ["create", "widget", "test_widget_3", "--no-use-ui", "--no-open-editor"]
        )
        assert result.exit_code == 0, result.output
        widget_dir = git_repo / "test_plugin" / "bec_widgets" / "widgets" / "test_widget_3"
        assert os.path.isdir(widget_dir)
        assert os.path.isfile(widget_dir / "test_widget_3.py")
        assert not os.path.isfile(widget_dir / "test_widget_3.ui")
        assert not os.path.isfile(widget_dir / "test_widget_3_ui.py")

    @patch("bec_widgets.utils.bec_plugin_manager.create.widget.logger")
    @patch("bec_widgets.utils.bec_plugin_manager.create.widget.plugin_repo_path")
    def test_no_add_widget_dupe_name(
        self, plugin_repo_path, logger, runner: CliRunner, git_repo: Path
    ):
        plugin_repo_path.return_value = str(git_repo)
        result = runner.invoke(
            main._app, ["create", "widget", "test_widget", "--no-use-ui", "--no-open-editor"]
        )
        assert result.exit_code == -1, result.output
        assert "already exists!" in logger.error.mock_calls[0].args[0]

    @patch("bec_widgets.utils.bec_plugin_manager.create.widget.logger")
    @patch("bec_widgets.utils.bec_plugin_manager.create.widget.plugin_repo_path")
    def test_no_add_widget_bad_name(
        self, plugin_repo_path, logger, runner: CliRunner, git_repo: Path
    ):
        plugin_repo_path.return_value = str(git_repo)
        result = runner.invoke(
            main._app, ["create", "widget", "12345", "--no-use-ui", "--no-open-editor"]
        )
        assert result.exit_code == -1, result.output
        assert "not a valid name for a widget" in logger.error.mock_calls[0].args[0]

    @patch("bec_widgets.utils.bec_plugin_manager.create.widget.copier")
    @patch("bec_widgets.utils.bec_plugin_manager.create.widget.logger")
    @patch("bec_widgets.utils.bec_plugin_manager.create.widget.plugin_repo_path")
    def test_copier_error_logged(
        self, plugin_repo_path, logger, copier, runner: CliRunner, git_repo: Path
    ):
        class CopierFailure(Exception): ...

        copier.run_update.side_effect = CopierFailure
        plugin_repo_path.return_value = str(git_repo)
        result = runner.invoke(
            main._app, ["create", "widget", "test_widget_4", "--no-use-ui", "--no-open-editor"]
        )
        assert result.exit_code == -1, result.output
        assert "CopierFailure" in logger.error.mock_calls[0].args[0]

    @patch("bec_widgets.utils.bec_plugin_manager.create.widget.open_and_watch_ui_editor")
    @patch("bec_widgets.utils.bec_plugin_manager.create.widget.plugin_repo_path")
    def test_editor_opened_on_success(
        self, plugin_repo_path, open_editor, runner: CliRunner, git_repo: Path
    ):
        plugin_repo_path.return_value = str(git_repo)
        runner.invoke(main._app, ["create", "widget", "TeSt_wiDgeT_5", "--use-ui", "--open-editor"])
        open_editor.assert_called_with("test_widget_5")

    @patch("bec_widgets.utils.bec_plugin_manager.edit_ui.logger")
    @patch("bec_widgets.utils.bec_plugin_manager.edit_ui.open_designer")
    @patch("bec_widgets.utils.bec_plugin_manager.edit_ui.plugin_repo_path")
    @patch("bec_widgets.utils.bec_plugin_manager.create.widget.plugin_repo_path")
    def test_widget_editor_watcher(
        self,
        plugin_repo_path,
        plugin_repo_path_2,
        open_designer,
        logger: MagicMock,
        runner: CliRunner,
        git_repo: Path,
    ):
        plugin_repo_path.return_value = str(git_repo)
        plugin_repo_path_2.return_value = str(git_repo)

        widget_dir = git_repo / "test_plugin" / "bec_widgets" / "widgets" / "test_widget_6"
        widget_ui_file = widget_dir / "test_widget_6.ui"
        compiled_widget_ui_file = widget_dir / "test_widget_6_ui.py"

        test_collector = SimpleNamespace()

        def test_function(args: list[str]):
            test_collector.ui_file = args[0]
            with open(compiled_widget_ui_file) as f:
                test_collector.initial_compiled_ui_contents = f.read()
            with open(args[0], "w") as f:
                f.write(REPLACEMENT_UI_CONTENTS)
            start = time.monotonic()
            while call("done!") not in logger.success.call_args_list:
                time.sleep(0.05)
                if time.monotonic() - start > 5:
                    raise TimeoutError("Waiting for recompilation timed out.")
            with open(compiled_widget_ui_file) as f:
                test_collector.final_compiled_ui_contents = f.read()

        open_designer.side_effect = test_function
        result = runner.invoke(
            main._app, ["create", "widget", "test_widget_6", "--use-ui", "--open-editor"]
        )

        assert result.exit_code == 0, result.output
        assert test_collector.ui_file == str(widget_ui_file)
        assert (
            test_collector.initial_compiled_ui_contents != test_collector.final_compiled_ui_contents
        )
        assert "" in test_collector.final_compiled_ui_contents
