import pytest
import sys
import os
from unittest.mock import MagicMock

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

@pytest.fixture
def mock_task_store():
    store = MagicMock()
    store.is_cancelled.return_value = False
    return store

@pytest.fixture
def mock_subprocess():
    """Mocks asyncio.create_subprocess_exec / shell"""
    with MagicMock() as mock_exec, MagicMock() as mock_shell:
        # We use unittest.mock.patch manually or via the fixture if we imported it
        # But here let's just use the context managers from unittest.mock
        from unittest.mock import patch
        
        # Patching where it is used
        with patch("backend.flash_manager.asyncio.create_subprocess_exec") as mock_exec, \
             patch("backend.flash_manager.asyncio.create_subprocess_shell") as mock_shell, \
             patch("backend.main.asyncio.create_subprocess_shell") as mock_shell_main:
        
            # Setup default process mock
            process_mock = MagicMock()
            
            # Make communicate awaitable
            async def async_communicate(*args, **kwargs):
                return (b"stdout", b"stderr")
            process_mock.communicate.side_effect = async_communicate

            process_mock.returncode = 0
            
            # Make wait awaitable
            async def async_wait():
                return 0
            process_mock.wait.side_effect = async_wait
            
            # Make stdout.readline awaitable
            async def async_readline():
                return b""
            
            process_mock.stdout = MagicMock()
            process_mock.stdout.readline.side_effect = async_readline
            
            # Make the mock awaitable
            async def async_process(*args, **kwargs):
                return process_mock
                
            mock_exec.side_effect = async_process
            mock_shell.side_effect = async_process
            mock_shell_main.side_effect = async_process

            yield mock_exec, mock_shell, process_mock
