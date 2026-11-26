import { createRouter, createWebHistory } from 'vue-router'

import Overview from '@/views/Overview.vue'
import WorkbenchView from '@/views/WorkbenchView.vue'
import SnapshotSignoffView from '@/views/SnapshotSignoffView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'overview', component: Overview },
    {
      path: '/snapshot_signoff',
      name: 'snapshot_signoff',
      component: SnapshotSignoffView,
      props: true,
    },
    { path: '/signoff', component: SnapshotSignoffView },
    { path: '/snapshot-signoff', component: SnapshotSignoffView },
    { path: '/snapshot-sign-off', component: SnapshotSignoffView },
    { path: '/snapshot-approval', component: SnapshotSignoffView },
    { path: '/snapshot_approval', component: SnapshotSignoffView },
    { path: '/:moduleKey', name: 'module', component: WorkbenchView, props: true },
  ],
})

export default router
