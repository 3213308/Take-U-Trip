# app/adapters/real/train12306.py
"""12306 余票查询适配器（免费、免登录、非官方）

接口来源：
- 车站代码表: https://kyfw.12306.cn/otn/resources/js/framework/station_name.js
- 余票查询:   https://kyfw.12306.cn/otn/leftTicket/queryO

注意：这是逆向接口，非官方承诺，可能随时变更。
"""

import asyncio
import logging
import re
import time

import httpx

from app.adapters.base import BaseTransportAdapter

logger = logging.getLogger(__name__)

_STATION_URL = "https://kyfw.12306.cn/otn/resources/js/framework/station_name.js"
# 12306 的余票查询端点字母会轮换，且偶发 302 到 error.html，按顺序尝试
_QUERY_ENDPOINTS = ("queryG", "queryZ", "queryA", "queryO")
_INIT_URL = "https://kyfw.12306.cn/otn/leftTicket/init"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Referer": "https://kyfw.12306.cn/otn/leftTicket/init",
}

# 进程级缓存：车站代码表
_station_map: dict[str, str] | None = None
_station_loaded_at: float = 0.0
# 串行化所有 12306 请求：并发 burst 容易触发反爬 302
_query_lock = asyncio.Lock()


async def _load_station_map() -> dict[str, str]:
    """拉取车站代码表，返回 {车站中文名: 三字母代码}"""
    global _station_map, _station_loaded_at
    if _station_map and time.time() - _station_loaded_at < 86400:
        return _station_map
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(_STATION_URL, headers=_HEADERS)
        r.raise_for_status()
        text = r.text
    # 格式: @bjb|北京北|VAP|beijingbei|bjb|0|0357|北京|||
    # 每段: @<拼音>|<中文名>|<三字母代码>|<拼音2>|...
    pairs = re.findall(r"@[a-z]+\|([^|]+)\|([A-Z]+)\|", text)
    _station_map = {name: code for name, code in pairs}
    _station_loaded_at = time.time()
    logger.info("12306 车站代码表加载完成: %d 站", len(_station_map))
    return _station_map


def _find_station_code(name: str, smap: dict[str, str]) -> str | None:
    """模糊匹配车站名：优先精确，再去掉'站'后缀，再包含匹配"""
    name = name.strip()
    if name in smap:
        return smap[name]
    # 用户常传"雄安站""成都站"，去掉"站"
    for suffix in ("站", "东站", "西站", "南站", "北站"):
        if name.endswith(suffix):
            base = name[: -len(suffix)]
            if base in smap:
                return smap[base]
    # 包含匹配（取第一个）
    for k, v in smap.items():
        if name in k or k in name:
            return v
    return None


def _parse_duration(dep: str, arr: str) -> str:
    """根据 HH:MM-HH:MM 算时长，跨天自动+24h"""
    try:
        dh, dm = map(int, dep.split(":"))
        ah, am = map(int, arr.split(":"))
        d_min = dh * 60 + dm
        a_min = ah * 60 + am
        if a_min < d_min:
            a_min += 24 * 60
        diff = a_min - d_min
        h, m = divmod(diff, 60)
        return f"{h}h{m:02d}m"
    except Exception:
        return ""


class Train12306Adapter(BaseTransportAdapter):
    """12306 高铁/动车查询（免费）"""

    @staticmethod
    async def _query_with_retry(params: dict, retries: int = 3) -> dict | None:
        """串行 + 重试 + 端点轮换地请求余票接口。

        12306 偶发把 queryX 302 到 error.html（反爬抖动），单次失败不代表无票，
        重新 init 拿 cookie、换端点字母、退避后通常能恢复。
        """
        async with _query_lock:
            for attempt in range(retries):
                async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                    for ep in _QUERY_ENDPOINTS:
                        try:
                            # 每次都重新 init 拿 cookie，避免会话失效
                            await client.get(_INIT_URL, headers=_HEADERS)
                            await asyncio.sleep(0.15)
                            r = await client.get(
                                f"https://kyfw.12306.cn/otn/leftTicket/{ep}",
                                params=params, headers=_HEADERS,
                            )
                            if r.status_code == 200 and "error" not in str(r.url):
                                data = r.json()
                                if data and data.get("httpstatus") == 200:
                                    return data
                        except Exception as e:  # 网络/JSON 异常也走重试
                            logger.debug("12306 %s 第%d次尝试异常: %s", ep, attempt + 1, e)
                # 本轮所有端点都没成功，退避后整体重试
                await asyncio.sleep(0.4 * (attempt + 1))
        logger.warning("12306 多次重试仍失败: %s", params)
        return None

    async def search(self, departure: str, destination: str, date: str,
                     transport_type: str = "all") -> list[dict]:
        smap = await _load_station_map()
        frm = _find_station_code(departure, smap)
        to = _find_station_code(destination, smap)
        if not frm or not to:
            logger.warning("12306 车站未匹配: %s/%s", departure, destination)
            return []

        params = {
            "leftTicketDTO.train_date": date,
            "leftTicketDTO.from_station": frm,
            "leftTicketDTO.to_station": to,
            "purpose_codes": "ADULT",
        }
        data = await self._query_with_retry(params)
        if not data:
            return []

        rows = data["data"]["result"]
        # 车次名→到站站码 映射（用于解析终到站名）
        mp = data["data"].get("map", {})

        results: list[dict] = []
        for row in rows:
            fields = row.split("|")
            # 12306 字段位置（queryO 接口）
            train_no = fields[3]       # 车次号 G123
            dep_station = mp.get(fields[6], fields[6])
            arr_station = mp.get(fields[7], fields[7])
            dep_time = fields[8]
            arr_time = fields[9]
            # 座位字段（不同席别余票，可能是"有"/数字）
            # 29: 商务座/特等座, 30: 一等座, 31: 二等座
            business = fields[32]
            first = fields[31]
            second = fields[30]
            # 票价字段：12306 余票接口不直接给票价，需要另一个接口
            # 这里先标记价格未知，让 LLM 知道是真实车次但价格需核实
            seat_price = None
            seat_label = ""
            if second not in ("", "--"):
                seat_label = "二等座"
            elif first not in ("", "--"):
                seat_label = "一等座"
            elif business not in ("", "--"):
                seat_label = "商务座"

            # 过滤：只保留高铁/动车（G/D/C 字头）
            if transport_type in ("高铁", "train") and not train_no[0] in ("G", "D", "C"):
                continue

            results.append({
                "type": "高铁/动车" if train_no[0] in ("G", "D", "C") else "普速",
                "number": train_no,
                "departure": dep_time,
                "arrival": arr_time,
                "duration": _parse_duration(dep_time, arr_time),
                "price": None,  # 12306 余票接口不含票价，需另查
                "seat": f"{seat_label}余票{second or first or business or '有'}",
                "dep_station": dep_station,
                "arr_station": arr_station,
            })

        # 按出发时间排序
        results.sort(key=lambda x: x["departure"])
        return results[:10]
