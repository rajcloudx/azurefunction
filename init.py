import logging
import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.network import NetworkManagementClient

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    # Parse request parameters
    vm_name = req.params.get('vm_name')
    resource_group_name = req.params.get('resource_group_name')
    location = req.params.get('location')

    if not vm_name or not resource_group_name or not location:
        return func.HttpResponse(
            "Please pass vm_name, resource_group_name, and location in the request body",
            status_code=400
        )

    try:
        credential = DefaultAzureCredential()
        subscription_id = 'your_subscription_id'  # Replace with your Azure Subscription ID

        # Create management clients
        resource_client = ResourceManagementClient(credential, subscription_id)
        compute_client = ComputeManagementClient(credential, subscription_id)
        network_client = NetworkManagementClient(credential, subscription_id)

        # Create the resource group if it doesn't exist
        resource_client.resource_groups.create_or_update(resource_group_name, {'location': location})

        # Create a virtual network
        vnet_name = f'{vm_name}-vnet'
        subnet_name = f'{vm_name}-subnet'
        vnet_params = {
            'location': location,
            'address_space': {'address_prefixes': ['10.0.0.0/16']}
        }
        subnet_params = {
            'address_prefix': '10.0.0.0/24'
        }

        vnet_result = network_client.virtual_networks.begin_create_or_update(
            resource_group_name, vnet_name, vnet_params
        ).result()

        subnet_result = network_client.subnets.begin_create_or_update(
            resource_group_name, vnet_name, subnet_name, subnet_params
        ).result()

        # Create a public IP address
        ip_name = f'{vm_name}-ip'
        ip_params = {
            'location': location,
            'public_ip_allocation_method': 'Dynamic'
        }
        ip_address_result = network_client.public_ip_addresses.begin_create_or_update(
            resource_group_name, ip_name, ip_params
        ).result()

        # Create a network interface
        nic_name = f'{vm_name}-nic'
        nic_params = {
            'location': location,
            'ip_configurations': [{
                'name': f'{vm_name}-ipconfig',
                'subnet': {'id': subnet_result.id},
                'public_ip_address': {'id': ip_address_result.id}
            }]
        }
        nic_result = network_client.network_interfaces.begin_create_or_update(
            resource_group_name, nic_name, nic_params
        ).result()

        # Create a virtual machine
        vm_params = {
            'location': location,
            'hardware_profile': {'vm_size': 'Standard_DS1_v2'},
            'storage_profile': {
                'image_reference': {
                    'publisher': 'Canonical',
                    'offer': 'UbuntuServer',
                    'sku': '18.04-LTS',
                    'version': 'latest'
                }
            },
            'os_profile': {
                'computer_name': vm_name,
                'admin_username': 'azureuser',
                'admin_password': 'Password123!'  # Replace with your own password
            },
            'network_profile': {
                'network_interfaces': [{'id': nic_result.id}]
            }
        }

        vm_result = compute_client.virtual_machines.begin_create_or_update(
            resource_group_name, vm_name, vm_params
        ).result()

        return func.HttpResponse(f"VM {vm_name} created successfully.", status_code=200)

    except Exception as e:
        logging.error(f"Error creating VM: {e}")
        return func.HttpResponse(f"Error creating VM: {e}", status_code=500)
