export default [
  {
    path: '/user',
    layout: false,
    routes: [
      {
        path: '/user/login',
        component: './user/login',
      },
    ],
  },
  // Default workflow route — fullscreen (no ADP layout chrome)
  {
    path: '/workflow',
    component: './FlowDemo',
    layout: false,
  },
  // Legacy editor route — traditional sidebar layout
  {
    path: '/workflow/old',
    name: 'editor',
    icon: 'edit',
    component: './FlowDemo',
  },
  {
    path: '/workflow/history',
    name: 'history',
    icon: 'history',
    component: './FlowHistory',
  },
];
