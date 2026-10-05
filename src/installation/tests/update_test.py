#!/usr/bin/env python3
"""Check update scope, ownership, and component preservation in temporary homes."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[3]


def main() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        home = Path(temporary)
        mock_bin = home / 'mock-bin'
        mock_bin.mkdir()
        sudo = mock_bin / 'sudo'
        sudo.write_text('#!/bin/sh\necho "Unexpected sudo request" >&2\nexit 99\n')
        sudo.chmod(0o755)
        environment = dict(os.environ, HOME=str(home), PYTHONDONTWRITEBYTECODE='1',
                           PATH=f"{mock_bin}:{os.environ['PATH']}")
        environment.pop('SHELL_SCRIPTS_INSTALL_ROOT', None)

        def run(script: str, *args: str, success: bool = True) -> str:
            result = subprocess.run([str(REPOSITORY / script), *args], env=environment,
                                    capture_output=True, text=True)
            assert (result.returncode == 0) == success, result.stdout + result.stderr
            return result.stdout + result.stderr

        run('setup.sh', '--component', 'system:amd-gaming', '--module', 'termlay', '--no-configure')
        registry = home / '.local/state/shell-scripts/registry.json'
        installed = home / '.local/bin'
        # Explicit user selections must not request system-registry privileges.
        output = run('update.sh', '--module', 'system', '--module', 'termlay')
        assert 'Updated system:' in output and 'Updated termlay:' in output
        state = json.loads(registry.read_text())
        assert state['modules']['system']['components'] == ['amd-gaming']
        assert not (installed / 'install-h848-audio-fix').exists()
        assert 'source_sha256' in state['modules']['termlay']['commands']['termlay']
        previous = registry.read_bytes()
        command = installed / 'termlay'
        command.write_bytes(command.read_bytes() + b'\n# local edit\n')
        assert 'changed locally' in run('update.sh', '--module', 'termlay', success=False)
        assert registry.read_bytes() == previous
        # Missing selections must not silently become new installations.
        environment['SHELL_SCRIPTS_INSTALL_ROOT'] = str(home / 'system')
        run('update.sh', '--module', 'backup', success=False)
        run('update.sh', '--component', 'system:h848-audio', success=False)
        assert not (installed / 'backup-home').exists()
        assert registry.read_bytes() == previous
    print('Update lifecycle tests passed')


if __name__ == '__main__':
    main()
