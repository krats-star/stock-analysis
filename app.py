import sys
import os
import io # Explicitly imported for main application context

from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, QFileDialog, QLineEdit, QTextEdit, QListWidget, QListWidgetItem, QMessageBox, QInputDialog
from PyQt5.QtCore import Qt, QThread, pyqtSignal

from googleapiclient.errors import HttpError

# Import functions from pdf_analyzer.py
from pdf_analyzer import extract_text_from_pdf
from google_drive_service import GoogleDriveService
from gemini_analyzer import GeminiAnalyzer

class Worker(QThread):
    # Signals for updating the UI
    status_update = pyqtSignal(str)
    folders_loaded = pyqtSignal(list)
    analysis_progress = pyqtSignal(str)
    analysis_complete = pyqtSignal(str)
    error_occurred = pyqtSignal(str, str)
    google_drive_service_initialized = pyqtSignal(object)
    gemini_analyzer_initialized = pyqtSignal(object)

    def __init__(self, selected_company_folder_id=None, google_drive_service=None, gemini_analyzer=None):
        super().__init__()
        self.selected_company_folder_id = selected_company_folder_id
        self.google_drive_service = google_drive_service
        self.gemini_analyzer = gemini_analyzer

    def run(self):
        if self.selected_company_folder_id is None:
            self.initialize_drive_service()
        else:
            self.analyze_pdfs()

    def initialize_drive_service(self):
        self.status_update.emit('Authenticating with Google Drive...')
        try:
            self.google_drive_service = GoogleDriveService()
            try:
                gemini_api_key = os.getenv("GEMINI_API_KEY")
                if not gemini_api_key:
                    self.status_update.emit('GEMINI_API_KEY not found. Please enter it.')
                    self.error_occurred.emit('API Key Missing', 'GEMINI_API_KEY environment variable not set. Please enter your Gemini API key.')
                    return
                self.gemini_analyzer = GeminiAnalyzer(gemini_api_key)
                
            except ValueError as e:
                self.error_occurred.emit('API Key Error', str(e))
                self.status_update.emit('Initialization failed.')
                return
            self.google_drive_service_initialized.emit(self.google_drive_service)
            self.gemini_analyzer_initialized.emit(self.gemini_analyzer)
            self.status_update.emit('Google Drive service initialized. Loading folders...')
            self.load_company_folders()
        except HttpError as error:
            self.error_occurred.emit('Google Drive Error', f'An error occurred with Google Drive authentication: {error}\nPlease ensure your credentials.json is valid and you have internet access.')
            self.status_update.emit('Authentication failed.')
        except Exception as e:
            self.error_occurred.emit('Error', f'An unexpected error occurred during Google Drive initialization: {e}')
            self.status_update.emit('Initialization failed.')

    def load_company_folders(self):
        if not self.google_drive_service:
            return

        company_folders = self.google_drive_service.list_company_folders()

        if not company_folders:
            self.status_update.emit("No company folders found in 'Stock Analysis'. Please create them on Google Drive.")
            self.folders_loaded.emit([])
            return

        self.folders_loaded.emit(company_folders)
        self.status_update.emit('Select a company folder to analyze.')

    def analyze_pdfs(self):
        if not self.selected_company_folder_id:
            self.error_occurred.emit('No Folder Selected', 'Please select a company folder from the list first.')
            return

        self.analysis_progress.emit(f'Starting PDF analysis for selected folder...')

        try:
            pdf_files = self.google_drive_service.list_pdf_files_in_folder(self.selected_company_folder_id)

            if not pdf_files:
                self.analysis_progress.emit(f"No PDF files found in the selected folder. Please upload some PDF files.")
                self.analysis_complete.emit("No PDFs to analyze.")
                return

            self.analysis_progress.emit(f"Found {len(pdf_files)} PDF files. Processing...")
            for pdf_file in pdf_files:
                file_id = pdf_file['id']
                file_name = pdf_file['name']
                self.analysis_progress.emit(f"\n--- Processing: {file_name} ---")

                try:
                    pdf_stream = self.google_drive_service.download_pdf(file_id, file_name)
                    print(f"Debug: Type of pdf_stream before passing to extract_text_from_pdf: {type(pdf_stream)}")
                    print(f"Debug: 'io' in globals() in app.py: {'io' in globals()}")
                    extracted_text = extract_text_from_pdf(pdf_stream)
                    
                    if not extracted_text.strip():
                        self.analysis_progress.emit(f"No text could be extracted from {file_name}. Skipping analysis.")
                        continue

                    self.analysis_progress.emit(f"Text extracted from {file_name}. Analyzing with Gemini...")

                    analysis_result = self.gemini_analyzer.analyze_text(extracted_text)
                    self.analysis_progress.emit(f"Analysis Result for {file_name}:\n{analysis_result}")

                except HttpError as e:
                    self.analysis_progress.emit(f"Error processing {file_name} (Google Drive/API issue): {e}")
                    self.error_occurred.emit('Google Drive Error', f"Error processing {file_name}: {e}")
                except Exception as e:
                    self.analysis_progress.emit(f"Error processing {file_name}: {e}")
                    self.error_occurred.emit('Processing Error', f"Error processing {file_name}: {e}")

            self.analysis_complete.emit("All selected PDFs processed.")

        except HttpError as e:
            self.analysis_progress.emit(f"Error during PDF analysis (Google Drive/API issue): {e}")
            self.error_occurred.emit('Analysis Error', f"Error during PDF analysis: {e}")
        except Exception as e:
            self.analysis_progress.emit(f"Error during PDF analysis: {e}")
            self.error_occurred.emit('Analysis Error', f"Error during PDF analysis: {e}")

