export default [
  {
    path: '/workflow',
    name: 'workflow',
    icon: 'apartment',
    routes: [
      {
        path: '/workflow/editor',
        name: 'workflow.editor',
        icon: 'edit',
        component: './FlowDemo',
      },
      {
        path: '/workflow/history',
        name: 'workflow.history',
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
  }
];
