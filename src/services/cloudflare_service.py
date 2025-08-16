"""
Cloudflare Service - all operations with Cloudflare
"""
import requests
from typing import Tuple, Optional, List

from src.utils.logger import get_logger

logger = get_logger("cloudflare_service")

class CloudflareService:
    """Service for working with Cloudflare"""

    def __init__(self, api_token: str):
        self.api_token = api_token
        self.base_url = "https://api.cloudflare.com/client/v4"
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }

    def add_zone(self, domain_name: str) -> Optional[Tuple[str, List[str]]]:
        """
        Adds a new zone (domain) to Cloudflare.

        Args:
            domain_name: The name of the domain to add.

        Returns:
            A tuple containing the zone_id and a list of name_servers, or None on error.
        """
        url = f"{self.base_url}/zones"
        data = {
            "name": domain_name,
            "account": {"id": self._get_account_id()} # Helper to get account ID
        }
        try:
            response = requests.post(url, headers=self.headers, json=data, timeout=10)
            response.raise_for_status()
            result = response.json()
            if result.get("success"):
                zone_id = result["result"]["id"]
                name_servers = result["result"]["name_servers"]
                logger.info(f"Zone {domain_name} created successfully. Zone ID: {zone_id}")
                return zone_id, name_servers
            else:
                logger.error(f"Error adding zone {domain_name}: {result['errors'][0]['message']}")
                return None
        except requests.RequestException as e:
            logger.error(f"API request failed while adding zone {domain_name}: {e}")
            return None

    def create_a_records(self, zone_id: str, ip_address: str) -> bool:
        """
        Creates standard A-records (@, www, *) for a zone.

        Args:
            zone_id: The ID of the zone to add records to.
            ip_address: The IP address for the A-records.

        Returns:
            True if all records were created successfully, False otherwise.
        """
        url = f"{self.base_url}/zones/{zone_id}/dns_records"
        records_to_create = [
            {"type": "A", "name": "@", "content": ip_address, "proxied": True},
            {"type": "A", "name": "www", "content": ip_address, "proxied": True},
            {"type": "A", "name": "*", "content": ip_address, "proxied": True},
        ]
        success = True
        for record in records_to_create:
            try:
                response = requests.post(url, headers=self.headers, json=record, timeout=10)
                response.raise_for_status()
                result = response.json()
                if not result.get("success"):
                    logger.error(f"Error creating A-record {record['name']} for zone {zone_id}: {result['errors'][0]['message']}")
                    success = False
                else:
                    logger.info(f"A-record {record['name']} created for zone {zone_id}.")
            except requests.RequestException as e:
                logger.error(f"API request failed while creating A-record for zone {zone_id}: {e}")
                success = False
        return success

    def _get_account_id(self) -> Optional[str]:
        """Helper function to get the first account ID."""
        try:
            response = requests.get(f"{self.base_url}/accounts", headers=self.headers, timeout=10)
            response.raise_for_status()
            result = response.json()
            if result.get("success") and result["result"]:
                return result["result"][0]["id"]
            logger.error("Could not retrieve Cloudflare Account ID.")
            return None
        except requests.RequestException as e:
            logger.error(f"API request failed while getting account ID: {e}")
            return None
