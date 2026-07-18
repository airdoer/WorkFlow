// @ts-ignore
/* eslint-disable */
import { request } from '@umijs/max';

/** SSO 登录 POST /api/auth/login */
export async function ssoLogin(body: { username?: string; key?: string }, options?: { [key: string]: any }) {
  return request<{ result: { token: string; username: string } }>('/api/auth/login', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  });
}

/** 获取当前用户信息 GET /api/user/info */
export async function currentUser(options?: { [key: string]: any }) {
  return request<{
    result: {
      name: string;
      username: string;
      role: { id: string; name: string; permissions: any[] };
      is_admin: boolean;
      access: string;
    };
  }>('/api/user/info', {
    method: 'GET',
    ...(options || {}),
  });
}

/** 退出登录 POST /api/auth/logout */
export async function outLogin(options?: { [key: string]: any }) {
  return request<Record<string, any>>('/api/auth/logout', {
    method: 'POST',
    ...(options || {}),
  });
}

/** 获取规则列表 GET /api/rule */
export async function rule(
  params: {
    // query
    /** 当前的页码 */
    current?: number;
    /** 页面的容量 */
    pageSize?: number;
  },
  options?: { [key: string]: any },
) {
  return request<API.RuleList>('/api/rule', {
    method: 'GET',
    params: {
      ...params,
    },
    ...(options || {}),
  });
}
