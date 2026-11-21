import re
from pathlib import Path

from django.test import SimpleTestCase

# Marcadores reais do git ficam sempre no início da linha. Comentários
# decorativos como "# =====" não devem ser acusados.
CONFLICT_MARKER = re.compile(r'^(<{7} |={7}$|>{7} )', re.MULTILINE)


class NoMergeConflictMarkersTests(SimpleTestCase):
    def test_no_conflict_markers_in_core_files(self):
        root = Path(__file__).resolve().parents[2]
        offenders = []
        for pattern in ('*.py', '*.html', '*.css', '*.js'):
            for path in (root / 'core').rglob(pattern):
                text = path.read_text(encoding='utf-8')
                if CONFLICT_MARKER.search(text):
                    offenders.append(path.relative_to(root).as_posix())
        self.assertEqual(offenders, [], f'Arquivos com marcador de conflito: {offenders}')
