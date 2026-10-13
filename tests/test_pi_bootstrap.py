"""Exercise Pi's no-TTY bootstrap command without downloading vendor code."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'hydra_heads/scripts/update-agents.sh'


class PiBootstrapTests(unittest.TestCase):
    def test_python_fallback_executes_shell_without_controlling_tty(self):
        text = SCRIPT.read_text()
        function = text[text.index('install_command_for() {'):text.index('# ── Shell startup file protection')]
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as directory:
            home = Path(directory)
            (home / 'python').symlink_to(__import__('sys').executable)
            (home / 'sh').symlink_to('/bin/sh')
            # Force the macOS branch by exposing Python and sh but no setsid.
            selection = subprocess.run(['/bin/bash', '-c', 'unset BASH_ENV; PATH="$TEST_PATH"; ' + function + '\ninstall_command_for pi'],
                                       env=dict(os.environ, TEST_PATH=str(home), BASH_ENV='/dev/null'), text=True,
                                       capture_output=True, check=True).stdout.strip()
            self.assertIn('os.setsid()', selection)
            payload = 'test ! -t 0 && printf "NO_TTY_OK\\n"\n'
            command = selection.split(' | ', 1)[1]
            result = subprocess.run(['/bin/bash', '-c', command], input=payload,
                                    env=dict(os.environ, PATH=str(home)), text=True,
                                    capture_output=True, check=True)
            self.assertEqual(result.stdout, 'NO_TTY_OK\n')

    def test_linux_retains_native_setsid(self):
        text = SCRIPT.read_text()
        function = text[text.index('install_command_for() {'):text.index('# ── Shell startup file protection')]
        result = subprocess.run(['/bin/bash', '-c', function + '\ninstall_command_for pi'],
                                text=True, capture_output=True, check=True)
        self.assertIn('| setsid sh', result.stdout)


if __name__ == '__main__':
    unittest.main()
