import json
import logging
import time
from typing import List, Dict, Optional
import threading

logger = logging.getLogger(__name__)

class ProxyManager:
    """Manages a pool of proxies with rotation and cooldown logic."""

    def __init__(self, proxies: List[Dict[str, str]], cooldown_seconds: int = 600):
        """
        Initialize the proxy manager.
        
        Args:
            proxies: List of proxy dictionaries (e.g., [{"http": "...", "https": "..."}, ...])
        """
        self.proxies = proxies
        self.cooldown_seconds = cooldown_seconds
        self._lock = threading.Lock()
        
        # Track usage and bad status
        # Key: proxy_id (index in self.proxies), Value: timestamp until when it's bad
        self._bad_proxies: Dict[int, float] = {} 
        
        # Simple round-robin index
        self._current_index = 0

    def get_proxy(self) -> Optional[Dict[str, str]]:
        """
        Get an available proxy from the pool.
        Returns a proxy dict or None if no proxies are available.
        """
        if not self.proxies:
            return None

        with self._lock:
            # Try to find a good proxy starting from current index
            start_index = self._current_index
            count = len(self.proxies)

            for _ in range(count):
                idx = self._current_index
                # Move index for next call immediately
                self._current_index = (self._current_index + 1) % count
                
                # Check if this proxy is in cooldown
                if idx in self._bad_proxies:
                    cooldown_until = self._bad_proxies[idx]
                    if time.time() < cooldown_until:
                        continue # Still bad
                    else:
                        # Cooldown expired
                        del self._bad_proxies[idx]
                logger.info("Using proxy %s", idx)
                return self.proxies[idx]

            # If we looped through all and found none
            logger.warning("All proxies are currently in cooldown.")
            return None

    def mark_bad(self, proxy: Dict[str, str]):
        """
        Mark a proxy as bad (e.g. 429 received) to trigger cooldown.
        """
        if not proxy:
            return

        with self._lock:
            try:
                # Find index of this proxy
                idx = self.proxies.index(proxy)
                self._bad_proxies[idx] = time.time() + self.cooldown_seconds
                logger.info(f"Marked proxy {idx} as bad for {self.cooldown_seconds}s")
            except ValueError:
                pass # Proxy not in our list?

def load_proxies_from_json(file_path: str) -> List[Dict[str, str]]:
    """Load proxies from a JSON file."""
    try:
        with open(file_path, 'r') as f:
            proxies = json.load(f)
            if isinstance(proxies, list):
                return proxies
            else:
                logger.error("Proxy file must contain a list of proxy objects.")
                return []
    except Exception as e:
        logger.error(f"Failed to load proxies from {file_path}: {e}")
        return []
