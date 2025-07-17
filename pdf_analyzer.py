import os
import os
import io

from PIL import Image
import pytesseract
from pdf2image import convert_from_bytes

# IMPORTANT: You need to install Tesseract OCR engine separately.
# Download from: https://tesseract-ocr.github.io/tessdoc/Downloads.html
# Then, set the path to the tesseract executable if it's not in your PATH.
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe' # Example path

# IMPORTANT: You also need to install Poppler to use pdf2image.
# Download from: http://blog.alivate.com.au/poppler-windows/
# Extract the archive and add the 'bin' folder to your system's PATH environment variable.


def extract_text_from_pdf(pdf_file_stream):
    text = ""
    try:
        # Reset stream position for image processing
        pdf_file_stream.seek(0)
        images = convert_from_bytes(pdf_file_stream.read())
        for img in images:
            text += pytesseract.image_to_string(img)
        print("Text extracted using OCR.")
        return text
    except Exception as e:
        print(f"Error extracting text from PDF using OCR: {e}. This might be a scanned PDF or an image-based PDF.")
        return ""