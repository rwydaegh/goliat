import os
import requests
import json

API_TOKEN = "YOUR_TENSORDOCK_API_TOKEN"
BASE_URL = "https://dashboard.tensordock.com/api/v2"
GPU_TYPE = "geforcertx4090-pcie-24gb" # Switched to RTX 4090
REQUESTED_VCPUS = 8
REQUESTED_RAM_GB = 32

def find_hostnode():
    """Finds a specific hostnode that supports dedicated IPs."""
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Accept": "application/json"
    }
    params = {
        "gpu": GPU_TYPE,
        "minVcpu": REQUESTED_VCPUS,
        "minRamGb": REQUESTED_RAM_GB
    }
    print(f"Querying available hostnodes for {GPU_TYPE} with dedicated IP support...")
    response = requests.get(f"{BASE_URL}/hostnodes", headers=headers, params=params)
    response.raise_for_status()
    hostnodes = response.json().get("data", {}).get("hostnodes", [])
    
    for node in hostnodes:
        if node.get("available_resources", {}).get("has_public_ip_available"):
            node_id = node['id']
            location_name = node.get("location", {}).get("city", "Unknown")
            print(f"Found suitable hostnode: {node_id} in {location_name}")
            return node_id
                
    print("No suitable hostnode found with dedicated IP support.")
    return None

def create_vm_with_dedicated_ip(hostnode_id):
    """Creates a Windows VM on a specific hostnode with a dedicated IP."""
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    payload = {
        "data": {
            "type": "virtualmachine",
            "attributes": {
                "name": "my-windows-4090-instance",
                "type": "virtualmachine",
                "image": "windows10",
                "hostnode_id": hostnode_id,
                "useDedicatedIp": True,
                "resources": {
                    "vcpu_count": REQUESTED_VCPUS,
                    "ram_gb": REQUESTED_RAM_GB,
                    "storage_gb": 250,
                    "gpus": {
                        GPU_TYPE: {"count": 1}
                    }
                },
                "password": "YOUR_VM_PASSWORD"
            }
        }
    }
    print(f"Sending creation request to hostnode {hostnode_id}...")
    response = requests.post(f"{BASE_URL}/instances", headers=headers, data=json.dumps(payload))
    
    print(f"Status Code: {response.status_code}")
    try:
        print("Response JSON:")
        print(response.json())
    except json.JSONDecodeError:
        print("Response content is not valid JSON:")
        print(response.text)

    response.raise_for_status()
    return response.json()

if __name__ == "__main__":
    print("Searching for a suitable hostnode...")
    node_id = find_hostnode()
    if node_id:
        try:
            vm_info = create_vm_with_dedicated_ip(node_id)
            print("\nVM creation successful!")
            print(json.dumps(vm_info, indent=2))
        except requests.exceptions.HTTPError as e:
            print(f"\nAn HTTP error occurred: {e}")
            if e.response:
                print(f"Response body: {e.response.text}")
        except Exception as e:
            print(f"\nAn unexpected error occurred: {e}")
    else:
        print("Could not find any available hostnode with the specified GPU and resources.")