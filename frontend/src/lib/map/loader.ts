import AMapLoader from "@amap/amap-jsapi-loader";

const AMAP_KEY = import.meta.env.VITE_AMAP_KEY as string | undefined;
const AMAP_SECURITY_CODE = import.meta.env.VITE_AMAP_SECURITY_CODE as string | undefined;

export function isAmapConfigured(): boolean {
  return Boolean(AMAP_KEY && AMAP_SECURITY_CODE);
}

let amapPromise: Promise<any> | null = null;

/**
 * 加载高德 JSAPI 2.0（全 app 单例）。
 * 安全密钥必须在 AMap 脚本加载前设置（新申请的 key 强制要求）。
 * 失败时清空缓存允许下次重试。
 */
export function loadAMap(): Promise<any> {
  if (amapPromise) return amapPromise;

  if (!isAmapConfigured()) {
    return Promise.reject(
      new Error("缺少高德地图配置：请在 .env.local 中填写 VITE_AMAP_KEY 与 VITE_AMAP_SECURITY_CODE"),
    );
  }

  window._AMapSecurityConfig = {
    securityJsCode: AMAP_SECURITY_CODE,
  };

  amapPromise = AMapLoader.load({
    key: AMAP_KEY!,
    version: "2.0",
    plugins: [
      "AMap.Geocoder",
      "AMap.Walking",
      "AMap.InfoWindow",
      "AMap.Scale",
      "AMap.ToolBar",
    ],
  }).catch((e) => {
    amapPromise = null;
    throw e;
  });

  return amapPromise;
}
