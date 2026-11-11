import {Component, ElementRef, OnDestroy, ViewChild} from '@angular/core';
import {HttpClient} from '@angular/common/http';
import {CommonModule} from '@angular/common';
import {FormsModule} from '@angular/forms';
import {Subject, Subscription} from 'rxjs';
import {debounceTime, switchMap} from 'rxjs/operators';

export interface EmotionZone {
  type: 'face' | 'sky' | 'scenery';
  box: { x: number; y: number; width: number; height: number }; // percentages 0-100
  label?: string;
}

export interface ImageMetadata {
  dimensions: { width: number; height: number };
  channels: number;
  mean_intensity: { red: number; green: number; blue: number };
  detected_zones?: EmotionZone[];
  active_mood?: string;
}

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './app.html',
  styleUrls: ['./app.css']
})
export class AppComponent implements OnDestroy {
  private readonly API_BASE = 'http://localhost:8000/api';

  selectedFile: File | null = null;
  originalImageSrc: string | null = null;
  processedImageSrc: string | null = null;
  metadata: ImageMetadata | null = null;

  // Processing Modes: 'mood' (Adaptive Emotion Presets) or 'manual' (DIP Low-level filters)
  pipelineMode: 'mood' | 'manual' = 'mood';

  // Mood Presets & Emotion Zone Controls
  selectedMood: string = 'nostalgic_warmth';
  faceBrightness: number = 15;
  skySoftness: number = 5;
  claheClipLimit: number = 2.0;
  showZoneOverlay: boolean = true;

  // Manual DIP Filter Controls
  selectedFilter: string = 'average';
  filterParam: number = 5;

  isLoading: boolean = false;
  statusMessage: string = '';

  // Comparison slider
  viewMode: 'split' | 'side-by-side' = 'split';
  splitPosition: number = 50; // percentage
  isDraggingSplit: boolean = false;

  private currentBlobUrl: string | null = null;
  private filterTrigger$ = new Subject<void>();
  private filterSub: Subscription;

  @ViewChild('comparisonContainer') comparisonContainer?: ElementRef<HTMLDivElement>;

  constructor(private http: HttpClient) {
    // Reactive debounce stream for live-updating the photo
    this.filterSub = this.filterTrigger$
      .pipe(
        debounceTime(120),
        switchMap(() => {
          this.isLoading = true;
          this.statusMessage =
            this.pipelineMode === 'mood'
              ? `Enhancing memory with '${this.getMoodLabel()}' preset...`
              : `Applying ${this.selectedFilter}...`;

          const formData = new FormData();
          formData.append('file', this.selectedFile!);
          formData.append('pipeline_mode', this.pipelineMode);

          if (this.pipelineMode === 'mood') {
            formData.append('mood_preset', this.selectedMood);
            formData.append('face_brightness', this.faceBrightness.toString());
            formData.append('sky_softness', this.skySoftness.toString());
            formData.append('clahe_limit', this.claheClipLimit.toString());
          } else {
            formData.append('filter_type', this.selectedFilter);
            formData.append('param', this.filterParam.toString());
          }

          return this.http.post(`${this.API_BASE}/filter`, formData, {
            responseType: 'blob',
            observe: 'response',
          });
        })
      )
      .subscribe({
        next: (response) => {
          this.isLoading = false;
          if (this.currentBlobUrl) {
            URL.revokeObjectURL(this.currentBlobUrl);
          }

          if (response.body) {
            this.currentBlobUrl = URL.createObjectURL(response.body);
            this.processedImageSrc = this.currentBlobUrl;
          }

          const metaHeader = response.headers.get('X-Image-Meta');
          if (metaHeader) {
            try {
              this.metadata = JSON.parse(metaHeader);
            } catch (e) {
              console.error('Failed to parse metadata header', e);
            }
          }
          this.statusMessage = 'Memory enhanced successfully.';
        },
        error: (err) => {
          this.isLoading = false;
          console.error('Processing error:', err);
          this.statusMessage = 'Processing error. Ensure backend is running.';
        }
      });
  }

