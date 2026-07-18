// 环境配置：根据运行环境自动检测后端 URL
// - Docker 开发（Umi dev server）：留空，走 UMI 代理
// - 生产（Nginx 静态部署）：直接指向后端端口
// - 本地开发：留空，走 UMI 代理
(function() {
  // 如果已经通过其他方式设置，则不覆盖
  if (window.FLASK_BACKEND_URL) return;

  var hostname = window.location.hostname;

  // 检测是否为 Umi 开发服务器模式
  // Umi dev server 会在页面中注入 __UMI_UI__ 等标记
  // 或者通过检查是否运行在开发端口上
  // 最可靠的方式：Umi 开发模式下页面会有热更新标记
  var isUmiDev = (
    // Umi dev 模式特征：存在 hot update 相关全局变量
    typeof __webpack_hash__ !== 'undefined' ||
    // 或者检查 meta 标签
    document.querySelector('meta[name="umi-dev"]') !== null
  );

  if (isUmiDev) {
    // Umi 开发模式：不设置 FLASK_BACKEND_URL，所有请求走 Umi 代理
    return;
  }

  // 生产模式（非 localhost 访问的 Nginx 部署）：直接指向后端端口
  if (hostname !== 'localhost' && hostname !== '127.0.0.1') {
    window.FLASK_BACKEND_URL = 'http://' + hostname + ':16666';
  }
  // 本地开发时留空，走 UMI 代理
})();
