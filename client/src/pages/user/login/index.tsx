import {
  LoginForm,
  ProFormCheckbox,
} from '@ant-design/pro-components';
import {
  Helmet,
  useModel,
} from '@umijs/max';
import { Alert, App, Spin } from 'antd';
import { createStyles } from 'antd-style';
import React, { useEffect, useState } from 'react';
import { Footer } from '@/components';
import { ssoLogin } from '@/services/ant-design-pro/api';
import Settings from '../../../../config/defaultSettings';

const REDIRECT_STORAGE_KEY = 'wf_login_redirect';

/** 从 sessionStorage 获取并清除登录 redirect 目标 */
const getAndClearLoginRedirect = (): string => {
  const saved = sessionStorage.getItem(REDIRECT_STORAGE_KEY);
  if (saved) {
    sessionStorage.removeItem(REDIRECT_STORAGE_KEY);
    return saved;
  }
  // 兜底：从 URL 参数中取 redirect
  const urlParams = new URLSearchParams(window.location.search);
  const redirect = urlParams.get('redirect');
  if (redirect) {
    try {
      return decodeURIComponent(redirect);
    } catch {
      return redirect;
    }
  }
  return '/';
};

/**
 * Validate redirect URL to prevent open redirect attacks.
 * Only allow same-origin relative paths starting with '/'.
 * Handles both raw and encodeURIComponent-encoded values.
 */
const getSafeRedirectUrl = (redirect: string | null): string => {
  if (!redirect) return '/';
  // 先尝试 decode（可能是 encodeURIComponent 编码后的值）
  let decoded = redirect;
  try {
    decoded = decodeURIComponent(redirect);
  } catch {
    // 如果 decode 失败就用原值
  }
  if (!decoded.startsWith('/')) return '/';
  if (decoded.startsWith('//')) return '/';
  try {
    const parsed = new URL(decoded, window.location.origin);
    if (parsed.origin !== window.location.origin) return '/';
    return `${parsed.pathname}${parsed.search}${parsed.hash}`;
  } catch {
    return '/';
  }
};

