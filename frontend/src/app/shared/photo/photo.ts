import { Component, input } from '@angular/core';

export type MarketingPhoto =
  | 'hero-chat'
  | 'import-chat'
  | 'empty-mood'
  | 'landing-mockup-hero'
  | 'landing-mockup-chat'
  | 'landing-mockup-phone'
  | 'landing-mockup-card'
  | 'landing-mockup-evidence'
  | 'landing-mockup-privacy';

const PHOTO_FILES: Record<MarketingPhoto, string> = {
  'hero-chat': 'hero-chat.jpg',
  'import-chat': 'import-chat.jpg',
  'empty-mood': 'empty-mood.jpg',
  'landing-mockup-hero': 'landing-mockup-hero.png',
  'landing-mockup-chat': 'landing-mockup-chat.png',
  'landing-mockup-phone': 'landing-mockup-phone.png',
  'landing-mockup-card': 'landing-mockup-card.png',
  'landing-mockup-evidence': 'landing-mockup-evidence.png',
  'landing-mockup-privacy': 'landing-mockup-privacy.png',
};

@Component({
  selector: 'app-photo',
  standalone: true,
  host: {
    '[class.photo-host--cover]': 'cover()',
    '[class.photo-host--fill]': 'fill()',
    '[class.photo-host--contain]': 'contain()',
  },
  template: `
    <img
      [class]="'app-photo ' + extraClass()"
      [src]="src()"
      [alt]="alt()"
      [style.object-position]="objectPosition() || null"
      [attr.loading]="priority() ? 'eager' : 'lazy'"
      [attr.fetchpriority]="priority() ? 'high' : null"
      decoding="async"
    />
  `,
  styles: `
    :host {
      display: block;
    }

    :host.photo-host--cover {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
    }

    :host.photo-host--fill {
      width: 100%;
      height: 100%;
    }

    :host.photo-host--contain {
      width: 100%;
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .app-photo {
      display: block;
      width: 100%;
      height: auto;
      object-fit: cover;
      border-radius: 20px;
    }

    :host.photo-host--cover .app-photo,
    :host.photo-host--fill .app-photo {
      height: 100%;
      border-radius: 0;
      object-position: 28% 58%;
    }

    :host.photo-host--contain .app-photo {
      width: auto;
      max-width: 100%;
      max-height: 100%;
      object-fit: contain;
      border-radius: 0;
    }
  `,
})
export class PhotoComponent {
  readonly name = input.required<MarketingPhoto>();
  readonly alt = input('');
  readonly extraClass = input('');
  readonly cover = input(false);
  readonly fill = input(false);
  readonly contain = input(false);
  readonly priority = input(false);
  readonly objectPosition = input('');

  src(): string {
    return `/assets/images/${PHOTO_FILES[this.name()]}`;
  }
}
