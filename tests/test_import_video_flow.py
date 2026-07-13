import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from gui.screens import editor_screen
from gui.screens.editor_screen import EditorScreen


class FakeButton:
    def __init__(self):
        self.states = []

    def config(self, **options):
        self.states.append(options)


class FakeJobContext:
    cancellation_requested = False

    def __init__(self):
        self.reports = []

    def report(self, progress, message):
        self.reports.append((progress, message))

    def check_cancelled(self):
        return None


def test_import_asks_mode_before_starting_media_analysis(monkeypatch, tmp_path):
    source = tmp_path / "filme.mov"
    source.write_bytes(b"movie")
    choices = []
    analysis_calls = []
    screen = SimpleNamespace(
        root=object(),
        _analyze_video_for_import=lambda path, mode: analysis_calls.append((path, mode)),
    )

    monkeypatch.setattr(
        editor_screen.filedialog, "askopenfilename", lambda **_options: str(source)
    )
    monkeypatch.setattr(
        editor_screen,
        "ImportModeDialog",
        lambda parent, path, callback: choices.append((parent, path, callback)),
    )

    EditorScreen.import_video(screen)

    assert len(choices) == 1
    assert analysis_calls == []
    choices[0][2]("segment")
    assert analysis_calls == [(str(source), "segment")]


def test_confirmed_mode_is_analyzed_then_forwarded_to_review(monkeypatch, tmp_path):
    source = tmp_path / "filme.mov"
    source.write_bytes(b"movie")
    jobs = []
    reviews = []
    import_button = FakeButton()

    def start_job(*arguments):
        jobs.append(arguments)
        return object()

    screen = SimpleNamespace(
        root=object(),
        import_btn=import_button,
        video_processor=SimpleNamespace(
            get_video_info=lambda _path: {
                "duration": 42.0,
                "fps": 24.0,
                "width": 1920,
                "height": 1080,
            }
        ),
        project_manager=SimpleNamespace(get_originals_dir=lambda: str(tmp_path)),
        _start_ui_job=start_job,
        _start_video_import=lambda _plan: None,
    )
    monkeypatch.setattr(
        editor_screen,
        "ImportVideoDialog",
        lambda *arguments: reviews.append(arguments),
    )

    EditorScreen._analyze_video_for_import(screen, str(source), "segment")

    assert import_button.states[-1]["state"] == editor_screen.tk.DISABLED
    assert jobs[0][0] == "Analisando mídia"
    context = FakeJobContext()
    video_info = jobs[0][1](context)
    assert context.reports[0][0] == 10
    assert context.reports[-1] == (100, "Análise concluída")

    jobs[0][2](video_info)

    assert reviews[0][1] == str(source)
    assert reviews[0][4] == "segment"
    assert reviews[0][2]["duration"] == 42.0
