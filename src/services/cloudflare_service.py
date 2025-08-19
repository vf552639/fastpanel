"""
Cloudflare Service - all operations with Cloudflare
"""
import requests
from typing import Tuple, Optional, List

from src.utils.logger import get_logger

logger = get_logger("cloudflare_service")

class CloudflareService:
    """Service for working with Cloudflare"""

    def __init__(self, api_token: str, email: str):
        self.api_token = api_token
        self.email = email
        self.base_url = "https://api.cloudflare.com/client/v4"
        self.headers = {
            "X-Auth-Email": self.email,
            "X-Auth-Key": self.api_token,
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
        }
        try:
            account_id = self._get_account_id()
            if not account_id:
                return None
            data["account"] = {"id": account_id}

            response = requests.post(url, headers=self.headers, json=data, timeout=10)
            response.raise_for_status()
            result = response.json()

            if result.get("success"):
                zone_id = result["result"]["id"]
                name_servers = result["result"]["name_servers"]
                logger.info(f"Zone {domain_name} created successfully. Zone ID: {zone_id}")
                return zone_id, name_servers
            else:
                error_message = result.get('errors', [{}])[0].get('message', 'Unknown error')
                logger.error(f"Error adding zone {domain_name}: {error_message}")
                return None
        except requests.exceptions.HTTPError as http_err:
             logger.error(f"HTTP error occurred while adding zone {domain_name}: {http_err} - {http_err.response.text}")
             return None
        except requests.RequestException as e:
            logger.error(f"API request failed while adding zone {domain_name}: {e}")
            return None

    def create_a_records(self, zone_id: str, ip_address: str) -> int:
        """
        Creates standard A-records (@, www, *) for a zone.

        Args:
            zone_id: The ID of the zone to add records to.
            ip_address: The IP address for the A-records.

        Returns:
            The number of successfully created records (0 to 3).
        """
        # ИЗМЕНЕНО: Проверка IP-адреса перед отправкой запроса
        if not ip_address or not (ip_address.replace('.', '').isdigit()):
            logger.error(f"Invalid IP address provided for zone {zone_id}: '{ip_address}'")
            return 0

        url = f"{self.base_url}/zones/{zone_id}/dns_records"
        records_to_create = [
            # Запись для '@' теперь использует имя зоны, как рекомендует Cloudflare
            {"type": "A", "name": "@", "content": ip_address, "proxied": True},
            {"type": "A", "name": "www", "content": ip_address, "proxied": True},
            {"type": "A", "name": "*", "content": ip_address, "proxied": True},
        ]
        
        # ИЗМЕНЕНО: Логика для подсчета успешных операций
        successful_creations = 0
        for record in records_to_create:
            try:
                response = requests.post(url, headers=self.headers, json=record, timeout=10)
                response.raise_for_status()
                result = response.json()
                if result.get("success"):
                    logger.info(f"A-record '{record['name']}' created for zone {zone_id}.")
                    successful_creations += 1
                else:
                    error_message = result.get('errors', [{}])[0].get('message', 'Unknown error')
                    # Логируем ошибку только для конкретной записи
                    logger.error(f"Error creating A-record '{record['name']}' for zone {zone_id}: {error_message}")
            except requests.RequestException as e:
                logger.error(f"API request failed while creating A-record '{record['name']}' for zone {zone_id}: {e}")
        
        return successful_creations

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
