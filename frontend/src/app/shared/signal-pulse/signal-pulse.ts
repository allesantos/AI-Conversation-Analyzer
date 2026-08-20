import {
  Component,
  Input,
  OnChanges,
  SimpleChanges,
  ElementRef,
  ViewChild,
  AfterViewInit,
} from '@angular/core';
import { CommonModule } from '@angular/common';

type Level = 'MUITO_BAIXO' | 'BAIXO' | 'MODERADO' | 'ALTO' | 'MUITO_ALTO';

const LEVEL_AMPLITUDE: Record<Level, number> = {
  MUITO_BAIXO: 0.1,
  BAIXO: 0.25,
  MODERADO: 0.5,
  ALTO: 0.75,
  MUITO_ALTO: 1.0,
};

const LEVEL_COLOR: Record<Level, string> = {
  MUITO_BAIXO: '#b8a99a',
  BAIXO: '#b8a99a',
  MODERADO: '#d4a04a',
  ALTO: '#8b4a6b',
  MUITO_ALTO: '#c26a6a',
};

@Component({
  selector: 'app-signal-pulse',
  standalone: true,
  imports: [CommonModule],
  template: `
    <svg
      #svg
      [attr.width]="width"
      [attr.height]="height"
      [attr.viewBox]="'0 0 ' + width + ' ' + height"
      class="signal-pulse"
      role="img"
      [attr.aria-label]="'Pulso de sinal: ' + (level || 'sem dados')"
    >
      <path
        [attr.d]="pathData"
        fill="none"
        [attr.stroke]="strokeColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
        [class.animate-draw]="animate"
        [style.stroke-dasharray]="animate ? pathLength : 'none'"
        [style.stroke-dashoffset]="animate ? pathLength : '0'"
      />
      @if (showDot) {
        <circle
          [attr.cx]="dotX"
          [attr.cy]="dotY"
          r="4"
          [attr.fill]="strokeColor"
          class="pulse-dot"
        />
      }
    </svg>
  `,
  styles: `
    :host {
      display: inline-flex;
      align-items: center;
    }

    .signal-pulse {
      overflow: visible;
    }

    .animate-draw {
      animation: draw-pulse 1.2s ease-out forwards;
    }

    @keyframes draw-pulse {
      to {
        stroke-dashoffset: 0;
      }
    }

    .pulse-dot {
      opacity: 0;
      animation: fade-dot 0.3s ease-out 1.1s forwards;
    }

    @keyframes fade-dot {
      to {
        opacity: 1;
      }
    }

    @media (prefers-reduced-motion: reduce) {
      .animate-draw {
        animation: none;
        stroke-dashoffset: 0 !important;
        stroke-dasharray: none !important;
      }
      .pulse-dot {
        animation: none;
        opacity: 1;
      }
    }
  `,
})
export class SignalPulseComponent implements OnChanges, AfterViewInit {
  @Input() level: Level | string | null = null;
  @Input() width = 120;
  @Input() height = 40;
  @Input() animate = false;
  @Input() showDot = false;
  @Input() points: number[] | null = null;

  @ViewChild('svg') svgRef!: ElementRef<SVGElement>;

  pathData = '';
  pathLength = 0;
  strokeColor = '#6b7a99';
  dotX = 0;
  dotY = 0;

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  ngOnChanges(_changes: SimpleChanges): void {
    this.rebuild();
  }

  ngAfterViewInit(): void {
    this.measurePath();
  }

  private rebuild(): void {
    const amp = LEVEL_AMPLITUDE[(this.level as Level) ?? 'MODERADO'] ?? 0.5;
    this.strokeColor = LEVEL_COLOR[(this.level as Level) ?? 'MODERADO'] ?? '#6b7a99';
    const mid = this.height / 2;
    const maxAmp = mid * 0.85;

    if (this.points && this.points.length > 1) {
      this.pathData = this.buildFromPoints(this.points, mid, maxAmp);
    } else {
      this.pathData = this.buildPulse(amp, mid, maxAmp);
    }

    const lastSeg = this.pathData.split(/[A-Z]/i);
    const last = lastSeg[lastSeg.length - 1];
    const coords = last?.trim().split(/[\s,]+/).map(Number) ?? [];
    this.dotX = coords[coords.length - 2] || this.width;
    this.dotY = coords[coords.length - 1] || mid;

    requestAnimationFrame(() => this.measurePath());
  }

  private buildPulse(amp: number, mid: number, maxAmp: number): string {
    const w = this.width;
    const segments = 6;
    const step = w / segments;
    const pts: [number, number][] = [[0, mid]];

    for (let i = 1; i <= segments; i++) {
      const x = i * step;
      const noise = Math.sin(i * 1.8) * 0.6 + Math.sin(i * 3.1) * 0.4;
      const y = mid - noise * amp * maxAmp;
      pts.push([x, Math.max(2, Math.min(this.height - 2, y))]);
    }

    let d = `M${pts[0][0]},${pts[0][1]}`;
    for (let i = 1; i < pts.length; i++) {
      const [px, py] = pts[i - 1];
      const [cx, cy] = pts[i];
      const cpx = (px + cx) / 2;
      d += ` C${cpx},${py} ${cpx},${cy} ${cx},${cy}`;
    }
    return d;
  }

  private buildFromPoints(values: number[], mid: number, maxAmp: number): string {
    const max = Math.max(...values.map(Math.abs), 1);
    const w = this.width;
    const step = w / (values.length - 1 || 1);
    const pts: [number, number][] = values.map((v, i) => [
      i * step,
      mid - (v / max) * maxAmp * 0.8,
    ]);

    let d = `M${pts[0][0]},${pts[0][1]}`;
    for (let i = 1; i < pts.length; i++) {
      const [px, py] = pts[i - 1];
      const [cx, cy] = pts[i];
      const cpx = (px + cx) / 2;
      d += ` C${cpx},${py} ${cpx},${cy} ${cx},${cy}`;
    }
    return d;
  }

  private measurePath(): void {
    if (!this.svgRef) return;
    const path = this.svgRef.nativeElement.querySelector('path');
    if (path) {
      this.pathLength = (path as SVGPathElement).getTotalLength?.() || 200;
    }
  }
}
