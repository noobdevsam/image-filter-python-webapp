import {Component} from '@angular/core';
import {HttpClient} from '@angular/common/http';
import {CommonModule} from '@angular/common';
import {FormsModule} from '@angular/forms';

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

  // 4. Process Saved Server File
  // applyFilter(): void {
  //   if (!this.uploadedFileId) return;
  //
  //   this.isLoading = true;
  //   this.statusMessage = 'Processing filter on server...';
  //
  //   const formData = new FormData();
  //   formData.append('filter_type', this.selectedFilter);
  //   formData.append('param', this.filterParam.toString());
  //   formData.append('output_format', this.outputFormat);
  //
  //   this.http.post<any>(`${this.API_BASE}/files/process/${this.uploadedFileId}`, formData).subscribe({
  //     next: (res) => {
  //       this.processedFileId = res.processed_file_id;
  //       this.processedImageSrc = `${this.API_BASE}/files/download/${res.processed_file_id}?t=${Date.now()}`;
  //       this.statusMessage = `Filter '${this.selectedFilter}' applied successfully!`;
  //       this.isLoading = false;
  //     },
  //     error: (err) => {
  //       console.error('Processing error:', err);
  //       this.statusMessage = 'Failed to apply filter.';
  //       this.isLoading = false;
  //     }
  //   });
  // }
// --- OPTION A: If your backend returns binary blob streams directly (/api/filter) ---
  applyFilter(): void {
    if (!this.selectedFile) return;

    this.isLoading = true;
    this.statusMessage = 'Applying filter...';

    const formData = new FormData();
    formData.append('file', this.selectedFile);
    formData.append('filter_type', this.selectedFilter);
    formData.append('param', this.filterParam.toString());

    // Set responseType to 'blob' so Angular doesn't try to parse raw JPEG bytes as JSON
    this.http.post(`${this.API_BASE}/filter`, formData, {responseType: 'blob'}).subscribe({
      next: (blob: Blob) => {
        // Create a direct, cache-proof Blob Object URL for the <img> src tag
        if (this.processedImageSrc) {
          URL.revokeObjectURL(this.processedImageSrc); // Revoke previous memory allocation
        }
        this.processedImageSrc = URL.createObjectURL(blob);
        this.statusMessage = 'Filter applied successfully!';
        this.isLoading = false;
      },
      error: (err) => {
        console.error('Filter error:', err);
        this.statusMessage = 'Failed to apply filter.';
        this.isLoading = false;
      }
    });
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
