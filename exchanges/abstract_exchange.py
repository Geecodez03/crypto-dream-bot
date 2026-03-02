from abc import ABC, abstractmethod
from typing import Dict, Optional


class AbstractExchange(ABC):
    @abstractmethod
    def get_balances(self) -> Dict[str, float]:
        pass

    @abstractmethod
    def get_market_data(self, symbol: str) -> Dict[str, float]:
        pass

    @abstractmethod
    def place_order(
        self, order_type: str, symbol: str, amount: float, price: Optional[float] = None
    ) -> Dict[str, float]:
        pass
