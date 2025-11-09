"""
Forms for bulk import operations.
"""
from django import forms


class BulkImportForm(forms.Form):
    """Form for uploading bulk import files."""
    
    file = forms.FileField(
        label="Upload File",
        help_text="Upload CSV or XLSX file for bulk import",
        required=True,
    )
    
    model_type = forms.ChoiceField(
        choices=[
            ("item", "Items"),
            ("batch", "Batches"),
            ("order", "Orders"),
        ],
        label="Import Type",
        required=True,
    )
    
    def clean_file(self):
        file = self.cleaned_data.get("file")
        
        if not file:
            raise forms.ValidationError("No file uploaded")
        
        # Validate file extension
        allowed_extensions = ['.csv', '.xlsx', '.xls']
        file_name = file.name.lower()
        
        if not any(file_name.endswith(ext) for ext in allowed_extensions):
            raise forms.ValidationError(
                f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
            )
        
        # Validate file size (max 10MB)
        max_size = 10 * 1024 * 1024  # 10MB
        if file.size > max_size:
            raise forms.ValidationError(
                f"File too large. Maximum size: 10MB"
            )
        
        return file