  ngOnDestroy(): void {
    this.filterSub.unsubscribe();
    if (this.currentBlobUrl) {
      URL.revokeObjectURL(this.currentBlobUrl);
    }
  }

  // 1. File Selection
  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files[0]) {
      this.selectedFile = input.files[0];

      const reader = new FileReader();
      reader.onload = (e) => {
        this.originalImageSrc = e.target?.result as string;
        this.triggerFilterUpdate();
      };
      reader.readAsDataURL(this.selectedFile);

      this.processedImageSrc = null;
      this.metadata = null;
    }
  }

  // 2. Mode and Parameter Handlers
  setPipelineMode(mode: 'mood' | 'manual'): void {
    this.pipelineMode = mode;
    this.triggerFilterUpdate();
  }

  onMoodChange(): void {
    if (this.selectedMood === 'nostalgic_warmth') {
      this.faceBrightness = 15;
      this.skySoftness = 5;
      this.claheClipLimit = 2.0;
    } else if (this.selectedMood === 'gentle_portrait') {
      this.faceBrightness = 25;
      this.skySoftness = 7;
      this.claheClipLimit = 1.5;
    } else if (this.selectedMood === 'silver_gelatin') {
      this.faceBrightness = 10;
      this.skySoftness = 3;
      this.claheClipLimit = 3.0;
    } else if (this.selectedMood === 'vivid_scenery') {
      this.faceBrightness = 10;
      this.skySoftness = 3;
      this.claheClipLimit = 3.5;
    }
    this.triggerFilterUpdate();
  }

  onFilterChange(): void {
    if (['average', 'median', 'gaussian'].includes(this.selectedFilter)) {
      this.filterParam = 5;
    } else if (this.selectedFilter === 'brightness') {
      this.filterParam = 30;
    } else if (this.selectedFilter === 'contrast') {
      this.filterParam = 1.5;
    } else {
      this.filterParam = 1.0;
    }
    this.triggerFilterUpdate();
  }

  onParamChange(): void {
    this.triggerFilterUpdate();
  }

  triggerFilterUpdate(): void {
    if (!this.selectedFile) return;
    this.filterTrigger$.next();
  }

  getMoodLabel(): string {
    switch (this.selectedMood) {
      case 'nostalgic_warmth': return 'Nostalgic Warmth (Sepia Tone)';
      case 'gentle_portrait': return 'Gentle Portrait (Soft Highlights)';
      case 'silver_gelatin': return 'Classic Silver Gelatin (Deep B&W)';
      case 'vivid_scenery': return 'Scenery Clarity (Texture Boost)';
      default: return this.selectedMood;
    }
  }

  // 3. Download
  downloadImage(): void {
    if (!this.processedImageSrc) return;
    const link = document.createElement('a');
    link.href = this.processedImageSrc;
    const name = this.pipelineMode === 'mood' ? this.selectedMood : this.selectedFilter;
    link.download = `memory_enhanced_${name}_${Date.now()}.jpg`;
    link.click();
  }

  // 4. Overlapping Split Comparison Slider handlers
  startDrag(event: MouseEvent | TouchEvent): void {
    this.isDraggingSplit = true;
    this.updateSplitPosition(event);
  }

  stopDrag(): void {
    this.isDraggingSplit = false;
  }

  onDrag(event: MouseEvent | TouchEvent): void {
    if (!this.isDraggingSplit) return;
    this.updateSplitPosition(event);
  }

  private updateSplitPosition(event: MouseEvent | TouchEvent): void {
    if (!this.comparisonContainer) return;
    const rect = this.comparisonContainer.nativeElement.getBoundingClientRect();
    const clientX = 'touches' in event ? event.touches[0].clientX : event.clientX;
    const offsetX = clientX - rect.left;
    const percentage = (offsetX / rect.width) * 100;
    this.splitPosition = Math.max(0, Math.min(100, percentage));
  }
}
