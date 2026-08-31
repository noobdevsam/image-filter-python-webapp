import {Component} from '@angular/core';
import {HttpClient} from '@angular/common/http';
import {CommonModule} from '@angular/common';
import {FormsModule} from '@angular/forms';
import {finalize} from 'rxjs';

interface ImageMetadata {
  file_id: string;
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
export class AppComponent {
  private readonly API_BASE = 'http://localhost:8000/api';

  selectedFile: File | null = null;
  uploadedFileId: string | null = null;
  processedFileId: string | null = null;

  originalImageSrc: string | null = null;
  processedImageSrc: string | null = null;
  metadata: ImageMetadata | null = null;

  selectedFilter: string = 'average';
  filterParam: number = 5;
  outputFormat: string = 'jpg';
  isLoading: boolean = false;
  statusMessage: string = '';

  constructor(private http: HttpClient) {
  }

  // 1. Handle File Selection and Upload to Server Storage
  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files[0]) {
      this.selectedFile = input.files[0];

      // Local preview
      const reader = new FileReader();
      reader.onload = (e) => (this.originalImageSrc = e.target?.result as string);
      reader.readAsDataURL(this.selectedFile);

      // Reset state
      this.processedImageSrc = null;
      this.processedFileId = null;
      this.metadata = null;

      // Automatically upload file to persistent server storage
      this.uploadFileToServer();
    }
  }

  uploadFileToServer(): void {
    if (!this.selectedFile) return;

    this.isLoading = true;
    this.statusMessage = 'Uploading file to server...';
    const formData = new FormData();
    formData.append('file', this.selectedFile);

    this.http.post<any>(`${this.API_BASE}/files/upload`, formData).subscribe({
      next: (res) => {
        this.uploadedFileId = res.file_id;
        this.statusMessage = 'File uploaded successfully.';
        this.fetchMetadata(res.file_id);
        this.isLoading = false;
      },
      error: (err) => {
        console.error('Upload failed:', err);
        this.statusMessage = 'Failed to upload image to server.';
        this.isLoading = false;
      }
    });
  }

  // 2. Fetch Image Metadata Statistics
  fetchMetadata(fileId: string): void {
    this.http.get<ImageMetadata>(`${this.API_BASE}/files/metadata/${fileId}`).subscribe({
      next: (data) => (this.metadata = data),
      error: (err) => console.error('Error fetching metadata:', err)
    });
  }

  // 3. Reset Filter Default Parameter Bounds
  onFilterChange(): void {
    if (['average', 'median', 'gaussian'].includes(this.selectedFilter)) {
      this.filterParam = 5;
    } else if (this.selectedFilter === 'brightness') {
      this.filterParam = 30;
    } else if (this.selectedFilter === 'contrast') {
      this.filterParam = 1.5;
    }
  }


  applyFilter(): void {
    if (!this.selectedFile) return;

    this.isLoading = true;
    this.statusMessage = 'Processing filter on backend...';
    this.processedImageSrc = null;

    const formData = new FormData();
    formData.append('file', this.selectedFile);
    formData.append('filter_type', this.selectedFilter);
    formData.append('param', this.filterParam.toString());

    this.http.post<any>(`${this.API_BASE}/filter`, formData)
      .pipe(
        finalize(() => {
          this.isLoading = false;
        })
      )
      .subscribe({
        next: (res) => {
          this.processedFileId = res.processed_file_id;
          this.statusMessage = res.message || 'Filter applied successfully.';
          this.fetchProcessedImage();  // Load the processed image into the preview pane
        },
        error: (err) => {
          console.error('Processing error:', err);
          this.statusMessage = 'Failed to apply filter.';
        }
      });
  }

  // applyFilter(): void {
  //   if (!this.selectedFile) return;
  //
  //   this.isLoading = true;
  //   this.statusMessage = 'Processing filter on backend...';
  //   this.processedImageSrc = null; // Clear old preview
  //
  //   const formData = new FormData();
  //   formData.append('file', this.selectedFile);
  //   formData.append('filter_type', this.selectedFilter);
  //   formData.append('param', this.filterParam.toString());
  //
  //   // Expect default JSON response from backend
  //   this.http.post<any>(`${this.API_BASE}/filter`, formData).subscribe({
  //     next: (res) => {
  //       this.processedFileId = res.processed_file_id;
  //       this.statusMessage = res.message;
  //       this.isLoading = false;
  //     },
  //     error: (err) => {
  //       console.error('Processing error:', err);
  //       this.statusMessage = 'Failed to apply filter.';
  //       this.isLoading = false;
  //     }
  //   });
  // }

// Loads the image into the frontend "After" preview pane via download endpoint
  fetchProcessedImage(): void {
    if (!this.processedFileId) return;

    this.statusMessage = 'Fetching processed image from server...';
    // Append cache-busting timestamp to avoid stale browser cache
    this.processedImageSrc = `${this.API_BASE}/files/download/${this.processedFileId}?t=${Date.now()}`;
    this.statusMessage = 'Processed image loaded successfully!';
  }

  // 5. Download Output File Stream
  downloadImage(): void {
    if (!this.processedFileId) return;

    const downloadUrl = `${this.API_BASE}/files/download/${this.processedFileId}`;
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = this.processedFileId;
    link.click();
  }

  // 6. Purge Storage via Housekeeping Endpoint
  cleanupStorage(): void {
    this.http.delete<any>(`${this.API_BASE}/files/cleanup`).subscribe({
      next: (res) => {
        this.statusMessage = `Storage cleaned up. Removed ${res.files_deleted} files.`;
        this.originalImageSrc = null;
        this.processedImageSrc = null;
        this.selectedFile = null;
        this.uploadedFileId = null;
        this.processedFileId = null;
        this.metadata = null;
      },
      error: (err) => console.error('Cleanup failed:', err)
    });
  }
}
