// 环境配置：根据运行环境自动检测后端 URL
// - Docker 开发：使用宿主机映射的后端端口
// - 本地开发：留空，走 UMI 代理
// - 生产：使用实际后端地址
(function() {
  // 如果已经通过其他方式设置，则不覆盖
  if (window.FLASK_BACKEND_URL) return;

  var hostname = window.location.hostname;
  // Docker 容器内访问（非 localhost）时，直接指向后端端口
  if (hostname !== 'localhost' && hostname !== '127.0.0.1') {
    window.FLASK_BACKEND_URL = 'http://' + hostname + ':16666';
  }
  // 本地开发时留空，走 UMI 代理
})();
