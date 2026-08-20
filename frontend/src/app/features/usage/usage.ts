import { DatePipe, DecimalPipe } from '@angular/common';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { UsageRecord, UsageSummary } from '../../core/models/api.models';
import { UsageService } from '../../core/services/usage.service';

/** Taxa fixa MVP — R$ por USD (estimativa, sem cotação ao vivo). */
const USD_BRL_RATE = 5.5;

export interface UsageDayGroup {
  key: string;
  label: string;
  records: UsageRecord[];
  totalCost: number;
}

@Component({
  selector: 'app-usage',
  imports: [DatePipe, DecimalPipe],
  templateUrl: './usage.html',
  styleUrl: './usage.scss',
})
export class UsageComponent implements OnInit {
  private readonly usageService = inject(UsageService);

  readonly summary = signal<UsageSummary | null>(null);
  readonly error = signal<string | null>(null);
  readonly selectedDay = signal<string | null>(null);

  readonly dayGroups = computed((): UsageDayGroup[] => {
    const records = this.summary()?.records ?? [];
    if (!records.length) {
      return [];
    }

    const byDay = new Map<string, UsageRecord[]>();
    for (const record of records) {
      const key = this.dayKey(record.created_at);
      const list = byDay.get(key);
      if (list) {
        list.push(record);
      } else {
        byDay.set(key, [record]);
      }
    }

    return [...byDay.entries()]
      .sort(([a], [b]) => (a < b ? 1 : a > b ? -1 : 0))
      .map(([key, dayRecords]) => ({
        key,
        label: this.dayLabel(key),
        records: dayRecords,
        totalCost: dayRecords.reduce((sum, r) => sum + r.estimated_cost, 0),
      }));
  });

  readonly activeDay = computed((): UsageDayGroup | null => {
    const groups = this.dayGroups();
    if (!groups.length) {
      return null;
    }
    const selected = this.selectedDay();
    return groups.find((g) => g.key === selected) ?? groups[0];
  });

  ngOnInit(): void {
    this.usageService.getSummary().subscribe({
      next: (data) => {
        this.summary.set(data);
        const first = this.dayGroups()[0];
        this.selectedDay.set(first?.key ?? null);
      },
      error: () => this.error.set('Falha ao carregar dados de uso.'),
    });
  }

  selectDay(key: string): void {
    this.selectedDay.set(key);
  }

  operationLabel(op: string): string {
    const labels: Record<string, string> = {
      analyze: 'Análise',
      ask: 'Pergunta',
      suggestions: 'Sugestões',
      embeddings: 'Embeddings',
      transcription: 'Transcrição',
    };
    return labels[op] ?? op;
  }

  formatCostUsd(cost: number): string {
    return cost < 0.01 ? `$${cost.toFixed(4)}` : `$${cost.toFixed(2)}`;
  }

  formatCostBrl(costUsd: number): string {
    const brl = costUsd * USD_BRL_RATE;
    if (brl < 0.01) {
      return brl.toLocaleString('pt-BR', {
        style: 'currency',
        currency: 'BRL',
        minimumFractionDigits: 4,
        maximumFractionDigits: 4,
      });
    }
    return brl.toLocaleString('pt-BR', {
      style: 'currency',
      currency: 'BRL',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }

  formatCostPair(costUsd: number): string {
    return `${this.formatCostUsd(costUsd)} · ${this.formatCostBrl(costUsd)}`;
  }

  trackRecord(_index: number, record: UsageRecord): string {
    return record.id;
  }

  private dayKey(iso: string): string {
    const d = new Date(iso);
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  }

  private dayLabel(key: string): string {
    const [y, m, d] = key.split('-').map(Number);
    const date = new Date(y, m - 1, d);
    return date.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
  }
}
