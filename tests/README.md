# KlipperFleet Unit Tests

This directory contains unit tests for the KlipperFleet backend, focusing on flashing workflows, device management, and system interactions. The tests use `pytest` and `unittest.mock` to simulate hardware and system commands, allowing them to run locally without physical devices.

## Test Configurations & Scenarios

The following configurations and scenarios are covered:

### 1. Flash Manager (`test_flash_manager.py`)

*   **CAN Flashing**:
    *   **Standard CAN**: Verifies `flashtool.py` invocation with correct UUID and interface.
    *   **CAN Bridge**: Ensures bridges are identified correctly.
    *   **Reboot to Katapult**: Verifies the CAN sequence (Set ID -> Complete) to jump to bootloader.

*   **Serial Flashing**:
    *   **Standard Serial**: Verifies `flashtool.py` invocation with serial device path.
    *   **Magic Baud**: Verifies the 1200bps baud rate trigger for DFU entry.

*   **DFU Flashing**:
    *   **Standard DFU**: Verifies `dfu-util` invocation with correct VID:PID and address.
    *   **DFU Exit (Leave)**: Verifies the `:leave` suffix is applied when requested.
    *   **DFU No-Exit**: Verifies the `:leave` suffix is omitted when requested.

*   **Linux MCU Flashing**:
    *   **Service Handling**: Verifies that the Klipper service is stopped before flashing and started after.
    *   **Make Flash**: Verifies the `make flash` command execution.

*   **Device Discovery**:
    *   **CAN Discovery**: Mocks `canbus_query.py` output.
    *   **Serial Discovery**: Mocks `ls /dev/serial/by-id/*` output.
    *   **DFU Discovery**: Mocks `dfu-util -l` output.

### 2. Main Application Logic (`test_main.py`)

*   **Batch Operations**:
    *   **Mixed Fleet**: Verifies the correct order of operations for a fleet containing CAN, Serial, and DFU devices.
    *   **Bridge Handling**: Ensures CAN bridges are flashed *after* other CAN devices to maintain bus connectivity.
    *   **Service Management**: Verifies global service stop/start wrapping the batch operation.

*   **DFU Cycle Test**:
    *   **Phase 1 (Entry)**: Simulates successful and failed DFU entry via Magic Baud.
    *   **Phase 2 (Exit)**: Simulates successful and failed DFU exit via `dfu-util`.
    *   **Full Cycle**: Verifies the complete flow and status reporting.

*   **Fleet Management**:
    *   **Device Registration**: Verifies adding/updating devices in `fleet.json`.
    *   **Status Overrides**: Verifies that active tasks override the reported device status (e.g., showing "Flashing" instead of "Offline").

## Running Tests

Prerequisites:
```bash
pip install pytest pytest-asyncio
```

Run all tests:
```bash
pytest tests/
```

Run specific test file:
```bash
pytest tests/test_flash_manager.py
```
