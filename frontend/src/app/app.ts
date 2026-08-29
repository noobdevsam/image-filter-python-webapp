import {Component} from '@angular/core';
import {HttpClient} from '@angular/common/http';
import {CommonModule} from '@angular/common';
import {FormsModule} from '@angular/forms';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css']
})
export class AppComponent {
  selectedFile: File | null = null;
  originalImageSrc: string | null = null;
  processedImageSrc: string | null = null;

  selectedFilter: string = 'average';
  filterParam: number = 5;
  isLoading: boolean = false;

  constructor(private http: HttpClient) {
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files[0]) {
      this.selectedFile = input.files[0];
      const reader = new FileReader();
      reader.onload = (e) => this.originalImageSrc = e.target?.result as string;
      reader.readAsDataURL(this.selectedFile);
      this.processedImageSrc = null;
    }
  }

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
    const formData = new FormData();
    formData.append('file', this.selectedFile);
    formData.append('filter_type', this.selectedFilter);
    formData.append('param', this.filterParam.toString());

    this.http.post('http://localhost:8000/api/filter', formData, {responseType: 'blob'})
      .subscribe({
        next: (blob) => {
          this.processedImageSrc = URL.createObjectURL(blob);
          this.isLoading = false;
        },
        error: (err) => {
          console.error('Filter processing error:', err);
          this.isLoading = false;
        }
      });
  }

  saveImage(): void {
    if (!this.processedImageSrc) return;
    const link = document.createElement('a');
    link.href = this.processedImageSrc;
    link.download = `filtered_${this.selectedFilter}.jpg`;
    link.click();
  }
}
