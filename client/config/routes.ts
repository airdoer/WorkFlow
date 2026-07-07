export default [
  {
    path: '/workflow',
    name: '工作流',
    icon: 'apartment',
    routes: [
      {
        path: '/workflow/editor',
        name: '编辑器',
        icon: 'edit',
        component: './FlowDemo',
      },
      {
        path: '/workflow/history',
        name: '历史记录',
        icon: 'history',
        component: './FlowHistory',
      },
    ],
  },
  // Fullscreen editor route — no ADP layout chrome, accessible via fullscreen button
  {
    path: '/workflow/fullscreen',
    component: './FlowDemo',
    layout: false,
  },
  {
    name: 'result',
    icon: 'checkCircle',
    path: '/result',
    routes: [
      {
        path: '/result',
        redirect: '/result/success',
      },
      {
        name: 'success',
        icon: 'checkCircle',
        path: '/result/success',
        component: './result/success',
      },
      {
        name: 'fail',
        icon: 'closeCircle',
        path: '/result/fail',
        component: './result/fail',
      },
    ],
  },
];
