import { ChangeDetectionStrategy, Component, computed, effect, inject, input, signal } from '@angular/core';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';

import { Video } from '../core/api.models';

const YOUTUBE_ID = /^[\w-]{11}$/;

@Component({
  selector: 'app-video-list',
  templateUrl: './video-list.component.html',
  styleUrl: './video-list.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class VideoListComponent {
  private readonly sanitizer = inject(DomSanitizer);

  readonly videos = input.required<Video[]>();

  /** Video being played inline, if any. */
  protected readonly playing = signal<string | null>(null);

  protected readonly playerUrl = computed<SafeResourceUrl | null>(() => {
    const id = this.playing();
    // Built from a validated id only: never trust a URL coming from the API.
    return id && YOUTUBE_ID.test(id)
      ? this.sanitizer.bypassSecurityTrustResourceUrl(
          `https://www.youtube-nocookie.com/embed/${id}?autoplay=1&rel=0`,
        )
      : null;
  });

  constructor() {
    // Stop the player when the list changes (other opening, other language).
    effect(() => {
      this.videos();
      this.playing.set(null);
    });
  }

  protected play(video: Video): void {
    this.playing.set(video.video_id);
  }

  protected duration(seconds: number): string {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = String(seconds % 60).padStart(2, '0');
    return h ? `${h}:${String(m).padStart(2, '0')}:${s}` : `${m}:${s}`;
  }

  protected views(count: number): string {
    return `${new Intl.NumberFormat('fr-FR', { notation: 'compact' }).format(count)} vues`;
  }
}
