from pathlib import Path

from django.test import SimpleTestCase


class NoMergeConflictMarkersTests(SimpleTestCase):
    def test_no_conflict_markers_in_core_python_files(self):
        root = Path(__file__).resolve().parents[2]
        markers = ('<<<<<<< ', '=======', '>>>>>>> ')
        offenders = []
        for path in (root / 'core').rglob('*.py'):
            text = path.read_text(encoding='utf-8')
            if any(marker in text for marker in markers):
                offenders.append(path.relative_to(root).as_posix())
        self.assertEqual(offenders, [], f'Arquivos com marcador de conflito: {offenders}')
