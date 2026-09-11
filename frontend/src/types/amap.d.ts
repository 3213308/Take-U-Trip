/** 高德 JSAPI 2.0 无官方 TS 类型，此处做环境声明 */

export {};

declare global {
  interface Window {
    /** 必须在 AMap 脚本加载前设置 */
    _AMapSecurityConfig?: {
      securityJsCode?: string;
      serviceHost?: string;
    };
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const AMap: any;
}