/** 获取 SSO 回调 URL 中的 payload（token、username） */
const getSsoCallbackPayload = () => {
  const routeQuery: Record<string, string> = {};
  new URLSearchParams(window.location.search || '').forEach((v, k) => {
    routeQuery[k] = v;
  });
  const hashParams = new URLSearchParams((window.location.hash || '').replace(/^#\/?/, ''));

  const readValue = (keys: string[]) => {
    for (const key of keys) {
      const routeValue = routeQuery[key];
      if (routeValue) return String(routeValue).trim();
      const hashValue = hashParams.get(key);
      if (hashValue) return String(hashValue).trim();
    }
    return '';
  };

  return {
    token: readValue(['token', 'access_token', 'sso_token']),
    username: readValue(['username', 'user_name', 'login_name', 'loginName', 'name']),
  };
};

/** 构建 SSO 回调 URL */
const buildSsoCallbackUrl = () => {
  const ssoDirectCallbackUrl = (window as any).SSO_DIRECT_CALLBACK_URL || process.env.SSO_DIRECT_CALLBACK_URL;
  // 从当前登录页 URL 中获取 redirect 参数（已 encodeURIComponent）
  const redirect = new URL(window.location.href).searchParams.get('redirect');
  const callbackParams = new URLSearchParams();
  callbackParams.set('sso_callback', '1');
  if (redirect) {
    // 透传 redirect，保持编码
    callbackParams.set('redirect', redirect);
  }

  if (ssoDirectCallbackUrl) {
    const joinChar = ssoDirectCallbackUrl.includes('?') ? '&' : '?';
    return `${ssoDirectCallbackUrl}${joinChar}${callbackParams.toString()}`;
  }

  const callbackBase = `${window.location.origin}${window.location.pathname}`;
  return `${callbackBase}?${callbackParams.toString()}`;
};

/** 判断是否为 SSO 回调请求 */
const isSsoCallbackRequest = () => {
  const searchParams = new URLSearchParams(window.location.search || '');
  return searchParams.get('sso_callback') === '1';
};

/** 标记 SSO 跳转时间，防止循环跳转 */
const markSsoRedirect = () => {
  sessionStorage.setItem('wf_sso_redirect_at', String(Date.now()));
};

const clearSsoRedirectMark = () => {
  sessionStorage.removeItem('wf_sso_redirect_at');
};

const wasRecentSsoRedirect = () => {
  const raw = sessionStorage.getItem('wf_sso_redirect_at');
  if (!raw) return false;
  const timestamp = Number(raw);
  if (!timestamp || Number.isNaN(timestamp)) {
    clearSsoRedirectMark();
    return false;
  }
  return Date.now() - timestamp < 2 * 60 * 1000; // 2 分钟内
};

const useStyles = createStyles(({ token }) => {
  return {
    container: {
      display: 'flex',
      flexDirection: 'column',
      height: '100vh',
      overflow: 'auto',
      backgroundImage:
        "url('https://mdn.alipayobjects.com/yuyan_qk0oxh/afts/img/V-_oS6r-i7wAAAAAAAAAAAAAFl94AQBr')",
      backgroundSize: '100% 100%',
    },
    ssoTip: {
      marginBottom: 16,
      color: 'rgba(0, 0, 0, 0.65)',
    },
  };
});

const Login: React.FC = () => {
  const { initialState, setInitialState } = useModel('@@initialState');
  const { styles } = useStyles();
  const { message } = App.useApp();
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [ssoUsername, setSsoUsername] = useState('');

  const fetchUserInfo = async () => {
    const userInfo = await initialState?.fetchUserInfo?.();
    if (userInfo) {
      setInitialState((s) => ({
        ...s,
        currentUser: userInfo,
      }));
    }
  };

  /** 尝试使用 SSO 回调中的信息登录 */
  const trySsoCallbackLogin = async () => {
    const { token, username } = getSsoCallbackPayload();
    if (!token && !username) return false;

    setLoading(true);
    try {
      // 如果 SSO 回调带了 username，调用后端登录接口获取 token
      const loginResult = await ssoLogin({ username });
      const resultToken = loginResult.result?.token;
      const resultUsername = loginResult.result?.username || username;

      if (resultToken) {
        localStorage.setItem('access-token', resultToken);
      }

      clearSsoRedirectMark();
      setSsoUsername(resultUsername);

      message.success('登录成功！');
      await fetchUserInfo();

      // 从 sessionStorage 或 URL 参数获取 redirect 目标
      const redirectUrl = getAndClearLoginRedirect();
      // 安全验证：只允许同源相对路径
      if (redirectUrl.startsWith('/') && !redirectUrl.startsWith('//')) {
        window.location.href = redirectUrl;
      } else {
        window.location.href = '/';
      }
      return true;
    } catch (err: any) {
      const msg = err?.data?.message || err?.message || '登录失败，请重试';
      setErrorMessage(msg);
      message.error(msg);
      return false;
    } finally {
      setLoading(false);
    }
  };

  /** 启动 SSO 登录跳转 */
  const startSsoLogin = () => {
    setErrorMessage('');
    setSsoUsername('');
    setLoading(true);

    const ssoUrl = (window as any).SSO_URL || process.env.SSO_URL || 'https://sogame-kagura-gateway.corp.kuaishou.com/login';
    const jumpTargetUrl = buildSsoCallbackUrl();
    const jumpUrl = `${ssoUrl}?url=${encodeURIComponent(jumpTargetUrl)}`;
    markSsoRedirect();
    window.location.replace(jumpUrl);
  };

  useEffect(() => {
    // 1. 尝试使用 SSO 回调信息登录
    const payload = getSsoCallbackPayload();
    if (payload.token || payload.username) {
      trySsoCallbackLogin();
      return;
    }

    // 2. 如果是 SSO 回调但没带有效信息
    if (isSsoCallbackRequest()) {
      setErrorMessage('SSO 回调未携带有效登录信息，请检查 SSO 回调参数配置');
      return;
    }

    // 3. 如果刚跳转过 SSO 但回来还是没信息，防止循环跳转
    if (wasRecentSsoRedirect()) {
      setErrorMessage('SSO 登录未返回有效信息，已停止循环跳转，请检查 SSO 回调参数');
      return;
    }

    // 4. 正常启动 SSO 登录流程
    startSsoLogin();
  }, []);

  return (
    <div className={styles.container}>
      <Helmet>
        <title>
          登录页
          {Settings.title && ` - ${Settings.title}`}
        </title>
      </Helmet>
      <div
        style={{
          flex: '1',
          padding: '32px 0',
        }}
      >
        <LoginForm
          contentStyle={{
            minWidth: 280,
            maxWidth: '75vw',
          }}
          logo={<img alt="logo" src="/logo1.png" />}
          title="WorkFlow"
          subTitle="统一 SSO 登录"
          onFinish={async () => {
            // 点击登录按钮也触发 SSO 跳转
            startSsoLogin();
          }}
        >
          {errorMessage && (
            <Alert
              style={{ marginBottom: 24 }}
              message={errorMessage}
              type="error"
              showIcon
            />
          )}

          <div className={styles.ssoTip}>
            {loading ? (
              <Spin tip="正在处理登录..." />
            ) : (
              <span>点击登录将跳转到 SSO 进行认证，认证成功后将自动返回。</span>
            )}
          </div>

          {ssoUsername && (
            <div style={{ marginTop: 16, fontSize: 12, color: 'rgba(0, 0, 0, 0.65)' }}>
              当前认证用户：{ssoUsername}
            </div>
          )}
        </LoginForm>
      </div>
      <Footer />
    </div>
  );
};

export default Login;
