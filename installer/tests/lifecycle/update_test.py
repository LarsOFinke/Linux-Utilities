#!/usr/bin/env python3
"""Check update scope, ownership, and component preservation in temporary homes."""

from __future__ import annotations

import hashlib
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

        run('main.sh', 'setup', '--component', 'system:amd-gaming', '--module', 'termlay',
            '--module', 'connect-vps', '--module', 'backup', '--module', 'log-scout',
            '--no-configure')
        registry = home / '.local/state/shell-scripts/registry.json'
        installed = home / '.local/bin'
        state = json.loads(registry.read_text())
        old_helpers = {
            'backup': {'backup_home_common.sh': 'scripts/snapshot/backup_home_common.sh'},
            'log-scout': {'log_scout_rules.py': 'scripts/log_scout_rules.py'},
            'termlay': {'Layout.py': 'scripts/layout/Layout.py',
                        'TermlayError.py': 'scripts/TermlayError.py'},
            'connect-vps': {'Connection.py': 'scripts/Connection.py',
                            'ConnectVpsError.py': 'scripts/ConnectVpsError.py'},
        }
        for module, helpers in old_helpers.items():
            category = 'data-privacy' if module == 'backup' else (
                'monitoring' if module == 'log-scout' else 'system-utilities')
            for name, relative in helpers.items():
                source = REPOSITORY / 'src' / category / module / relative
                target = installed / name
                target.write_bytes(source.read_bytes())
                target.chmod(0o644)
                state['modules'][module]['commands'][name] = {
                    'path': str(target), 'source': str(source),
                    'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                }
        registry.write_text(json.dumps(state))
        altered_helper = installed / 'backup_home_common.sh'
        original_helper = altered_helper.read_bytes()
        altered_helper.write_bytes(original_helper + b'\n# local edit\n')
        assert 'changed locally' in run('main.sh', 'update', '--module', 'backup', success=False)
        altered_helper.write_bytes(original_helper)
        # Explicit user selections must not request system-registry privileges.
        output = run('main.sh', 'update', '--module', 'system', '--module', 'termlay',
                     '--module', 'connect-vps', '--module', 'backup', '--module', 'log-scout')
        assert all(f'Updated {name}:' in output for name in
                   ('system', 'termlay', 'connect-vps', 'backup', 'log-scout'))
        state = json.loads(registry.read_text())
        assert state['modules']['system']['components'] == ['amd-gaming']
        assert not (installed / 'install-h848-audio-fix').exists()
        assert 'source_sha256' in state['modules']['termlay']['commands']['termlay']
        for module, helpers in old_helpers.items():
            expected = {module}
            assert set(state['modules'][module]['commands']) == expected
            main_command = module
            assert (installed / main_command).read_bytes().startswith(b'\x7fELF')
            for name in helpers:
                assert not (installed / name).exists()
        assert subprocess.run([str(installed / 'termlay'), '--version'], env=environment,
                              capture_output=True, text=True, check=True).stdout.strip() == 'termlay 0.5.0'
        assert subprocess.run([str(installed / 'connect-vps'), '--help'], env=environment,
                              capture_output=True, text=True, check=True).returncode == 0
        previous = registry.read_bytes()
        command = installed / 'termlay'
        command.write_bytes(command.read_bytes() + b'\n# local edit\n')
        assert 'changed locally' in run('main.sh', 'update', '--module', 'termlay', success=False)
        assert registry.read_bytes() == previous
        # Missing selections must not silently become new installations.
        environment['SHELL_SCRIPTS_INSTALL_ROOT'] = str(home / 'system')
        run('main.sh', 'update', '--module', 'network', success=False)
        run('main.sh', 'update', '--component', 'system:h848-audio', success=False)
        assert not (installed / 'capture-traffic').exists()
        assert registry.read_bytes() == previous
    print('Update lifecycle tests passed')


if __name__ == '__main__':
    main()
