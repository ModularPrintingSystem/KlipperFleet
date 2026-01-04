import json
import os
from typing import List, Dict, Any

class FleetManager:
    def __init__(self, data_dir: str) -> None:
        self.data_dir: str = data_dir
        self.fleet_file: str = os.path.join(data_dir, "fleet.json")
        self._ensure_data_dir()

    def _ensure_data_dir(self) -> None:
        os.makedirs(self.data_dir, exist_ok=True)
        if not os.path.exists(self.fleet_file):
            with open(self.fleet_file, 'w') as f:
                json.dump([], f)

    def get_fleet(self) -> List[Dict[str, Any]]:
        """Returns the list of registered devices in the fleet."""
        with open(self.fleet_file, 'r') as f:
            return json.load(f)

    def save_device(self, device: Dict[str, Any]) -> None:
        """Adds or updates a device in the fleet."""
        fleet: List[Dict[str, Any]] = self.get_fleet()
        old_id: Any | None = device.get('old_id')
        target_id = old_id if old_id else device['id']
        
        # Check if device already exists by ID or old_id
        for i, d in enumerate(fleet):
            if d['id'] == target_id:
                # Remove old_id from the saved data
                save_data: Dict[str, Any] = device.copy()
                save_data.pop('old_id', None)
                fleet[i] = save_data
                break
        else:
            save_data: Dict[str, Any] = device.copy()
            save_data.pop('old_id', None)
            fleet.append(save_data)
        
        with open(self.fleet_file, 'w') as f:
            json.dump(fleet, f, indent=4)

    def remove_device(self, device_id: str) -> None:
        """Removes a device from the fleet."""
        fleet: List[Dict[str, Any]] = self.get_fleet()
        fleet = [d for d in fleet if d['id'] != device_id]
        with open(self.fleet_file, 'w') as f:
            json.dump(fleet, f, indent=4)
