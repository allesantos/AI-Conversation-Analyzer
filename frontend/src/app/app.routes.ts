import { Routes } from '@angular/router';
import { authGuard, guestGuard } from './core/guards/auth.guard';
import { LoginComponent } from './features/auth/login/login';
import { RegisterComponent } from './features/auth/register/register';
import { DemoReportComponent } from './features/marketing/demo/demo-report';
import { ImportPageComponent } from './features/marketing/import-page/import-page';
import { LandingComponent } from './features/marketing/landing/landing';
import { ConversationDetailComponent } from './features/conversations/conversation-detail';
import { ConversationsComponent } from './features/conversations/conversations';
import { DashboardComponent } from './features/dashboard/dashboard';
import { ShellComponent } from './shared/shell/shell';
import { UsageComponent } from './features/usage/usage';

export const routes: Routes = [
  { path: '', component: LandingComponent, pathMatch: 'full' },
  { path: 'importar', component: ImportPageComponent },
  { path: 'demo', component: DemoReportComponent },
  { path: 'login', component: LoginComponent, canActivate: [guestGuard] },
  { path: 'register', component: RegisterComponent, canActivate: [guestGuard] },
  {
    path: '',
    component: ShellComponent,
    canActivate: [authGuard],
    children: [
      { path: 'dashboard', component: DashboardComponent },
      { path: 'conversations', component: ConversationsComponent },
      { path: 'conversations/:id', component: ConversationDetailComponent },
      { path: 'usage', component: UsageComponent },
    ],
  },
  { path: '**', redirectTo: '' },
];
