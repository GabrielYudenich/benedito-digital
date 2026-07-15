import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from gui.screens.editor_screen import EditorScreen


class FakeTree:
    def __init__(self):
        self.items = {}
        self.children = {"": []}
        self.next_id = 1
        self.focused = ""

    def insert(self, parent, _position, **options):
        item = f"item-{self.next_id}"
        self.next_id += 1
        self.items[item] = {"parent": parent, **options}
        self.children.setdefault(parent, []).append(item)
        self.children.setdefault(item, [])
        return item

    def get_children(self, item=""):
        return tuple(self.children.get(item, []))

    def delete(self, item):
        for child in list(self.children.get(item, [])):
            self.delete(child)
        parent = self.items.get(item, {}).get("parent")
        if parent in self.children and item in self.children[parent]:
            self.children[parent].remove(item)
        self.children.pop(item, None)
        self.items.pop(item, None)

    def focus(self):
        return self.focused


class FakeStatus:
    def set(self, _value):
        return None


class FakeLogger:
    def exception(self, message):
        raise AssertionError(message)


def test_media_tree_groups_sources_and_loads_frame_pages_lazily(tmp_path):
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    for number in range(1, 206):
        (frames_dir / f"frame_{number:06d}.png").write_bytes(b"frame")

    tree = FakeTree()
    screen = SimpleNamespace(
        project_manager=SimpleNamespace(
            get_project_videos=lambda: ["rolo-1.mov"],
            get_frames_dir=lambda _video: str(frames_dir),
        ),
        workspace=SimpleNamespace(get_proxy_path=lambda _video: None),
        media_tree=tree,
        _media_tree_items={},
        _media_video_items={},
        logger=FakeLogger(),
        status_var=FakeStatus(),
    )

    EditorScreen.load_project_videos(screen)

    video_item = tree.get_children("")[0]
    proxy_item, frames_item = tree.get_children(video_item)
    page_items = tree.get_children(frames_item)
    assert screen._media_tree_items[video_item]["kind"] == "video"
    assert screen._media_tree_items[proxy_item]["kind"] == "proxy"
    assert len(page_items) == 3
    assert len(tree.get_children(page_items[0])) == 1

    tree.focused = page_items[0]
    EditorScreen._on_media_tree_open(screen)

    assert len(tree.get_children(page_items[0])) == 100
    first_frame = tree.get_children(page_items[0])[0]
    assert screen._media_tree_items[first_frame]["filename"] == "frame_000001.png"
