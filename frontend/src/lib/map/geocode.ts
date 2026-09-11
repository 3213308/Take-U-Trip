import type { GeoPoint } from "@/stores/mapStore";

/** 高德批量地理编码每批上限，超过会整批失败 */
const BATCH_LIMIT = 10;

/**
 * 从目的地字符串提取可用于 Geocoder 的城市名：
 * "四川（成都进出）" → "成都"、"北京" → "北京"；提取失败返回 undefined（全国搜索）
 */
export function extractCity(destination: string): string | undefined {
  const cityMatch = destination.match(/([一-龥]{2,6}?)(?:市|州|盟|地区)/);
  if (cityMatch) return cityMatch[1];
  const paren = destination.match(/[（(]([一-龥]{2,6})[)）]/);
  if (paren) {
    const cleaned = paren[1].replace(/(进出|周边|一带|深度|自由行|游玩)/g, "");
    if (cleaned.length >= 2) return cleaned.slice(0, 4);
  }
  return destination.length >= 2 && destination.length <= 4 ? destination : undefined;
}

function createGeocoder(AMap: any, city?: string): any {
  return city ? new AMap.Geocoder({ city }) : new AMap.Geocoder();
}

function geocodeBatch(
  AMap: any,
  city: string | undefined,
  addresses: string[],
): Promise<Map<string, GeoPoint>> {
  return new Promise((resolve) => {
    createGeocoder(AMap, city).getLocation(addresses, (status: string, result: any) => {
      const map = new Map<string, GeoPoint>();
      if (status === "complete" && result?.info === "OK") {
        const codes: any[] = result.geocodes ?? [];
        addresses.forEach((addr, i) => {
          const g = codes[i];
          if (g?.location && typeof g.location === "object") {
            map.set(addr, { lng: g.location.lng, lat: g.location.lat });
          }
        });
      }
      resolve(map);
    });
  });
}

/** 单点编码（批量失败的兜底），地址直查失败时尝试"城市+地址" */
function geocodeOne(
  AMap: any,
  city: string | undefined,
  address: string,
): Promise<GeoPoint | null> {
  const tryOnce = (addr: string) =>
    new Promise<GeoPoint | null>((resolve) => {
      createGeocoder(AMap, city).getLocation(addr, (status: string, result: any) => {
        const g = result?.geocodes?.[0];
        if (status === "complete" && result?.info === "OK" && g?.location && typeof g.location === "object") {
          resolve({ lng: g.location.lng, lat: g.location.lat });
        } else {
          resolve(null);
        }
      });
    });

  return (async () => {
    const direct = await tryOnce(address);
    if (direct) return direct;
    if (city && !address.startsWith(city)) {
      return tryOnce(`${city}${address}`);
    }
    return null;
  })();
}

/**
 * 批量地理编码：地点名 → 经纬度。
 * 自动分片（每批 ≤10）、批量失败地址单点兜底、兜底失败用"城市+地址"重试。
 */
export async function batchGeocode(
  AMap: any,
  addresses: string[],
  city?: string,
): Promise<Map<string, GeoPoint>> {
  const out = new Map<string, GeoPoint>();
  const uniq = [...new Set(addresses)];
  if (!uniq.length) return out;

  for (let start = 0; start < uniq.length; start += BATCH_LIMIT) {
    const chunk = uniq.slice(start, start + BATCH_LIMIT);
    const got = await geocodeBatch(AMap, city, chunk);
    for (const addr of chunk) {
      const hit = got.get(addr);
      if (hit) {
        out.set(addr, hit);
      } else {
        const pt = await geocodeOne(AMap, city, addr);
        if (pt) out.set(addr, pt);
      }
    }
  }
  return out;
}