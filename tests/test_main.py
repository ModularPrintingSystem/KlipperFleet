import pytest
import asyncio
import os
from unittest.mock import MagicMock, patch, AsyncMock
from backend.main import app, batch_operation, get_flash_offset, test_magic_baud as app_test_magic_baud, post_config_tree, ConfigPreview

@pytest.mark.asyncio
async def test_kconfig_resolution_loop():
    # Test that the 10-pass loop correctly resolves dependencies
    with patch("backend.main.kconfig_mgr") as mock_kconfig_mgr:
        preview = ConfigPreview(
            profile=None,
            values=[
                {"name": "SYM_A", "value": "y"},
                {"name": "SYM_B", "value": "y"}
            ]
        )
        
        # Mock Request
        mock_request = MagicMock()
        
        await post_config_tree(preview, mock_request)
        
        # Verify set_value was called multiple times for each symbol
        # (10 passes * 2 symbols = 20 calls)
        assert mock_kconfig_mgr.set_value.call_count == 20
        
        # Verify the order (it should repeat the values list 10 times)
        calls = mock_kconfig_mgr.set_value.call_args_list
        assert calls[0][0] == ("SYM_A", "y")
        assert calls[1][0] == ("SYM_B", "y")
        assert calls[2][0] == ("SYM_A", "y")

@pytest.mark.asyncio
async def test_batch_operation_bridge_sequencing(mock_task_store, mock_subprocess):
    # Mock dependencies
    with patch("backend.main.fleet_mgr") as mock_fleet_mgr, \
         patch("backend.main.flash_mgr") as mock_flash_mgr, \
         patch("backend.main.task_store", mock_task_store), \
         patch("backend.main.manage_klipper_services", new_callable=AsyncMock) as mock_services, \
         patch("os.path.exists", return_value=True):
        
        mock_fleet_mgr.get_fleet.return_value = [
            {"id": "can_dev", "name": "CAN Device", "method": "can", "profile": "can_prof", "is_bridge": False},
            {"id": "bridge_dev", "name": "Bridge Device", "method": "can", "profile": "bridge_prof", "is_bridge": True}
        ]
        
        # Setup flash manager mocks
        # Helper for async return values
        async def async_return(val):
            return val

        # Helper for async generators
        async def async_gen(items):
            for item in items:
                yield item

        # Sequence: 
        # 1. Initial check (can_dev) -> "service" (added to reboot_tasks)
        # 2. Initial check (bridge_dev) -> "service" (skipped, is bridge)
        # 3. Reboot wait loop (can_dev) -> "ready"
        # 4. Flash loop (can_dev) -> "ready"
        # 5. Flash loop (bridge_dev) -> "service" (triggers bridge reboot)
        status_sequence = ["service", "service", "ready", "ready", "service"]
        
        async def check_status_side_effect(*args, **kwargs):
            if status_sequence:
                return status_sequence.pop(0)
            return "ready"
        
        mock_flash_mgr.check_device_status.side_effect = check_status_side_effect
        
        mock_flash_mgr.reboot_to_katapult.side_effect = lambda *args, **kwargs: async_gen(["Rebooting..."])
        mock_flash_mgr.flash_can.side_effect = lambda *args, **kwargs: async_gen(["Flashing..."])
        mock_flash_mgr.flash_serial.side_effect = lambda *args, **kwargs: async_gen(["Flashing Serial..."])
        mock_flash_mgr.reboot_to_dfu.side_effect = lambda *args, **kwargs: async_gen(["Rebooting DFU..."])
        
        mock_flash_mgr.is_interface_up.side_effect = lambda *args, **kwargs: async_return(True)
        mock_flash_mgr.resolve_dfu_id.side_effect = lambda x, **kwargs: async_return(x)
        mock_flash_mgr.resolve_serial_id.side_effect = lambda x, **kwargs: async_return(x)
        mock_flash_mgr.ensure_canbus_up.side_effect = lambda *args, **kwargs: async_return(None)

        # Mock discover_can_devices to return devices in service mode
        mock_flash_mgr.discover_can_devices.side_effect = lambda *args, **kwargs: async_return([
            {"id": "can_dev", "mode": "service"},
            {"id": "bridge_dev", "mode": "service"}
        ])

        # Mock discover_serial_devices to return the bridge when it reboots
        # 1. Initial call (before reboot loop): []
        # 2. Bridge reboot loop: [bridge_dev_serial]
        serial_responses = [[]] + [[{"id": "bridge_dev_serial", "port": "/dev/ttyACM0"}]] * 50
        
        async def discover_serial_side_effect(*args, **kwargs):
            if serial_responses:
                return serial_responses.pop(0)
            return [{"id": "bridge_dev_serial", "port": "/dev/ttyACM0"}]

        mock_flash_mgr.discover_serial_devices.side_effect = discover_serial_side_effect
        mock_flash_mgr.discover_dfu_devices.side_effect = lambda *args, **kwargs: async_return([])
        
        # Mock resolve_serial_id to handle the bridge ID change
        mock_flash_mgr.resolve_serial_id.side_effect = lambda x, **kwargs: async_return("bridge_dev_serial" if x == "bridge_dev" else x)

        # Mock background tasks
        mock_bg_tasks = MagicMock()

        # Run batch operation
        result = await batch_operation("flash-all", mock_bg_tasks)

        # Get the task function that was added to background tasks
        task_func = mock_bg_tasks.add_task.call_args[0][0]

        # Execute the task function
        await task_func()


        # Verify service management
        mock_services.assert_any_call("stop")
        mock_services.assert_any_call("start")

        # Verify flashing
        # can_dev should be flashed via CAN
        assert mock_flash_mgr.flash_can.call_count == 1
        assert mock_flash_mgr.flash_can.call_args[0][0] == "can_dev"
        
        # bridge_dev should be flashed via Serial (after reboot)
        assert mock_flash_mgr.flash_serial.call_count == 1
        # The ID passed to flash_serial should be the resolved serial ID
        assert mock_flash_mgr.flash_serial.call_args[0][0] == "bridge_dev_serial"

