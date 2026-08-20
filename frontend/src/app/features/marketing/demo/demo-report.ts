import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

import { PhotoComponent } from '../../../shared/photo/photo';

@Component({
  selector: 'app-demo-report',
  imports: [RouterLink, PhotoComponent],
  templateUrl: './demo-report.html',
  styleUrl: './demo-report.scss',
})
export class DemoReportComponent {}
