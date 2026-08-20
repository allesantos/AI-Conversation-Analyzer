import { DatePipe, DecimalPipe } from '@angular/common';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import {
  DashboardConversationItem,
  DashboardSummary,
  InterestLevel,
} from '../../core/models/api.models';
import { AuthService } from '../../core/services/auth.service';
import { DashboardService } from '../../core/services/dashboard.service';
import { PhotoComponent } from '../../shared/photo/photo';
import { SignalPulseComponent } from '../../shared/signal-pulse/signal-pulse';

const USD_BRL_RATE = 5.5;

const LEVEL_ORDER: InterestLevel[] = [
  'MUITO_BAIXO',
  'BAIXO',
  'MODERADO',
  'ALTO',
  'MUITO_ALTO',
];

@Component({
  selector: 'app-dashboard',
  imports: [RouterLink, PhotoComponent, SignalPulseComponent, DatePipe, DecimalPipe],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.scss',
})
export class DashboardComponent implements OnInit {
  private readonly dashboardApi = inject(DashboardService);
  readonly auth = inject(AuthService);

  readonly summary = signal<DashboardSummary | null>(null);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);

  readonly distributionBars = computed(() => {
    const dist = this.summary()?.interest_distribution ?? {};
    const max = Math.max(1, ...LEVEL_ORDER.map((level) => dist[level] ?? 0));
    return LEVEL_ORDER.map((level) => {
      const count = dist[level] ?? 0;
      return {
        level,
        label: this.interestLevelLabel(level),
        count,
        widthPct: Math.round((count / max) * 100),
      };
    });
  });

  readonly hasAnalyzed = computed(() => (this.summary()?.analyzed_conversations ?? 0) > 0);

  ngOnInit(): void {
    this.dashboardApi.getSummary().subscribe({
      next: (data) => {
        this.summary.set(data);
        this.loading.set(false);
      },
      error: () => {
        this.error.set('Falha ao carregar o dashboard.');
        this.loading.set(false);
      },
    });
  }

  interestLevelLabel(level: InterestLevel | null | undefined): string {
    const labels: Record<InterestLevel, string> = {
      MUITO_BAIXO: 'Muito baixo',
      BAIXO: 'Baixo',
      MODERADO: 'Moderado',
      ALTO: 'Alto',
      MUITO_ALTO: 'Muito alto',
    };
    return level ? labels[level] : 'Sem análise';
  }

  formatCostBrl(costUsd: number): string {
    const brl = costUsd * USD_BRL_RATE;
    if (brl < 0.01) {
      return brl.toLocaleString('pt-BR', {
        style: 'currency',
        currency: 'BRL',
        minimumFractionDigits: 4,
      });
    }
    return brl.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
  }

  trackRecent(_index: number, item: DashboardConversationItem): string {
    return item.id;
  }
}
