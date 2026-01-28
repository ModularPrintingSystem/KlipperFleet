import pytest
import os
import json
from backend.fleet_manager import FleetManager

@pytest.fixture
def fleet_mgr(tmp_path):
    return FleetManager(str(tmp_path))

def test_save_and_get_device(fleet_mgr):
    device = {
        "id": "test_id",
        "name": "Test Device",
        "method": "can",
        "profile": "test_profile"
    }
    fleet_mgr.save_device(device)
    
    fleet = fleet_mgr.get_fleet()
    assert len(fleet) == 1
    assert fleet[0]["id"] == "test_id"
    assert fleet[0]["name"] == "Test Device"

def test_update_device(fleet_mgr):
    device = {"id": "test_id", "name": "Old Name"}
    fleet_mgr.save_device(device)
    
    updated_device = {"id": "test_id", "name": "New Name"}
    fleet_mgr.save_device(updated_device)
    
    fleet = fleet_mgr.get_fleet()
    assert len(fleet) == 1
    assert fleet[0]["name"] == "New Name"

def test_update_device_id(fleet_mgr):
    # Test changing the ID of a device using old_id
    device = {"id": "old_id", "name": "Test Device"}
    fleet_mgr.save_device(device)
    
    updated_device = {"id": "new_id", "old_id": "old_id", "name": "Test Device"}
    fleet_mgr.save_device(updated_device)
    
    fleet = fleet_mgr.get_fleet()
    assert len(fleet) == 1
    assert fleet[0]["id"] == "new_id"
    assert "old_id" not in fleet[0]

def test_remove_device(fleet_mgr):
    device = {"id": "test_id", "name": "Test Device"}
    fleet_mgr.save_device(device)
    assert len(fleet_mgr.get_fleet()) == 1
    
    fleet_mgr.remove_device("test_id")
    assert len(fleet_mgr.get_fleet()) == 0
