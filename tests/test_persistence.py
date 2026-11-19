"""存档路径解析：打包后必须写到 exe 同级目录，而不是临时解包目录。

PyInstaller ``--onefile`` 下 ``__file__`` 指向会被清理的 ``_MEIPASS``，
所以 ``_data_dir()`` 必须在冻结状态下改用 ``sys.executable`` 所在目录，
否则打包版的 ``progress.json`` / ``hiscore.txt`` 会随程序退出一起消失。
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src import game


class DataDirTest(unittest.TestCase):
    def test_source_mode_uses_repo_root(self) -> None:
        with patch.object(sys, "frozen", False, create=True):
            self.assertEqual(
                game._data_dir(),
                Path(game.__file__).resolve().parent.parent,
            )

    def test_frozen_mode_uses_executable_dir(self) -> None:
        fake_exe = r"C:\somewhere\th06-scarlet-mist.exe"
        with patch.object(sys, "frozen", True, create=True), \
             patch.object(sys, "executable", fake_exe):
            self.assertEqual(game._data_dir(), Path(fake_exe).resolve().parent)

    def test_save_paths_are_built_from_the_data_dir(self) -> None:
        from src import config

        with patch.object(sys, "frozen", True, create=True), \
             patch.object(sys, "executable", r"C:\app\game.exe"):
            base = Path(r"C:\app").resolve()
            self.assertEqual(game._hiscore_path(), base / config.HISCORE_FILE)
            self.assertEqual(game._progress_path(), base / config.PROGRESS_FILE)

    def test_campaign_progress_round_trips_through_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "progress.json"
            with patch.object(game, "_progress_path", return_value=path):
                game._save_progress(3, True)

                self.assertEqual(
                    game._load_progress(),
                    {"unlocked": 3, "all_cleared": True},
                )


if __name__ == "__main__":
    unittest.main()