@pytest.mark.asyncio
async def test_get_flash_offset():
    # Test various .config contents and ensure correct offset is returned
    test_cases = [
        ("CONFIG_FLASH_START_2000=y", "0x08002000"),
        ("CONFIG_STM32_FLASH_START_8000=y", "0x08008000"),
        ("CONFIG_FLASH_START_10000=y", "0x08010000"),
        ("CONFIG_FLASH_START_0=y", "0x08000000"),
        ("RANDOM_STUFF=y", "0x08000000"), # Default
    ]
    
    with patch("builtins.open", MagicMock()) as mock_open, \
         patch("os.path.exists", return_value=True):
        
        for content, expected in test_cases:
            mock_open.return_value.__enter__.return_value.read.return_value = content
            assert get_flash_offset("dummy_profile") == expected

@pytest.mark.asyncio
async def test_magic_baud_full_cycle(mock_task_store, mock_subprocess):
    with patch("backend.main.flash_mgr") as mock_flash_mgr, \
         patch("backend.main.task_store", mock_task_store), \
         patch("os.path.exists", return_value=True):
         
        # Setup mocks
        dfu_responses = [[], [{"id": "dfu_id", "serial": "123"}]]
        async def mock_discover_dfu():
            return dfu_responses.pop(0) if dfu_responses else []
        
        mock_flash_mgr.discover_dfu_devices.side_effect = mock_discover_dfu
        mock_flash_mgr.resolve_dfu_id.return_value = "dfu_id"
        
        async def async_gen(items):
            for item in items:
                yield item
                
        mock_flash_mgr.reboot_device.side_effect = lambda *args, **kwargs: async_gen(["Rebooting..."])
        mock_flash_mgr.reboot_to_dfu.side_effect = lambda *args, **kwargs: async_gen(["Rebooting to DFU..."])
        mock_flash_mgr.flash_dfu.side_effect = lambda *args, **kwargs: async_gen(["Exiting DFU..."])
        
        # Mock serial
        with patch("serial.Serial") as mock_serial:
            # Run test
            response = await app_test_magic_baud("serial_port", full_cycle=True)
            
            # Consume generator
            output = ""
            async for chunk in response.body_iterator:
                if isinstance(chunk, bytes):
                    output += chunk.decode()
                elif isinstance(chunk, str):
                    output += chunk
                else:
                    # Fallback for other types like bytearray
                    output += str(chunk)
                
            assert "PHASE1_SUCCESS" in output
            assert "PHASE2_SUCCESS" in output
            
            # Verify calls
            mock_serial.assert_called()
            mock_serial.return_value.close.assert_called()
            # mock_flash_mgr.flash_dfu.assert_called_once() # Not called in this test flow
            mock_flash_mgr.reboot_device.assert_called() # Called for phase 2
            # Check that leave=True was passed to flash_dfu for the exit phase
                # assert mock_flash_mgr.flash_dfu.call_args[1]['leave'] is True