class StockAnalyzerApp(QWidget):
    def __init__(self):
        super().__init__()
        self.google_drive_service = None
        self.gemini_analyzer = None
        self.selected_company_folder_id = None
        self.initUI()
        self.start_initialization_worker()

    def initUI(self):
        self.setWindowTitle('Stock Analysis Application')
        self.setGeometry(100, 100, 800, 600)

        self.layout = QVBoxLayout()

        # Folder Selection
        self.status_label = QLabel('Initializing...')
        self.layout.addWidget(self.status_label)

        self.company_folders_list = QListWidget()
        self.company_folders_list.itemClicked.connect(self.on_company_folder_selected)
        self.layout.addWidget(self.company_folders_list)

        self.selected_folder_label = QLabel('Selected Company Folder: None')
        self.layout.addWidget(self.selected_folder_label)

        # Analysis Button
        self.analyze_button = QPushButton('Analyze PDFs in Selected Folder')
        self.analyze_button.clicked.connect(self.start_analysis_worker)
        self.analyze_button.setEnabled(False) # Disable until services are initialized
        self.layout.addWidget(self.analyze_button)

        # Results Display
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.layout.addWidget(self.results_text)

        self.setLayout(self.layout)

    def start_initialization_worker(self):
        self.worker = Worker()
        self.worker.status_update.connect(self.status_label.setText)
        self.worker.folders_loaded.connect(self.populate_company_folders)
        self.worker.error_occurred.connect(self.handle_worker_error)
        self.worker.google_drive_service_initialized.connect(self.set_google_drive_service)
        self.worker.gemini_analyzer_initialized.connect(self.set_gemini_analyzer)
        self.worker.start()

    def handle_worker_error(self, title, message):
        if title == 'API Key Missing':
            self.prompt_for_gemini_key()
        else:
            self.show_message_box(title, message)

    def prompt_for_gemini_key(self):
        api_key, ok = QInputDialog.getText(self, 'Gemini API Key', 'Please enter your Gemini API Key:')
        if ok and api_key:
            os.environ["GEMINI_API_KEY"] = api_key
            QMessageBox.information(self, 'API Key Set', 'Gemini API Key has been set. Re-initializing application.')
            self.start_initialization_worker() # Re-trigger initialization
        else:
            QMessageBox.warning(self, 'API Key Required', 'Gemini API Key is required for analysis.')
            self.analyze_button.setEnabled(False) # Disable analysis if key is not set

    def set_google_drive_service(self, service):
        self.google_drive_service = service

    def set_gemini_analyzer(self, analyzer):
        self.gemini_analyzer = analyzer
        if self.google_drive_service and self.gemini_analyzer:
            self.analyze_button.setEnabled(True)

    def populate_company_folders(self, company_folders):
        self.company_folders_list.clear()
        for folder in company_folders:
            item = QListWidgetItem(folder['name'])
            item.setData(Qt.UserRole, folder['id']) # Store folder ID in item data
            self.company_folders_list.addItem(item)

    def on_company_folder_selected(self, item):
        self.selected_company_folder_id = item.data(Qt.UserRole)
        self.selected_folder_label.setText(f'Selected Company Folder: {item.text()}')
        self.results_text.clear()
        self.results_text.append(f'Ready to analyze PDFs in {item.text()}.')

    def start_analysis_worker(self):
        if not self.selected_company_folder_id:
            QMessageBox.warning(self, 'No Folder Selected', 'Please select a company folder from the list first.')
            return

        self.results_text.clear()
        self.worker = Worker(
            selected_company_folder_id=self.selected_company_folder_id,
            google_drive_service=self.google_drive_service,
            gemini_analyzer=self.gemini_analyzer
        )
        self.worker.analysis_progress.connect(self.results_text.append)
        self.worker.analysis_complete.connect(lambda msg: self.results_text.append(f"\n{msg}"))
        self.worker.error_occurred.connect(self.show_message_box)
        self.worker.start()

    def show_message_box(self, title, message):
        QMessageBox.critical(self, title, message)

if __name__ == '__main__':
    import sys
    app = QApplication(sys.argv)
    ex = StockAnalyzerApp()
    ex.show()
    sys.exit(app.exec_())