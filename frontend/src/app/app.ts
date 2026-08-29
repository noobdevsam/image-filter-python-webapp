import {CommonModule} from '@angular/common';
import {HttpClient} from '@angular/common/http';
import {Component, OnDestroy} from '@angular/core';
import {FormsModule} from '@angular/forms';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './app.html',
  styleUrls: ['./app.css']
})
export class AppComponent implements OnDestroy {
  private readonly apiUrl = 'http://localhost:8000/api/filter';

  selectedFile: File | null = null;
  originalImageSrc: string | null = null;
  processedImageSrc: string | null = null;
  selectedFilter = 'average';
  filterParam = 5;
  isLoading = false;
  errorMessage: string | null = null;
  selectedFileName: string | null = null;

  constructor(private http: HttpClient) {
  }

  ngOnDestroy(): void {
    this.revokeProcessedImageUrl();
  }

  get usesKernelSizeSlider(): boolean {
    return ['average', 'median', 'gaussian'].includes(this.selectedFilter);
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;

    if (!input.files || input.files.length === 0) {
      this.clearSelection();
      return;
    }

    this.selectedFile = input.files[0];
    this.selectedFileName = this.selectedFile.name;
    this.errorMessage = null;

    const reader = new FileReader();
    reader.onload = (e) => {
      this.originalImageSrc = e.target?.result as string;
    };
    reader.readAsDataURL(this.selectedFile);

    this.clearProcessedImage();
  }

  onFilterChange(): void {
    if (['average', 'median', 'gaussian'].includes(this.selectedFilter)) {
      this.filterParam = 5;
    } else if (this.selectedFilter === 'brightness') {
      this.filterParam = 30;
    } else if (this.selectedFilter === 'contrast') {
      this.filterParam = 1.5;
    } else {
      this.filterParam = 5;
    }

    this.errorMessage = null;
    this.clearProcessedImage();
  }

  applyFilter(): void {
    if (!this.selectedFile) {
      this.errorMessage = 'Please upload an image first.';
      return;
    }

    this.isLoading = true;
    this.errorMessage = null;

    const formData = new FormData();
    formData.append('file', this.selectedFile);
    formData.append('filter_type', this.selectedFilter);
    formData.append('param', this.filterParam.toString());

    this.http.post(this.apiUrl, formData, {responseType: 'blob' as const}).subscribe({
      next: (blob) => {
        this.revokeProcessedImageUrl();
        this.processedImageSrc = URL.createObjectURL(blob);
        this.isLoading = false;
      },
      error: (err) => {
        this.isLoading = false;
        this.processedImageSrc = null;
        this.errorMessage = this.extractErrorMessage(err);
      }
    });
  }

  saveImage(): void {
    if (!this.processedImageSrc) {
      return;
    }

    const link = document.createElement('a');
    link.href = this.processedImageSrc;
    link.download = `filtered_${this.selectedFilter}.jpg`;
    link.click();
  }

  clearSelection(): void {
    this.selectedFile = null;
    this.selectedFileName = null;
    this.originalImageSrc = null;
    this.errorMessage = null;
    this.clearProcessedImage();
  }

  private clearProcessedImage(): void {
    this.revokeProcessedImageUrl();
    this.processedImageSrc = null;
  }

  private revokeProcessedImageUrl(): void {
    if (this.processedImageSrc?.startsWith('blob:')) {
      URL.revokeObjectURL(this.processedImageSrc);
    }
  }

  private extractErrorMessage(err: unknown): string {
    if (typeof err === 'object' && err !== null) {
      const response = err as { error?: unknown; message?: unknown };

      if (typeof response.error === 'string') {
        return response.error;
      }

      if (typeof response.error === 'object' && response.error !== null) {
        const nested = response.error as { detail?: unknown };
        if (typeof nested.detail === 'string') {
          return nested.detail;
        }
      }

      if (typeof response.message === 'string') {
        return response.message;
      }
    }

    return 'Failed to process the image. Make sure the FastAPI backend is running on http://localhost:8000.';
  }
}
