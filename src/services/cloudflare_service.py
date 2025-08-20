"""
Cloudflare Service - all operations with Cloudflare
"""
from typing import Tuple, Optional, List
import time
from cloudflare import Cloudflare, APIStatusError, APIConnectionError
from cloudflare.types.accounts import Account

from src.utils.logger import get_logger

logger = get_logger("cloudflare_service")

class CloudflareService:
    """Service for working with Cloudflare using the official library"""

    def __init__(self, api_token: str, email: str):
        """Initializes the Cloudflare client."""
        if not api_token or not email:
            raise ValueError("API Token and Email are required for CloudflareService.")
            
        # Инициализация клиента с вашими учетными данными.
        # max_retries=3 означает, что библиотека сама попробует повторить запрос 3 раза
        # с нарастающей задержкой в случае сбоя (например, при ошибках 429, >500).
        self.client = Cloudflare(api_key=api_token, api_email=email, max_retries=3)
        self.account_id = None

    def _get_account_id(self) -> Optional[str]:
        """Helper function to get the first account ID."""
        if self.account_id:
            return self.account_id
        try:
            # ИЗМЕНЕНО: Корректная обработка итерируемого объекта
            # Метод .list() возвращает специальный объект для постраничной навигации.
            accounts_page = self.client.accounts.list()
            # Пытаемся получить первый элемент из него.
            first_account: Optional[Account] = next(iter(accounts_page), None)

            if first_account:
                self.account_id = first_account.id
                logger.info(f"Successfully retrieved Cloudflare Account ID: {self.account_id}")
                return self.account_id
            else:
                logger.error("Could not retrieve Cloudflare Account ID. No accounts found.")
                return None
                
        except APIStatusError as e:
            logger.error(f"Cloudflare API error while getting account ID: {e.status_code} - {e.response.text}")
            return None
        except APIConnectionError as e:
            logger.error(f"Connection error while getting account ID: {e.__cause__}")
            return None


    def add_zone(self, domain_name: str) -> Optional[Tuple[str, List[str]]]:
        """
        Adds a new zone (domain) to Cloudflare.

        Args:
            domain_name: The name of the domain to add.

        Returns:
            A tuple containing the zone_id and a list of name_servers, or None on error.
        """
        account_id = self._get_account_id()
        if not account_id:
            return None

        try:
            zone = self.client.zones.create(
                name=domain_name,
                account={"id": account_id}
            )
            # Небольшая задержка после создания зоны, чтобы дать API время на "подготовку"
            time.sleep(3)
            logger.info(f"Zone {domain_name} created successfully. Zone ID: {zone.id}")
            return zone.id, zone.name_servers
        except APIStatusError as e:
            # Обработка ошибки, если зона уже существует
            if any("already exists" in error.get("message", "") for error in e.body.get('errors', [])):
                logger.warning(f"Zone {domain_name} already exists. Attempting to fetch its info.")
                try:
                    zones = self.client.zones.list(name=domain_name)
                    if zones:
                        zone_info = next(iter(zones), None)
                        if zone_info:
                            return zone_info.id, zone_info.name_servers
                except APIStatusError as e_fetch:
                     logger.error(f"Failed to fetch existing zone {domain_name}: {e_fetch.status_code} - {e_fetch.response.text}")
            logger.error(f"Cloudflare API error while adding zone {domain_name}: {e.status_code} - {e.response.text}")
            return None
        except APIConnectionError as e:
            logger.error(f"Connection error while adding zone {domain_name}: {e.__cause__}")
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
        if not ip_address or not (ip_address.replace('.', '').isdigit()):
            logger.error(f"Invalid IP address provided for zone {zone_id}: '{ip_address}'")
            return 0
            
        records_to_create = [
            {"type": "A", "name": "@", "content": ip_address, "proxied": True, "ttl": 1},
            {"type": "A", "name": "www", "content": ip_address, "proxied": True, "ttl": 1},
            {"type": "A", "name": "*", "content": ip_address, "proxied": True, "ttl": 1},
        ]
        
        successful_creations = 0
        for record in records_to_create:
            try:
                self.client.dns.records.create(
                    zone_id=zone_id,
                    type=record["type"],
                    name=record["name"],
                    content=record["content"],
                    proxied=record["proxied"],
                    ttl=record["ttl"]
                )
                logger.info(f"A-record '{record['name']}' created for zone {zone_id}.")
                successful_creations += 1
            except APIStatusError as e:
                # Игнорируем ошибку, если запись уже существует
                if any("already exists" in error.get("message", "") for error in e.body.get('errors', [])):
                    logger.warning(f"A-record '{record['name']}' for zone {zone_id} already exists. Skipping.")
                    successful_creations += 1
                else:
                    logger.error(f"Failed to create A-record '{record['name']}' for zone {zone_id}: {e.status_code} - {e.response.text}")
            except APIConnectionError as e:
                logger.error(f"Connection error while creating A-record '{record['name']}': {e.__cause__}")

        return successful_creations
