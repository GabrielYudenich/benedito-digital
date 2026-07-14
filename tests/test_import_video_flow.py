import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from gui.screens import editor_screen
from gui.screens.editor_screen import EditorScreen
from gui.dialogs.import_video_dialog import ImportModeDialog
from core.media_import import build_import_selection


class FakeButton:
    def __init__(self):
        self.states = []

    def config(self, **options):
        self.states.append(options)

    def focus_set(self):
        return None


class FakePanel(FakeButton):
    def __init__(self, manager=""):
        super().__init__()
        self.manager = manager

    def winfo_manager(self):
        return self.manager

    def pack(self, **_options):
        self.manager = "pack"

    def pack_forget(self):
        self.manager = ""


class FakeWindow:
    def after_idle(self, _callback):
        return None


class FakeScrollCanvas:
    def __init__(self, height):
        self.height = height
        self.scrolls = []

    def winfo_height(self):
        return self.height

    def yview_scroll(self, units, kind):
        self.scrolls.append((units, kind))


class FakeBodyContent:
    def __init__(self, required_height):
        self.required_height = required_height

    def winfo_reqheight(self):
        return self.required_height


class FakeInputWidget:
    def __init__(self, widget_class):
        self.widget_class = widget_class

    def winfo_class(self):
        return self.widget_class


class FakeVariable:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


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
    selection = build_import_selection(
        "segment", start_value="00:01:00", end_value="00:02:00"
    )
    choices[0][2](selection)
    assert analysis_calls == [(str(source), selection)]


def test_confirmed_mode_is_analyzed_then_forwarded_to_review(monkeypatch, tmp_path):
    source = tmp_path / "filme.mov"
    source.write_bytes(b"movie")
    jobs = []
    reviews = []
    import_button = FakeButton()
    audio_calls = []

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
            },
            analyze_audio_balance=lambda path, start, duration: (
                audio_calls.append((path, start, duration))
                or {
                    "suggested_mode": "dual_mono_right",
                    "summary": "Canal esquerdo sem sinal.",
                    "rms_db": [float("-inf"), -20.0],
                }
            ),
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

    selection = build_import_selection(
        "segment", start_value="00:00:10", end_value="00:00:20"
    )
    EditorScreen._analyze_video_for_import(screen, str(source), selection)

    assert import_button.states[-1]["state"] == editor_screen.tk.DISABLED
    assert jobs[0][0] == "Analisando mídia"
    context = FakeJobContext()
    video_info = jobs[0][1](context)
    assert context.reports[0][0] == 10
    assert context.reports[-1] == (100, "Análise concluída")

    jobs[0][2](video_info)

    assert reviews[0][1] == str(source)
    assert reviews[0][4] == selection
    assert reviews[0][2]["duration"] == 42.0
    assert reviews[0][2]["audio_analysis"]["suggested_mode"] == "dual_mono_right"
    assert audio_calls == [(str(source), 10.0, 10.0)]


def test_segment_selection_has_explicit_visual_confirmation():
    dialog = object.__new__(ImportModeDialog)
    dialog.mode_var = FakeVariable("segment")
    dialog.selection_status_var = FakeVariable()
    dialog.full_radio = FakeButton()
    dialog.segment_radio = FakeButton()
    dialog.confirm_button = FakeButton()
    dialog.selection_status_label = FakeButton()
    dialog.start_var = FakeVariable("00:01:00")
    dialog.end_var = FakeVariable("00:02:00")
    dialog.interval_panel = FakePanel()
    dialog.selection_panel = FakePanel("pack")
    dialog.window = FakeWindow()

    dialog._refresh_selection()

    assert "SELECIONADO" in dialog.segment_radio.states[-1]["text"]
    assert "✓" in dialog.segment_radio.states[-1]["text"]
    assert "Trecho definido" in dialog.selection_status_var.get()
    assert dialog.confirm_button.states[-1]["text"] == "OK — analisar e revisar trecho"
    assert dialog.confirm_button.states[-1]["state"] == editor_screen.tk.NORMAL
    assert dialog.interval_panel.winfo_manager() == "pack"


def test_segment_selection_requires_end_time_before_analysis():
    dialog = object.__new__(ImportModeDialog)
    dialog.mode_var = FakeVariable("segment")
    dialog.selection_status_var = FakeVariable()
    dialog.full_radio = FakeButton()
    dialog.segment_radio = FakeButton()
    dialog.confirm_button = FakeButton()
    dialog.selection_status_label = FakeButton()
    dialog.start_var = FakeVariable("00:01:00")
    dialog.end_var = FakeVariable("")
    dialog.interval_panel = FakePanel()
    dialog.selection_panel = FakePanel("pack")
    dialog.window = FakeWindow()

    dialog._refresh_selection()

    assert dialog.confirm_button.states[-1]["state"] == editor_screen.tk.DISABLED
    assert "Informe um intervalo válido" in dialog.selection_status_var.get()


def test_import_choice_consumes_wheel_without_scrolling_background():
    dialog = object.__new__(ImportModeDialog)
    dialog.body_canvas = FakeScrollCanvas(height=300)
    dialog.body_content = FakeBodyContent(required_height=500)
    event = SimpleNamespace(delta=-120, num=0)

    assert dialog._scroll_selection_body(event) == "break"
    assert dialog.body_canvas.scrolls == [(1, "units")]

    dialog.body_content.required_height = 200
    assert dialog._scroll_selection_body(event) == "break"
    assert dialog.body_canvas.scrolls == [(1, "units")]


def test_number_shortcuts_do_not_steal_time_entry_digits():
    dialog = object.__new__(ImportModeDialog)
    selected_modes = []
    dialog._select_mode = selected_modes.append

    entry_event = SimpleNamespace(widget=FakeInputWidget("TEntry"))
    assert dialog._mode_shortcut(entry_event, "full") is None
    assert selected_modes == []

    card_event = SimpleNamespace(widget=FakeInputWidget("Radiobutton"))
    assert dialog._mode_shortcut(card_event, "segment") == "break"
    assert selected_modes == ["segment"]
