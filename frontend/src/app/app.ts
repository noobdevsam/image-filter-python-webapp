import {Component, ElementRef, OnDestroy, ViewChild} from '@angular/core';
import {HttpClient} from '@angular/common/http';
import {CommonModule} from '@angular/common';
import {FormsModule} from '@angular/forms';
import {Subject, Subscription} from 'rxjs';
import {debounceTime, distinctUntilChanged, switchMap} from 'rxjs/operators';

interface ImageMetadata {
  dimensions: { width: number; height: number };
  channels: number;
  mean_intensity: { red: number; green: number; blue: number };
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

  selectedFilter: string = 'average';
  filterParam: number = 5;
  isLoading: boolean = false;
  statusMessage: string = '';

  // Comparison slider
  viewMode: 'side-by-side' | 'split' = 'split';
  splitPosition: number = 50; // percentage
  isDraggingSplit: boolean = false;

  private currentBlobUrl: string | null = null;
  private filterTrigger$ = new Subject<{ filter: string; param: number }>();
  private filterSub: Subscription;

  @ViewChild('comparisonContainer') comparisonContainer?: ElementRef<HTMLDivElement>;

  constructor(private http: HttpClient) {
    // Debounce stream so slider dragging updates live without overwhelming the backend
    this.filterSub = this.filterTrigger$
      .pipe(
        debounceTime(100),
        switchMap(({filter, param}) => {
          this.isLoading = true;
          this.statusMessage = `Applying ${filter}...`;
          const formData = new FormData();
          formData.append('file', this.selectedFile!);
          formData.append('filter_type', filter);
          formData.append('param', param.toString());

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
          this.statusMessage = 'Filter applied in real-time.';
        },
        error: (err) => {
          this.isLoading = false;
          console.error('Processing error:', err);
          this.statusMessage = 'Failed to apply filter. Make sure backend is running.';
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
        // Automatically process immediately once file is picked
        this.triggerFilterUpdate();
      };
      reader.readAsDataURL(this.selectedFile);

      this.processedImageSrc = null;
      this.metadata = null;
    }
  }

  // 2. Filter or Param Change
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
    this.filterTrigger$.next({
      filter: this.selectedFilter,
      param: this.filterParam,
    });
  }

  // 3. Download Processed Image directly from local blob
  downloadImage(): void {
    if (!this.processedImageSrc) return;
    const link = document.createElement('a');
    link.href = this.processedImageSrc;
    link.download = `processed_${this.selectedFilter}_${Date.now()}.jpg`;
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
