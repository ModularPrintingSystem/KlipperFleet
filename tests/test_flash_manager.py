import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from backend.flash_manager import FlashManager

@pytest.fixture
def flash_mgr():
    return FlashManager(klipper_dir="/tmp/klipper", katapult_dir="/tmp/katapult")

@pytest.mark.asyncio
async def test_discover_can_devices(flash_mgr, mock_subprocess):
    mock_exec, _, process_mock = mock_subprocess
    
    # Mock katapult query output
    katapult_output = b"Found UUID: 1234567890ab, Application: Katapult\n"
    
    # Mock klipper query output
    klipper_output = b"Found canbus_uuid=abcdef123456, Application: Klipper\n"
    # Setup side effects for different calls
    async def side_effect(*args, **kwargs):
        # args[0] is the program
        cmd = args[0]
        
        async def async_communicate_katapult():
            return (katapult_output, b"")
            
        async def async_communicate_klipper():
            return (klipper_output, b"")
            
        if "flashtool.py" in str(args):
            process_mock.communicate.side_effect = async_communicate_katapult
        elif "canbus_query.py" in str(args):
            process_mock.communicate.side_effect = async_communicate_klipper
        return process_mock
        
    mock_exec.side_effect = side_effect
    
    # Mock Moonraker response
    # We use MagicMock with async side effects for httpx.AsyncClient
    mock_client = MagicMock()
    
    async def async_aenter(*args, **kwargs):
        return mock_client
    async def async_aexit(*args, **kwargs):
        pass
    
    mock_client.__aenter__.side_effect = async_aenter
    mock_client.__aexit__.side_effect = async_aexit
    
    async def async_get(*args, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"result": {"status": {"configfile": {"config": {}}}}}
        return resp
        
    mock_client.get.side_effect = async_get
    
    with patch("httpx.AsyncClient", return_value=mock_client), \
         patch("os.path.exists", return_value=True):
        devices = await flash_mgr.discover_can_devices()
        
        assert len(devices) == 2
        assert devices[0]['id'] == "1234567890ab"
        assert devices[0]['mode'] == "ready"
        assert devices[1]['id'] == "abcdef123456"
        assert devices[1]['mode'] == "service"

@pytest.mark.asyncio
async def test_discover_dfu_devices(flash_mgr, mock_subprocess):
    mock_exec, _, process_mock = mock_subprocess
    
    dfu_output = b'Found DFU: [0483:df11] ver=0200, devnum=12, cfg=1, intf=0, path="1-1.2", alt=0, name="@Internal Flash  /0x08000000/064*0002Kg", serial="357236543131"\n'
    
    async def async_communicate():
        return (dfu_output, b"")
    process_mock.communicate.side_effect = async_communicate
    
    devices = await flash_mgr.discover_dfu_devices()
    
    assert len(devices) == 1
    assert devices[0]['id'] == "357236543131"

@pytest.mark.asyncio
async def test_flash_can_device(flash_mgr, mock_subprocess):
    mock_exec, _, _ = mock_subprocess
    
    # Test flashing
    async for _ in flash_mgr.flash_can("1234567890ab", "klipper.bin"):
        pass
        
    # Verify flashtool.py was called with correct args
    call_args = mock_exec.call_args[0]
    assert "python3" in call_args
    assert "flashtool.py" in call_args[1] # script path

@pytest.mark.asyncio
async def test_flash_dfu_with_leave(flash_mgr, mock_subprocess):
    mock_exec, _, _ = mock_subprocess
    
    # Test flashing with leave=True
    async for _ in flash_mgr.flash_dfu("0483:df11", "klipper.bin", leave=True):
        pass
        
    call_args = mock_exec.call_args[0]
    assert "dfu-util" in call_args
    # Check args list
    # args are passed as *args to create_subprocess_exec
    # So call_args[0] is the tuple of args
    # But create_subprocess_exec(program, arg1, arg2...)
    # So call_args[0] is (program, arg1, arg2...)
    
    args_list = list(call_args)
    assert "-s" in args_list
    s_index = args_list.index("-s")
    assert ":leave" in args_list[s_index + 1]

@pytest.mark.asyncio
async def test_flash_dfu_without_leave(flash_mgr, mock_subprocess):
    mock_exec, _, _ = mock_subprocess
    
    # Test flashing with leave=False
    async for _ in flash_mgr.flash_dfu("0483:df11", "klipper.bin", leave=False):
        pass
        
    call_args = mock_exec.call_args[0]
    args_list = list(call_args)
    assert "-s" in args_list
    s_index = args_list.index("-s")
    assert ":leave" not in args_list[s_index + 1]

@pytest.mark.asyncio
async def test_flash_dfu_offsets(flash_mgr, mock_subprocess):
    mock_exec, _, _ = mock_subprocess
    
    offsets = [
        ("0x08000000", "0x08000000"),
        ("0x08002000", "0x08002000"),
        ("0x08008000", "0x08008000"),
        ("0x08010000", "0x08010000"),
    ]
    
    for input_addr, expected_addr in offsets:
        # Reset mock for each iteration
        mock_exec.reset_mock()
        
        async for _ in flash_mgr.flash_dfu("0483:df11", "klipper.bin", address=input_addr, leave=False):
            pass
            
        # Verify the first call (the download phase)
        # Note: flash_dfu might call dfu-util multiple times if leave=True
        # but here we set leave=False to simplify.
        
        # Find the call that has "-D" (download)
        download_call = None
        for call in mock_exec.call_args_list:
            args = list(call[0])
            if "-D" in args:
                download_call = args
                break
        
        assert download_call is not None
        assert "-s" in download_call
        s_index = download_call.index("-s")
        assert download_call[s_index + 1] == expected_addr

@pytest.mark.asyncio
async def test_reboot_to_dfu_magic_baud(flash_mgr, mock_subprocess):
    mock_exec, _, _ = mock_subprocess
    
    # Mock serial.Serial
    with patch("serial.Serial") as mock_serial:
        async for _ in flash_mgr.reboot_to_dfu("/dev/ttyACM0"):
            pass
            
        # Verify 1200bps open/close
        mock_serial.assert_called_with("/dev/ttyACM0", 1200)
        mock_serial.return_value.close.assert_called()

@pytest.mark.asyncio
async def test_check_device_status_bridge(flash_mgr, mock_subprocess):
    # Test that a bridge is identified as "service" if interface is up
    # even if Moonraker doesn't know about it (common for bridges)
    
    with patch.object(flash_mgr, 'is_interface_up', new_callable=AsyncMock) as mock_up:
        mock_up.return_value = True
        
        status = await flash_mgr.check_device_status(
            "1234567890ab", 
            "can", 
            is_bridge=True, 
            skip_moonraker=True
        )
        
        assert status == "service"

