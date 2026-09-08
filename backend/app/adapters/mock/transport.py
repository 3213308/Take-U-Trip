# app/adapters/mock/transport.py
"""Mock 交通数据"""

from app.adapters.base import BaseTransportAdapter

_MOCK_TRANSPORTS: dict[tuple[str, str], list[dict]] = {
    ("北京", "成都"): [
        {"type": "高铁", "number": "G89", "departure": "06:50", "arrival": "14:25",
         "duration": "7h35m", "price": 778.5, "seat": "二等座"},
        {"type": "飞机", "number": "CA4112", "departure": "08:00", "arrival": "10:55",
         "duration": "2h55m", "price": 1280, "seat": "经济舱"},
        {"type": "飞机", "number": "3U8886", "departure": "14:30", "arrival": "17:35",
         "duration": "3h5m", "price": 980, "seat": "经济舱"},
    ],
    ("上海", "成都"): [
        {"type": "飞机", "number": "MU5401", "departure": "09:00", "arrival": "12:15",
         "duration": "3h15m", "price": 1150, "seat": "经济舱"},
        {"type": "高铁", "number": "G1974", "departure": "07:18", "arrival": "19:32",
         "duration": "12h14m", "price": 1040, "seat": "二等座"},
    ],
}

_DEFAULT = [
    {"type": "高铁", "number": "G1234", "departure": "08:00", "arrival": "15:00",
     "duration": "7h", "price": 600, "seat": "二等座"},
    {"type": "飞机", "number": "CA1234", "departure": "10:00", "arrival": "13:00",
     "duration": "3h", "price": 1000, "seat": "经济舱"},
]


class MockTransportAdapter(BaseTransportAdapter):
    async def search(self, departure: str, destination: str, date: str,
                     transport_type: str = "all") -> list[dict]:
        results = _MOCK_TRANSPORTS.get((departure, destination), _DEFAULT)
        if transport_type != "all":
            results = [r for r in results if r["type"] == transport_type]
        return results
