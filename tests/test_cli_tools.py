import importlib.util
import plistlib
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git_runner(*args, **kwargs):
    return subprocess.CompletedProcess(args[0], 0, "true\n", "")


def test_write_env_quotes_values_and_uses_defaults(tmp_path):
    setup = load_script("setup")
    repo = tmp_path / 'repo with "quotes"'
    repo.mkdir()
    destination = tmp_path / ".env"

    setup.write_env(repo, destination, auto_push=False)

    text = destination.read_text()
    assert f'REPO_PATH="{repo.resolve()!s}'.replace('"quotes"', r'\"quotes\"') in text
    assert "AUTO_COMMIT=true" in text
    assert "AUTO_PUSH=false" in text
    assert "FULL_SYNC_INTERVAL=3600" in text


def test_setup_rejects_existing_or_invalid_repository(tmp_path):
    setup = load_script("setup")
    output = tmp_path / ".env"
    output.write_text("existing")
    with pytest.raises(FileExistsError):
        setup.write_env(tmp_path, output, auto_push=True)
    with pytest.raises(ValueError, match="existing directory"):
        setup.validate_repository(tmp_path / "missing", git_runner=git_runner)
    with pytest.raises(ValueError, match="Git work tree"):
        setup.validate_repository(tmp_path, git_runner=Mock(return_value=subprocess.CompletedProcess([], 1, "", "")))


def test_setup_main_returns_one_when_repository_check_times_out(tmp_path):
    setup = load_script("setup")
    output = []
    timeout = subprocess.TimeoutExpired(["git"], 30)
    assert setup.main(input_fn=Mock(return_value=str(tmp_path)), output_fn=output.append, git_runner=Mock(side_effect=timeout), project_dir=tmp_path) == 1
    assert output == ["Repository validation failed"]


def test_write_env_never_replaces_a_file_created_after_preflight(tmp_path, monkeypatch):
    setup = load_script("setup")
    destination = tmp_path / ".env"
    monkeypatch.setattr(Path, "exists", lambda path: False if path == destination else path.stat() is not None)
    destination.write_text("newer")
    with pytest.raises(FileExistsError):
        setup.write_env(tmp_path, destination, auto_push=True)
    assert destination.read_text() == "newer"


def test_setup_main_is_interactive_without_overwriting(tmp_path):
    setup = load_script("setup")
    repo = tmp_path / "repo"
    repo.mkdir()
    output = []
    assert setup.main(input_fn=Mock(side_effect=[str(repo), "n"]), output_fn=output.append, git_runner=git_runner, project_dir=tmp_path) == 0
    assert (tmp_path / ".env").exists()
    assert any("python" in message and "main.py" in message for message in output)
    assert "'$'" not in output[-1]
    assert setup.main(input_fn=Mock(), output_fn=output.append, git_runner=git_runner, project_dir=tmp_path) == 1


def test_setup_main_shell_quotes_a_special_project_path(tmp_path):
    setup = load_script("setup")
    project = tmp_path / "project $ space"
    project.mkdir()
    output = []
    assert setup.main(input_fn=Mock(side_effect=[str(tmp_path), "n"]), output_fn=output.append, git_runner=git_runner, project_dir=project) == 0
    assert "'" in output[-1] and "$" in output[-1]


def test_render_and_write_launchd_preview_stay_in_project(tmp_path):
    launchd = load_script("generate_launchd")
    project = tmp_path / "project"
    python_path = tmp_path / "venv" / "bin" / "python"
    payload = plistlib.loads(launchd.render_plist(project, python_path).encode())
    assert payload["ProgramArguments"] == [str(python_path.resolve()), str((project / "main.py").resolve())]
    assert payload["WorkingDirectory"] == str(project.resolve())
    assert payload["RunAtLoad"] is True and payload["KeepAlive"] is True
    assert payload["StandardOutPath"] == str((project / "logs" / "launchd.out.log").resolve())
    assert "/Users/username" not in launchd.render_plist(project, python_path)
    output = project / "build" / "agent.plist"
    assert launchd.write_plist(output, project, python_path) == output
    assert output.exists() and (project / "logs").is_dir()
