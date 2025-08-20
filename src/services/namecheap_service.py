"""
Namecheap Service - all operations with Namecheap
"""
import requests
from typing import List
from src.utils.logger import get_logger

logger = get_logger("namecheap_service")

class NamecheapService:
    """Service for working with Namecheap"""

    def __init__(self, api_user: str, api_key: str, client_ip: str):
        self.api_user = api_user
        self.api_key = api_key
        self.client_ip = client_ip
        # URL для рабочего (production) окружения
        self.base_url = "https://api.namecheap.com/xml.response"


    def update_nameservers(self, domain_name: str, nameservers: List[str]) -> bool:
        """
        Updates the nameservers for a domain at Namecheap.

        Args:
            domain_name: The domain to update (e.g., 'example.com').
            nameservers: A list of nameserver hostnames.

        Returns:
            True on success, False on failure.
        """
        sld, tld = domain_name.split('.', 1)
        params = {
            "ApiUser": self.api_user,
            "ApiKey": self.api_key,
            "UserName": self.api_user,
            "ClientIp": self.client_ip,
            "Command": "namecheap.domains.dns.setCustom",
            "SLD": sld,
            "TLD": tld,
            "NameServers": ",".join(nameservers)
        }
        try:
            response = requests.get(self.base_url, params=params, timeout=20)
            response.raise_for_status()
            
            # ИЗМЕНЕНО: Более надежная проверка на ошибку.
            # Мы проверяем, что статус в XML-ответе НЕ "OK".
            if 'Status="OK"' not in response.text:
                logger.error(f"Namecheap API error for {domain_name}: {response.text}")
                return False
                
            logger.info(f"Successfully updated nameservers for {domain_name} at Namecheap.")
            return True
        except requests.RequestException as e:
            logger.error(f"API request to Namecheap failed for {domain_name}: {e}")
            return False

    @staticmethod
    def get_public_ip() -> str:
        """
        Gets the current public IP address.
        """
        try:
            response = requests.get("https://api.ipify.org?format=json", timeout=10)
            response.raise_for_status()
            return response.json()["ip"]
        except requests.RequestException as e:
            logger.error(f"Could not get public IP: {e}")
            return "127.0.0.1" # Fallback
